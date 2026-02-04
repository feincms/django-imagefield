=================
django-imagefield
=================

.. image:: https://github.com/matthiask/django-imagefield/workflows/Tests/badge.svg
    :target: https://github.com/matthiask/django-imagefield

.. image:: https://readthedocs.org/projects/django-imagefield/badge/?version=latest
    :target: https://django-imagefield.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Heavily based on `django-versatileimagefield
<https://github.com/respondcreate/django-versatileimagefield>`_, but
with a few important differences:

- The amount of code is kept at a minimum. django-versatileimagefield
  has several times as much code (without tests).
- Generating images on-demand inside rendering code is made hard on
  purpose. Instead, images are generated when models are saved and also
  by running the management command ``process_imagefields``.
- django-imagefield does not depend on a fast storage or a cache to be
  and stay fast, at least as long as the image width and height is saved
  in the database. An important part of this is never determining
  whether a processed image exists in the hot path at all (except if you
  ``force`` it).
- django-imagefield fails early when image data is incomplete or not
  processable by Pillow_ for some reason.
- django-imagefield allows adding width, height and PPOI (primary point
  of interest) fields to the model by adding ``auto_add_fields=True`` to
  the field instead of boringly and verbosingly adding them yourself.

Replacing existing uses of django-versatileimagefield requires the
following steps:

- ``from imagefield.fields import ImageField as VersatileImageField, PPOIField``
- Specify the image sizes by either providing ``ImageField(formats=...)`` or
  adding the ``IMAGEFIELD_FORMATS`` setting. The latter overrides the
  former if given.
- Convert template code to access the new properties (e.g.
  ``instance.image.square`` instead of ``instance.image.crop.200x200``
  when using the ``IMAGEFIELD_FORMATS`` setting below).
- When using django-imagefield with a PPOI, make sure that the PPOI
  field is also added to ``ModelAdmin`` or ``InlineModelAdmin``
  fieldsets, otherwise you'll just see the image, but no PPOI picker.
  Contrary to django-versatileimagefield the PPOI field is editable
  itself, which avoids apart from other complexities a pitfall with
  inline form change detection.
- Add ``"imagefield"`` to ``INSTALLED_APPS``.

If you used e.g. ``instance.image.crop.200x200`` and
``instance.image.thumbnail.800x500`` before, you should add the
following setting:

.. code-block:: python

    IMAGEFIELD_FORMATS = {
        # image field path, lowercase
        'yourapp.yourmodel.image': {
            'square': ['default', ('crop', (200, 200))],
            'full': ['default', ('thumbnail', (800, 500))],

            # The 'full' spec is equivalent to the following format
            # specification in terms of image file produced (the
            # resulting file name is different though):
            # 'full': [
            #     'autorotate', 'process_jpeg', 'process_png',
            #     'process_gif', 'autorotate',
            #     ('thumbnail', (800, 500)),
            # ],
            # Note that the exact list of default processors may
            # change in the future.
        },
    }

After running ``./manage.py process_imagefields --all`` once you can now
use use ``instance.image.square`` and ``instance.image.thumbnail`` in
templates instead. Note that the properties on the ``image`` file do by
design not check whether thumbs exist.


Installation
============

Install from PyPI: ``pip install django-imagefield``.

For faster image processing with pyvips (optional)::

    pip install django-imagefield[vips]

Then add ``imagefield`` to your project's ``INSTALLED_APPS``::

    # settings.py
    INSTALLED_APPS = [
      ...
      "imagefield",
      ...
    ]


Image Processing Backends
==========================

django-imagefield supports two image processing backends:

**Pillow (default)**
  The default backend using the Pillow library. Provides 100% backward
  compatibility with existing code. No configuration needed.

**pyvips (optional, faster)**
  An optional backend using the libvips library through pyvips. Offers
  significantly better performance:

  - Significantly faster image processing
  - More memory-efficient image handling
  - Improved handling of large images

To use the pyvips backend:

1. Install the optional dependency::

    pip install django-imagefield[vips]

2. Configure the backend in your settings::

    # settings.py
    IMAGEFIELD_BACKEND = "vips"  # default is "pillow"

Both backends support all the same features and processors. You can switch
between backends without changing your code or reprocessing existing images.

