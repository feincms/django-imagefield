"""Image processors for pyvips backend."""

from imagefield.backend_base import calculate_crop_box


VIPS_PROCESSORS = {}


def register_vips(fn):
    """Register processor for vips backend."""
    VIPS_PROCESSORS[fn.__name__] = fn
    return fn


# Import build_handler for use by default processor
from imagefield.processing_pillow import build_handler  # noqa: E402


@register_vips
def default(get_image):
    """Default processing pipeline for vips backend."""
    return build_handler(
        [
            "preserve_icc_profile",
            "process_gif",
            "process_png",
            "process_jpeg",
            "autorotate",
        ],
        get_image,
        registry=VIPS_PROCESSORS,
    )


@register_vips
def autorotate(get_image):
    """Automatically rotate image based on EXIF orientation."""

    def processor(image, context):
        return get_image(image.autorot(), context)

    return processor


@register_vips
def process_jpeg(get_image):
    """Process JPEG images - convert to RGB and set quality."""

    def processor(image, context):
        if context.save_kwargs["format"] == "JPEG":
            context.save_kwargs["quality"] = 90
            context.save_kwargs["progressive"] = True
            # Convert to RGB if not already
            if image.interpretation != "srgb":
                image = image.colourspace("srgb")
        return get_image(image, context)

    return processor


@register_vips
def process_png(get_image):
    """Process PNG images - convert palette mode to RGBA."""

    def processor(image, context):
        # Only convert palette/indexed images, like Pillow backend
        # In vips, indexed/palette images typically have bands < 3
        if context.save_kwargs["format"] == "PNG" and image.bands < 3:
            # Convert to sRGB (RGB)
            image = image.colourspace("srgb")
            # Add alpha channel for consistency with Pillow's RGBA conversion
            if not image.hasalpha():
                image = image.addalpha()

        return get_image(image, context)

    return processor


@register_vips
def process_gif(get_image):
    """Process GIF images - preserve transparency and palette."""

    def processor(image, context):
        if context.save_kwargs["format"] != "GIF":
            return get_image(image, context)

        # pyvips handles GIF transparency automatically
        # Just pass through
        return get_image(image, context)

    return processor


@register_vips
def preserve_icc_profile(get_image):
    """Preserve ICC color profile in processed images.

    Note: vips automatically preserves ICC profiles in write_to_buffer,
    so this is a no-op for compatibility with the Pillow backend's
    processing pipeline.
    """

    def processor(image, context):
        # vips preserves ICC profiles automatically - nothing to do
        return get_image(image, context)

    return processor


@register_vips
def thumbnail(get_image, size):
    """Resize image to fit within size, preserving aspect ratio."""

    def processor(image, context):
        image = get_image(image, context)
        # Calculate scale factor
        f = min(1.0, size[0] / image.width, size[1] / image.height)
        # Use thumbnail_image which is optimized for downscaling
        new_width = int(f * image.width)
        new_height = int(f * image.height)
        return image.thumbnail_image(new_width, height=new_height)

    return processor


@register_vips
def crop(get_image, size):
    """Crop image to exact size, centered on PPOI."""
    width, height = size

    def processor(image, context):
        image = get_image(image, context)

        # Calculate crop box using shared function
        box = calculate_crop_box(image.width, image.height, width, height, context.ppoi)

        # vips crop uses (left, top, width, height) format
        cropped_image = image.crop(box.left, box.top, box.width, box.height)

        # Resize to exact dimensions
        return cropped_image.thumbnail_image(width, height=height)

    return processor
