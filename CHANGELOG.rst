.. _changelog:

Change log
==========

Next version
~~~~~~~~~~~~


0.23 (unreleased, experimental)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Experimental:** Added optional pyvips backend for faster, more memory-efficient
  image processing. Install with ``pip install django-imagefield[vips]`` and
  configure with ``IMAGEFIELD_BACKEND = "vips"``. The vips backend provides:

  - Significantly faster image processing (often 2-5x faster)
  - More memory-efficient handling of large images
  - Streaming from disk when possible instead of loading into memory
  - Smart color space handling (preserves grayscale JPEGs for smaller file sizes)
  - Automatic ICC profile preservation

- Added pluggable backend system with ``ImageBackend`` base class. Both Pillow
  and vips backends implement the same interface, allowing seamless switching.
- Centralized image format-to-extension mapping (``FORMAT_EXTENSIONS``) and
  cropping calculations (``calculate_crop_box``) to reduce code duplication.
- Renamed ``register`` to ``register_pillow`` for consistency. The old name
  remains available as a compatibility alias.
- Fixed bug where ``format`` parameter was passed twice to ``backend.save()``.
- Improved JPEG processing to preserve grayscale images (vips backend only).
  Pillow backend maintains conservative "convert all to RGB" approach.
- Fixed PNG processing to only convert palette/indexed images to RGBA, not all
  RGB images.
- Updated test suite with comprehensive vips backend integration tests (85 tests
  total with 97% coverage).
- Added documentation for backend behavior differences in README.


0.22 (2025-01-22)
~~~~~~~~~~~~~~~~~

- **Important:** Changed the image field to no longer automatically clean up
  processed images when deleting the model instance or when changing the image
  field itself. This behavior made it hard to reuse image field values when
  copying model data. Instead, processed images are only deleted when the image
  file itself is deleted (e.g. using ``object.image.delete()``).
- Rewrote ``process_imagefields`` to use the multiprocessing module, which
  hopefully improves compatibility on macOS.
- Introduced a ``--no-parallel`` argument to ``process_imagefields``.
- Added Django 5.2a1.
- Dropped the Python 2 fallback from the code. We don't support Python 2
  anymore.


0.21 (2024-12-09)
~~~~~~~~~~~~~~~~~

- Documented the ``preview`` spec used in the preview widget.
- Started masquerading our custom model fields as default Django image and char
  fields. This is expected to create migrations if you're already using the
  fields.


0.20 (2024-11-18)
~~~~~~~~~~~~~~~~~

- Added support for setting ``IMAGEFIELD_AUTOGENERATE = False``. Previously,
  only ``True`` or an iterable were supported.
- Dropped compatibility with Python 3.8 and 3.9.
- Added Python 3.13.
- Excluded Pillow 11.0.0 from the list of supported Pillow versions, see
  `#8535 <https://github.com/python-pillow/Pillow/issues/8530>`__.


0.19 (2024-08-03)
~~~~~~~~~~~~~~~~~

- Updated the pre-commit configuration, switched to biomejs.
- Started using a process pool to process images in parallel in
  ``process_imagefields``.
- Added Django 5.1rc1 to the CI, removed 4.1 (3.2 is still there).
- Attached signal handlers to model subclasses as well, so that proxy models
  are supported too.


0.18 (2023-12-07)
~~~~~~~~~~~~~~~~~

- Added Python 3.12, Django 5.0.
- Added an easy way to reduce the possibility of filename collisions.
  Unfortunately, the hashing scheme used by default has bad uniqueness
  properties. It's recommended to add ``IMAGEFIELD_BIN_DEPTH = 2`` to your
  settings and regenerate all processed images, for example using
  ``process_imagefields --all``. The default may change in the future. For now
  nothing changes, so there's no compatibility concerns.


0.17 (2023-09-25)
~~~~~~~~~~~~~~~~~

- Added a force-WEBP spec.
- Added Django 4.1 and 4.2, Python 3.11.
- Dropped Django 4.0 from the CI (3.2 is still in there).
- Switched to hatch and ruff.
- Added globbing support to the ``process_imagefields`` management command.


`0.16`_ (2022-05-04)
~~~~~~~~~~~~~~~~~~~~

.. _0.16: https://github.com/matthiask/django-imagefield/compare/0.15...0.16

- Raised the minimum Pillow version to 9.0.
- Avoided a deprecation warning by using the ``PIL.Image.Resampling`` enum.


`0.15`_ (2022-03-07)
~~~~~~~~~~~~~~~~~~~~

.. _0.15: https://github.com/matthiask/django-imagefield/compare/0.14...0.15

- Dropped support for Python < 3.8, Django < 3.2.
- Added a simplistic workaround for ``IOError`` exceptions which still plague
  Pillow when saving some JPEG files.


`0.14`_ (2021-12-23)
~~~~~~~~~~~~~~~~~~~~

