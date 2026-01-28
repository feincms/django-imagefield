from imagefield.processing_pillow import register_pillow


# Register with both backends since this processor only manipulates context
try:
    from imagefield.processing_vips import register_vips
except ImportError:
    # vips backend not available, that's OK
    register_vips = lambda fn: fn  # noqa: E731


@register_pillow
@register_vips
def force_jpeg(get_image):
    def processor(image, context):
        context.save_kwargs["format"] = "JPEG"
        image = get_image(image, context)
        context.save_kwargs["quality"] = 95
        return image

    return processor


def websafe(processors, extensions=None):
    extensions = extensions or {".png", ".gif", ".jpg", ".jpeg"}

    def spec(fieldfile, context):
        # XXX image type match would be SO much better instead of checking extensions
        if context.extension.lower() in extensions:
            context.processors = processors
        else:
            context.extension = ".jpg"
            context.processors = ["force_jpeg"]
            context.processors.extend(processors)

    return spec
