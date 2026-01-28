"""Image processors for Pillow backend."""

from PIL import Image, ImageOps


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
    def processor(image, context):
        if context.save_kwargs["format"] == "JPEG":
            context.save_kwargs["quality"] = 90
            context.save_kwargs["progressive"] = True
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
    width, height = size

    def processor(image, context):
        image = get_image(image, context)

        ppoi_x_axis = int(image.size[0] * context.ppoi[0])
        ppoi_y_axis = int(image.size[1] * context.ppoi[1])
        center_pixel_coord = (ppoi_x_axis, ppoi_y_axis)
        # Calculate the aspect ratio of `image`
        orig_aspect_ratio = float(image.size[0]) / float(image.size[1])
        crop_aspect_ratio = float(width) / float(height)

        # Figure out if we're trimming from the left/right or top/bottom
        if orig_aspect_ratio >= crop_aspect_ratio:
            # `image` is wider than what's needed,
            # crop from left/right sides
            orig_crop_width = int((crop_aspect_ratio * float(image.size[1])) + 0.5)
            orig_crop_height = image.size[1]
            crop_boundary_top = 0
            crop_boundary_bottom = orig_crop_height
            crop_boundary_left = center_pixel_coord[0] - (orig_crop_width // 2)
            crop_boundary_right = crop_boundary_left + orig_crop_width
            if crop_boundary_left < 0:
                crop_boundary_left = 0
                crop_boundary_right = crop_boundary_left + orig_crop_width
            elif crop_boundary_right > image.size[0]:
                crop_boundary_right = image.size[0]
                crop_boundary_left = image.size[0] - orig_crop_width

        else:
            # `image` is taller than what's needed,
            # crop from top/bottom sides
            orig_crop_width = image.size[0]
            orig_crop_height = int((float(image.size[0]) / crop_aspect_ratio) + 0.5)
            crop_boundary_left = 0
            crop_boundary_right = orig_crop_width
            crop_boundary_top = center_pixel_coord[1] - (orig_crop_height // 2)
            crop_boundary_bottom = crop_boundary_top + orig_crop_height
            if crop_boundary_top < 0:
                crop_boundary_top = 0
                crop_boundary_bottom = crop_boundary_top + orig_crop_height
            elif crop_boundary_bottom > image.size[1]:
                crop_boundary_bottom = image.size[1]
                crop_boundary_top = image.size[1] - orig_crop_height
        # Cropping the image from the original image
        cropped_image = image.crop(
            (
                crop_boundary_left,
                crop_boundary_top,
                crop_boundary_right,
                crop_boundary_bottom,
            )
        )
        # Resizing the newly cropped image to the size specified
        # (as determined by `width`x`height`)
        return cropped_image.resize((width, height), Image.Resampling.LANCZOS)

    return processor