Backend Behavior Differences
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While both backends provide the same API, there are some subtle differences in
how images are processed:

**ICC Color Profiles**
  - **Pillow**: Explicitly preserves ICC profiles via ``preserve_icc_profile`` processor
  - **vips**: Automatically preserves ICC profiles during image operations

**JPEG Color Space Handling**
  - **Pillow**: Converts all non-RGB images (including grayscale) to RGB
  - **vips**: Preserves grayscale images natively, only converts CMYK and images
    with transparency. Results in smaller file sizes for grayscale JPEGs.

**PNG Indexed Color Handling**
  - **Pillow**: Converts palette mode ("P") images to RGBA
  - **vips**: Converts images with < 3 bands (indexed/palette) to RGBA

These differences are generally transparent and result in equivalent or improved
output quality. The vips backend is optimized for better performance and smaller
file sizes where possible.

Custom Processors
-----------------

When writing custom processors, you work directly with the native image
objects of your chosen backend:

**Pillow backend** - processors receive ``PIL.Image.Image`` objects::

    from imagefield.processing_pillow import register_pillow
    from PIL import ImageDraw, ImageFont

    @register_pillow
    def add_watermark(get_image, text="© Copyright"):
        def processor(image, context):
            image = get_image(image, context)
            # Use full PIL API
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype("arial.ttf", 36)
            draw.text((10, 10), text, font=font, fill=(255, 255, 255, 128))
            return image
        return processor

**pyvips backend** - processors receive ``pyvips.Image`` objects::

    from imagefield.processing_vips import register_vips
    import pyvips

    @register_vips
    def add_watermark(get_image, text="© Copyright"):
        def processor(image, context):
            image = get_image(image, context)
            # Use full pyvips API
            text_img = pyvips.Image.text(text, font="sans 36", rgba=True)
            return image.composite(text_img, 'over', x=10, y=10)
        return processor

For processors that only manipulate context (like changing format or quality),
you can register them for both backends::

    from imagefield.processing_pillow import register_pillow
    try:
        from imagefield.processing_vips import register_vips
    except ImportError:
        register_vips = lambda fn: fn

    @register_pillow
    @register_vips
    def force_quality(get_image, quality=95):
        def processor(image, context):
            context.save_kwargs["quality"] = quality
            return get_image(image, context)
        return processor


Usage
=====

Once ``imagefield`` is added to ``INSTALLED_APPS``, add ``ImageField``
instances to your Django models in the usual way::

    from django.db import models
    from imagefield.fields import ImageField


    class ImageModel(models.Model):

        image = ImageField(
            upload_to="images",
            formats={
                "thumb": ["default", ("crop", (300, 300))],
                "desktop": ["default", ("thumbnail", (300, 225))],
            },
            auto_add_fields=True,
        )

* ``formats`` determines the sizes of the processed images created.
* ``auto_add_fields`` will add ``image_width``, ``image_height``, and ``image_ppoi``
  fields automatically, if not present on the model. (The field names used are
  customisable. See the ``ImageField`` constructor for details.)

A widget for selecting the PPOI is automatically used in the Django Admin.

To use an ``ImageField`` in your own Django Form, you should ensure that the
``image_ppoi`` field is added the form::

    from django.form import modelform_factory

    form_cls = modelform_factory(ImageModel, fields=['image', 'image_ppoi'])

You should make sure to add the ``form.media`` to your page template's ``<head>``.

Retrieve the image URL in your template like, ``instance.image.thumb``.


Template Usage
==============

Access image URLs in templates by using the format names defined in ``formats`` or
``IMAGEFIELD_FORMATS``:

.. code-block:: html

    <!-- Direct URL access -->
    <img src="{{ instance.image.thumb }}" alt="Thumbnail">
    <img src="{{ instance.image.desktop }}" alt="Desktop">

    <!-- In a background image -->
    <div style="background-image: url({{ instance.image.thumb }})"></div>

    <!-- Get width/height from auto-added fields -->
    <img src="{{ instance.image.thumb }}"
         width="{{ instance.image_width }}"
         height="{{ instance.image_height }}"
         alt="Image">


