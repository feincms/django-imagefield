from imagefield.processing_pillow import register_pillow


# Register with both backends since this processor only manipulates context
try:
    from imagefield.processing_vips import register_vips
except ImportError:
    # vips backend not available, that's OK
    register_vips = lambda fn: fn  # noqa: E731


@register_pillow
@register_vips
def force_webp(get_image):
    def processor(image, context):
        context.save_kwargs["format"] = "WEBP"
        image = get_image(image, context)
        context.save_kwargs["quality"] = 95
        return image

    return processor


def webp(processors):
    def spec(fieldfile, context):
        context.extension = ".webp"
        context.processors = ["force_webp"] + processors

    return spec