.. _0.14: https://github.com/matthiask/django-imagefield/compare/0.13...0.14

- Renamed the main branch to ``main``.
- Reformatted the frontend code using prettier and checked it using ESLint.
- Fixed a crash which happened when the PPOI field contained an invalid value.
- Added saving files in their original format to ``verified``. Previously, some
  images were accepted because they can be loaded but they could not be saved
  later.
- Added Python 3.10, Django 4.0 to the CI.
- Dropped support for Python 2.7, Django 1.11.
- Added a warning when using ``ImageField(null=True)``.
- Started using pre-commit.


`0.13`_ (2021-02-03)
~~~~~~~~~~~~~~~~~~~~

- Started using ``ImageOps.exif_transpose`` introduced in Pillow 6.0 to
  autorotate images.
- Allowed overriding the preview image for the form field by adding a
  ``"preview"`` spec to the field.
- Added descriptions when raising ``AttributeError`` exceptions.
- Fixed the alignment of file uploads when imagefields with PPOI widgets
  are used within a fieldbox in the admin interface.
- Do not accept keys or attributes starting with underscores in the
  versatile image proxy.
- Disallowed image format names starting with an underscore.
- Added ``IMAGEFIELD_VALIDATE_ON_SAVE`` to skip image validation when
  using model-level methods. Only use this when you are absolutely 100%
  sure that the images you are adding can be processed by Pillow.
- Switched from Travis CI to GitHub actions.


`0.12`_ (2020-07-24)
~~~~~~~~~~~~~~~~~~~~

- **BACKWARDS INCOMPATIBLE**: Consolidated cache key generation in the
  versatile image proxy and the admin widget code. Already cached values
  will be checked again. Also, the cache timeout has been changed from
  infinite (in case of the versatile image proxy) and 30 days (in case
  of the admin widget) to a random value between 170 and 190 days. This
  can be overridden by specifying the timeout as
  ``IMAGEFIELD_CACHE_TIMEOUT``. The setting may either be a value or a
  callable.
- Fixed a pickle/unpickle crash.
- Closed image files in more places to avoid resource warnings.
- Dropped Django 1.8 from the build matrix. Supporting it in the
  testsuite became annoying.
- Added verification of images even when not using forms.
- Ensured that configured fallbacks are also processed by
  ``process_imagefields``.
- Silenced more warnings when running the testsuite and generally
  improved test coverage.
- Avoided setting the image field files' value too early when using
  fallbacks.
- Added a new ``process_png`` processor which converts PNGs using
  palettes to RGBA. This avoids ugly artefacts when resizing images.


`0.11`_ (2020-01-27)
~~~~~~~~~~~~~~~~~~~~

- Changed the fallback facility to a keyword argument to the
  ``ImageField`` instance.
- Changed processing context creation to assign the ``name`` field
  earlier.


`0.10`_ (2020-01-24)
~~~~~~~~~~~~~~~~~~~~

- Added an experimental fallback facility for optional image fields.
- Allowed processor specs to return another processor spec in turn. This
  allows layering processor specs.
- Changed the image field to set image file's extensions depending on
  their image type. For example, a GIF uploaded as ``example.png`` will
  automatically be saved as ``example.gif``.
- Improved test coverage a bit.


`0.9`_ (2020-01-22)
~~~~~~~~~~~~~~~~~~~

- Fixed crashes because of image fields with ``None`` values.
- Fixed a case where an unsupported image was not detected early enough.
- Added a ``IMAGEFIELD_SILENTFAILURE`` setting for silent failure when
  processing images crashes. The default value of this setting is
  obviously ``False``. This is mostly useful when adding
  ``django-imagefield`` to a project which already has images (which may
  not be processible by Pillow).
- Fixed the image verification to accept CMYK images again.
- Added Django 3.0 to the test matrix.
- Removed Python 3.4 from the test matrix.
- Ensure that ``icc_profile`` isn't passed if it is falsy. The WebP
  encoder didn't like ``icc_profile=None``.
- Stopped including image fields of swapped models in ``IMAGEFIELDS``.
- Replaced ``ugettext*`` with ``gettext*``.
- Added an experimental websafe processor spec.


`0.8`_ (2019-06-21)
~~~~~~~~~~~~~~~~~~~

- **BACKWARDS INCOMPATIBLE**: Changed processing to pass additional
  processors' arguments as positional arguments instead of as a single
  list. This change only affects custom processors, no changes are
  necessary for users of the library, except if for example you passed
  arguments to processors such as ``default``, ``autorotate`` etc.
- Fixed a test to assume less about the error message for corrupt
  images.
- Localize the corrupt image validation errors.
- Stopped calling the storage's ``delete()`` method for non-existing
  images.
- Made the field resilient against NULL values from the database.


`0.7`_ (2018-10-18)
~~~~~~~~~~~~~~~~~~~

- Made error reporting in ``process_imagefields`` include more info.
- Made image field validation catch errors while determining the image
  dimension too.