IMAGEFIELD_FORMATS Structure
=============================

The ``IMAGEFIELD_FORMATS`` setting maps field paths to format specifications:

.. code-block:: python

    IMAGEFIELD_FORMATS = {
        # Key: "app_label.model_name.field_name" (lowercase)
        "yourapp.yourmodel.image": {
            # Value: Dict of format_name -> processor_list
            "format_name": [processor1, processor2, ...],
        },
    }

Each format specification is a list of processors. Processors can be:

- **String**: A processor name without arguments, e.g. ``"autorotate"``
- **Tuple**: A processor with arguments, e.g. ``("thumbnail", (800, 600))``
- **"default"**: Shorthand for common processors (autorotate, process_jpeg, process_png, process_gif, preserve_icc_profile)

Common processor arguments:

- ``("thumbnail", (width, height))``: Resize to fit within bounding box, preserving aspect ratio
- ``("crop", (width, height))``: Crop to exact dimensions, centered on PPOI

Example:

.. code-block:: python

    IMAGEFIELD_FORMATS = {
        "blog.post.header_image": {
            "thumbnail": ["default", ("thumbnail", (400, 300))],
            "square": ["default", ("crop", (200, 200))],
        },
    }


Forms
=====

The form widget builds on top of the default Django image field which allows
resetting the value of the field; it additionally shows a preview image, and if
there's a linked PPOI field, a PPOI picker.

The default preview is a max. 300x300 thumbnail. You can customize this by
adding a ``preview`` format spec to the list of formats.


Django REST Framework
=====================

To serialize image fields with their various formats in DRF, use ``SerializerMethodField``:

.. code-block:: python

    from rest_framework import serializers

    class MyModelSerializer(serializers.ModelSerializer):
        image_urls = serializers.SerializerMethodField()

        class Meta:
            model = MyModel
            fields = ['id', 'image_urls']

        def get_image_urls(self, obj):
            if not obj.image:
                return None
            return {
                'thumb': obj.image.thumb,
                'desktop': obj.image.desktop,
            }

This returns a dictionary of URLs for each defined format.


File Deletion
=============

When an image field is cleared or a model instance is deleted, django-imagefield
automatically removes all generated/processed images. However, the original uploaded
file is not automatically deleted, following Django's default behavior to prevent
accidental data loss.

If you need to delete original files, you can implement a custom signal handler.
See `Django's documentation on signals <https://docs.djangoproject.com/en/stable/ref/signals/#post-delete>`_
for details on handling the ``post_delete`` signal.


Image processors
================

django-imagefield uses an image processing pipeline modelled after
Django's middleware.

The following processors are available out of the box:

- ``autorotate``: Autorotates an image by reading the EXIF data.
- ``process_jpeg``: Converts non-RGB images to RGB, activates
  progressive encoding and sets quality to a higher value of 90.
- ``process_png``: Converts PNG images with palette to RGBA.
- ``process_gif``: Preserves transparency and palette data in resized
  images.
- ``preserve_icc_profile``: As the name says.
- ``thumbnail``: Resizes images to not exceed a bounding box.
- ``crop``: Crops an image to the given dimensions, also takes the PPOI
  (primary point of interest) information into account if provided.
- ``default``: The combination of ``autorotate``, ``process_jpeg``,
  ``process_gif``, ``process_png`` and ``preserve_icc_profile``.
  Additional default processors may be added in the future. It is
  recommended to use ``default`` instead of adding the processors
  one-by-one.

Processors can be specified either using their name alone, or if they
take arguments, using a tuple where the first entry is the processors'
name and the rest are positional arguments.

You can easily register your own processors or even override built-in
processors if you want to:

.. code-block:: python

    from imagefield.processing import register

    # You could also write a class with a __call__ method, but I really
    # like the simplicity of functions.

    @register
    def my_processor(get_image, ...):
        def processor(image, context):
            # read some information from the image...
            # or maybe modify it, but it's mostly recommended to modify
            # the image after calling get_image

            image = get_image(image, context)

            # modify the image, and return it...
            modified_image = ...
            # maybe modify the context...
            return modified_image
        return processor

The processor's name is taken directly from the registered object.

An example processor which converts images to grayscale would look as
follows:

