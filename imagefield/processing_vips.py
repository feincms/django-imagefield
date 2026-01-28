"""Image processors for pyvips backend."""

import pyvips


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
        # Check if image is palette/indexed mode
        # In vips, this would be an image with a colormap
        if context.save_kwargs["format"] == "PNG":
            # pyvips doesn't have an exact equivalent to PIL's "P" mode,
            # but we can check if the image has bands < 3 and convert
            if image.bands < 3:
                image = image.colourspace("srgb")
            # Ensure we have an alpha channel if needed
            if image.bands == 3 and not image.hasalpha():
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
    """Preserve ICC color profile in processed images."""

    def processor(image, context):
        try:
            icc_profile = image.get("icc-profile-data")
            if icc_profile:
                context.save_kwargs["icc_profile"] = icc_profile
        except pyvips.Error:
            # No ICC profile present
            pass
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

        ppoi_x_axis = int(image.width * context.ppoi[0])
        ppoi_y_axis = int(image.height * context.ppoi[1])
        center_pixel_coord = (ppoi_x_axis, ppoi_y_axis)

        # Calculate the aspect ratio of `image`
        orig_aspect_ratio = float(image.width) / float(image.height)
        crop_aspect_ratio = float(width) / float(height)

        # Figure out if we're trimming from the left/right or top/bottom
        if orig_aspect_ratio >= crop_aspect_ratio:
            # `image` is wider than what's needed,
            # crop from left/right sides
            orig_crop_width = int((crop_aspect_ratio * float(image.height)) + 0.5)
            orig_crop_height = image.height
            crop_boundary_top = 0
            crop_boundary_left = center_pixel_coord[0] - (orig_crop_width // 2)
            if crop_boundary_left < 0:
                crop_boundary_left = 0
            elif crop_boundary_left + orig_crop_width > image.width:
                crop_boundary_left = image.width - orig_crop_width

        else:
            # `image` is taller than what's needed,
            # crop from top/bottom sides
            orig_crop_width = image.width
            orig_crop_height = int((float(image.width) / crop_aspect_ratio) + 0.5)
            crop_boundary_left = 0
            crop_boundary_top = center_pixel_coord[1] - (orig_crop_height // 2)
            if crop_boundary_top < 0:
                crop_boundary_top = 0
            elif crop_boundary_top + orig_crop_height > image.height:
                crop_boundary_top = image.height - orig_crop_height

        # Crop the image (vips.crop uses left, top, width, height)
        cropped_image = image.crop(
            crop_boundary_left,
            crop_boundary_top,
            orig_crop_width,
            orig_crop_height,
        )

        # Resize to exact dimensions
        return cropped_image.thumbnail_image(width, height=height)

    return processor