- Fixed a problem where older versions of Django didn't allow specifying
  the chunk size for iterating over querysets.
- Modified django-imagefield's internals to allow changing the type and
  extension of generated images by way of dynamically specifying the
  processing pipeline.
- Changed the API of the ``get_image`` callable in processors to only
  return the image without the context (since the context is mutable and
  available already).


`0.6`_ (2018-09-13)
~~~~~~~~~~~~~~~~~~~

- Fixed a crash where unpickling image fields would fail.
- Changed ``process_imagefields`` to skip exclude model instances with
  an empty image field.
- Changed the ``thumbnail`` processor to not upscale images.
- Made ``process_imagefields`` not load the whole queryset at once to
  avoid massive slowdowns while determining the width and height of
  images (if those fields aren't filled in yet).
- Added housekeeping options to ``process_imagefields``. The only method
  implemented right now is ``--housekeep blank-on-failure`` which
  empties image fields where processing fails.
- Changed ``process_imagefields`` to process items in a deterministic
  order.
- Clarified the processors spec documentation a bit and added an example
  how to write a processor of your own.


`0.5`_ (2018-08-15)
~~~~~~~~~~~~~~~~~~~

- Dropped support for using image fields without associated height and
  width fields, because it is almost (?) always a really bad idea
  performance-wise.
- Fixed a bug where processed image names on Python 2 were different
  than those generated using Python 3. This bug affects only
  installations still using Python 2. Rerun ``./manage.py
  process_imagefields --all`` after upgrading.


`0.4`_ (2018-08-13)
~~~~~~~~~~~~~~~~~~~

- Added compatibility with Django 1.8 for prehistoric projects.
- Polished tests and docs a bit.


`0.3`_ (2018-05-29)
~~~~~~~~~~~~~~~~~~~

- **BACKWARDS INCOMPATIBLE**: Changed the filename generation method to
  preserve the filename part of the original file for SEO purposes etc.
  You should run ``./manage.py process_imagefields --all``, and
  optionally empty the ``__processed__`` folder before doing that if you
  do not want to keep old images around.
- Improved progress reporting in ``process_imagefields``.
- Added a call to ``instance.save()`` in ``process_imagefields`` so that
  width and height fields are saved (if any).
- Added ``accept="image/*"`` attribute to the file upload widget.
- Replaced the full image in the admin widget with an ad-hoc thumbnail.
- Fixed a bug where blank imagefields would not work correctly in the
  administration interface.
- Switched the preferred quote to ``"`` and started using `black
  <https://pypi.org/project/black/>`_ to automatically format Python
  code.


`0.2`_ (2018-03-28)
~~~~~~~~~~~~~~~~~~~

- Rename management command to ``process_imagefields``, and add
  ``--all`` option to process all imagefields.
- Fixed a bug where not all image fields from base classes were picked
  up for processing by ``process_imagefields``.
- Added the ``IMAGEFIELD_AUTOGENERATE`` setting, which can be set to a
  list of image fields (in ``app.model.field`` notation, lowercased) to
  only activate automatic processing of images upon model creation and
  update for a few specific fields, or to ``False`` to disable this
  functionality for all fields.
- Added system checks which warn when ``width_field`` and
  ``height_field`` are not used.
- Changed ``process_imagefields`` to process image fields in
  alphabetic order. Also, made cosmetic changes to the progress output.
- Added a test which verifies that generating processed image URLs is
  not slowed down by potentially slow storages (e.g. cloud storage)
- Fixed the PPOI JavaScript to not crash when some imagefields have no
  corresponding PPOI input.


`0.1`_ (2018-03-27)
~~~~~~~~~~~~~~~~~~~

- First release that should be fit for public consumption.


.. _0.1: https://github.com/matthiask/django-imagefield/commit/013b9a810fa6
.. _0.2: https://github.com/matthiask/django-imagefield/compare/0.1...0.2
.. _0.3: https://github.com/matthiask/django-imagefield/compare/0.2...0.3
.. _0.4: https://github.com/matthiask/django-imagefield/compare/0.3...0.4
.. _0.5: https://github.com/matthiask/django-imagefield/compare/0.4...0.5
.. _0.6: https://github.com/matthiask/django-imagefield/compare/0.5...0.6
.. _0.7: https://github.com/matthiask/django-imagefield/compare/0.6...0.7
.. _0.8: https://github.com/matthiask/django-imagefield/compare/0.7...0.8
.. _0.9: https://github.com/matthiask/django-imagefield/compare/0.8...0.9
.. _0.10: https://github.com/matthiask/django-imagefield/compare/0.9...0.10
.. _0.11: https://github.com/matthiask/django-imagefield/compare/0.10...0.11
.. _0.12: https://github.com/matthiask/django-imagefield/compare/0.11...0.12
.. _0.13: https://github.com/matthiask/django-imagefield/compare/0.12...0.13