.. code-block:: python

    from PIL import ImageOps
    from imagefield.processing import register

    @register
    def grayscale(get_image):
        def processor(image, context):
            image = get_image(image, context)
            return ImageOps.grayscale(image)
        return processor

Now include ``"grayscale"`` in the processing spec for the image where
you want to use it.


The processing context
======================

The ``context`` is a namespace with the following attributes (feel free
to add your own):

- ``processors``: The list of processors.
- ``name``: The name of the resulting image relative to its storages'
  root.
- ``extension``: The extension of the source and target.
- ``ppoi``: The primary point of interest as a list of two floats
  between 0 and 1.
- ``save_kwargs``: A dictionary of keyword arguments to pass to
  ``PIL.Image.save``.

The ``ppoi``, ``extension``, ``processors`` and ``name`` attributes
cannot be modified when running processors anymore. Under some
circumstances ``extension`` and ``name`` will not even be there.

If you want to modify the extension or file type, or create a different
processing pipeline depending on facts not known when configuring
settings you can use a callable instead of the list of processors. The
callable will receive the fieldfile and the context instance and must at
least set the context's ``processors`` attribute to something sensible.
Just as an example here's an image field which always returns JPEG
thumbnails:

.. code-block:: python

    from imagefield.processing import register

    @register
    def force_jpeg(get_image):
        def processor(image, context):
            image = get_image(image, context)
            context.save_kwargs["format"] = "JPEG"
            context.save_kwargs["quality"] = 90
            return image
        return processor

    def jpeg_processor_spec(fieldfile, context):
        context.extension = ".jpg"
        context.processors = [
            "force_jpeg",
            "autorotate",
            ("thumbnail", (200, 200)),
        ]

    class Model(...):
        image = ImageField(..., formats={"thumb": jpeg_processor_spec})

Of course you can also access the model instance through the field file
by way of its ``fieldfile.instance`` attribute and use those
informations to customize the pipeline.


Settings
========

django-imagefield supports a few settings to customize aspects of its behavior.

The default settings are as follows:

.. code-block:: python

    # Automatically generate and delete images when saving and deleting models.
    # Can either be a boolean or a list of "app.model.field" strings. It's
    # recommended to set this to False for some types of batch processing since
    # updating the images may slow things down a lot.
    IMAGEFIELD_AUTOGENERATE = True
    # The image field doesn't generally need a cache, but it's definitely
    # useful for admin thumbnails and the versatile image proxy. The timeout
    # can be configured here. By default, a random duration between 170 and
    # 190 days is used, so that the cache doesn't expire at the same time for
    # all images when running several server processes.
    IMAGEFIELD_CACHE_TIMEOUT = lambda: randint(170 * 86400, 190 * 86400)
    # See above.
    IMAGEFIELD_FORMATS = {}
    # Whether images should be deeply validated when saving them. It can be
    # useful to opt out of this for batch processing.
    IMAGEFIELD_VALIDATE_ON_SAVE = True
    # Errors while processing images lead to exceptions. Sometimes it's
    # desirable to only log those exceptions but fall back to the original
    # image. This setting let's you do that. Useful when you have many images
    # which haven't been verified by the image field.
    IMAGEFIELD_SILENTFAILURE = False
    # Add support for instance.image.crop.WxH and instance.image.thumbnail.WxH
    # An easier path to migrate away from django-versatileimagefield.
    IMAGEFIELD_VERSATILEIMAGEPROXY = False
    # How many folders and subfolders are created for processed images. The
    # default value is 1 for backwards compatibility, it's recommended to
    # increase the value to 2 or 3.
    IMAGEFIELD_BIN_DEPTH = 1


Development
===========

django-imagefield uses pre-commit_ to keep the code clean and formatted.

The easiest way to build the documentation and run the test suite is also by
using tox_:

.. code-block:: bash

    tox -e docs  # Open docs/build/html/index.html
    tox -l  # To show the available combinations of Python and Django


.. _documentation: https://django-imagefield.readthedocs.io/en/latest/
.. _Pillow: https://pillow.readthedocs.io/en/latest/
.. _tox: https://tox.readthedocs.io/
.. _pre-commit: https://pre-commit.com/
