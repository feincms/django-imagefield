"""Image processors for Pillow backend."""

from PIL import Image, ImageOps

from imagefield.backend_base import calculate_crop_box


PILLOW_PROCESSORS = {}


def build_handler(processors, handler=None, registry=None):
    """Build processor handler chain using specified registry.

    Args:
        processors: List of processor names or (name, *args) tuples
        handler: Base handler function (defaults to identity function)
        registry: Processor registry dict (defaults to PILLOW_PROCESSORS for backward compat)

    Returns:
        Composed handler function that processes images through the chain
    """
    registry = registry or PILLOW_PROCESSORS
    handler = handler or (lambda image, context: image)

    for part in reversed(processors):
        if isinstance(part, list | tuple):
            handler = registry[part[0]](handler, *part[1:])
        else:
            handler = registry[part](handler)

    return handler


def register_pillow(fn):
    """Register processor for Pillow backend."""
    PILLOW_PROCESSORS[fn.__name__] = fn
    return fn


@register_pillow
def default(get_image):
    return build_handler(
        [
            "preserve_icc_profile",
            "process_gif",
            "process_png",
            "process_jpeg",
            "autorotate",
        ],
        get_image,
    )


@register_pillow
def autorotate(get_image):
    def processor(image, context):
        return get_image(ImageOps.exif_transpose(image), context)

    return processor


@register_pillow
def process_jpeg(get_image):
    """Process JPEG images - convert to RGB, set quality."""

    def processor(image, context):
        if context.save_kwargs["format"] == "JPEG":
            context.save_kwargs["quality"] = 90
            context.save_kwargs["progressive"] = True
            # TODO: Could preserve grayscale ("L" mode) to save space,
            # but keeping simple conversion for now for compatibility
            if image.mode != "RGB":
                image = image.convert("RGB")
        return get_image(image, context)

    return processor


@register_pillow
def process_png(get_image):
    def processor(image, context):
        if context.save_kwargs["format"] == "PNG" and image.mode == "P":
            image = image.convert("RGBA")

        return get_image(image, context)

    return processor


@register_pillow
def process_gif(get_image):
    def processor(image, context):
        if context.save_kwargs["format"] != "GIF":
            return get_image(image, context)

        if "transparency" in image.info:
            context.save_kwargs["transparency"] = image.info["transparency"]
        palette = image.getpalette()
        image = get_image(image, context)
        image.putpalette(palette)
        return image

    return processor


@register_pillow
def preserve_icc_profile(get_image):
    def processor(image, context):
        icc_profile = image.info.get("icc_profile")
        if icc_profile:
            context.save_kwargs["icc_profile"] = icc_profile
        return get_image(image, context)

    return processor


@register_pillow
def thumbnail(get_image, size):
    def processor(image, context):
        image = get_image(image, context)
        f = min(1.0, size[0] / image.size[0], size[1] / image.size[1])
        return image.resize(
            [int(f * coord) for coord in image.size], Image.Resampling.LANCZOS
        )

    return processor


@register_pillow
def crop(get_image, size):
    """Crop image to exact size, centered on PPOI."""
    width, height = size

    def processor(image, context):
        image = get_image(image, context)

        # Calculate crop box using shared function
        box = calculate_crop_box(
            image.size[0], image.size[1], width, height, context.ppoi
        )

        # PIL crop uses (left, top, right, bottom) format
        cropped_image = image.crop(
            (box.left, box.top, box.left + box.width, box.top + box.height)
        )

        # Resize to exact dimensions
        return cropped_image.resize((width, height), Image.Resampling.LANCZOS)

    return processor
