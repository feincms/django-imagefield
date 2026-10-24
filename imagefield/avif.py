from imagefield.processing_pillow import register_pillow


# Register with both backends since this processor only manipulates context
try:
    from imagefield.processing_vips import register_vips
except ImportError:
    # vips backend not available, that's OK
    def register_vips(fn):
        return fn


@register_pillow
@register_vips
def force_avif(get_image):
    def processor(image, context):
        context.save_kwargs["format"] = "AVIF"
        image = get_image(image, context)
        context.save_kwargs["quality"] = 80
        return image

    return processor


def avif(processors):
    def spec(fieldfile, context):
        context.extension = ".avif"
        context.processors = ["force_avif"] + processors

    return spec
