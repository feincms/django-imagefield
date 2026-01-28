import hashlib
import io
import logging
import os
import warnings
from collections import namedtuple
from random import randint

from django.conf import settings
from django.core import checks
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import signals
from django.db.models.fields import files
from django.forms import ClearableFileInput
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from imagefield.backends import get_backend
from imagefield.processing import build_handler
from imagefield.websafe import websafe
from imagefield.widgets import (
    PPOIWidget,
    cache_key,
    cache_timeout,
    with_preview_and_ppoi,
)


DEFAULTS = {
    "IMAGEFIELD_AUTOGENERATE": True,
    "IMAGEFIELD_BACKEND": "pillow",
    "IMAGEFIELD_CACHE_TIMEOUT": lambda: randint(170 * 86400, 190 * 86400),
    "IMAGEFIELD_FORMATS": {},
    "IMAGEFIELD_VALIDATE_ON_SAVE": True,
    "IMAGEFIELD_SILENTFAILURE": False,
    "IMAGEFIELD_VERSATILEIMAGEPROXY": False,
    "IMAGEFIELD_BIN_DEPTH": 1,
}
for setting, default in DEFAULTS.items():
    if not hasattr(settings, setting):
        setattr(settings, setting, default)
if settings.IMAGEFIELD_BIN_DEPTH == 1:
    warnings.warn(
        "Set the IMAGEFIELD_BIN_DEPTH setting to 2 or 3 and rerun process_imagefields.",
        DeprecationWarning,
        stacklevel=1,
    )


class _SealableAttribute:
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return obj.__dict__[self.name]

    def __set__(self, obj, value):
        if obj._is_sealed:
            raise AttributeError(f"Attribute '{self.name}' is sealed")
        obj.__dict__[self.name] = value


class Context:
    ppoi = _SealableAttribute("ppoi")
    extension = _SealableAttribute("extension")
    processors = _SealableAttribute("processors")
    name = _SealableAttribute("name")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self._is_sealed = False

    def __repr__(self):
        # From https://docs.python.org/3/library/types.html#types.SimpleNamespace
        keys = sorted(self.__dict__)
        items = (f"{k}={self.__dict__[k]!r}" for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def seal(self):
        self._is_sealed = True


logger = logging.getLogger(__name__)
#: Imagefield instances
IMAGEFIELDS = []


def hashdigest(str):
    return hashlib.sha1(str.encode("utf-8")).hexdigest()


class VersatileImageProxy:
    def __init__(self, file, item):
        self.file = file
        self.items = [item]

    def __getitem__(self, key):
        if key.startswith("_"):
            raise KeyError(f"Invalid key '{key}' on VersatileImageProxy")
        self.items.append(key)
        return self

    def __getattr__(self, attribute):
        if attribute.startswith("_"):
            raise AttributeError(
                f"Invalid attribute '{attribute}' on VersatileImageProxy"
            )
        self.items.append(attribute)
        return self

    def __str__(self):
        processors = [
            "default",
            (self.items[0], tuple(map(int, self.items[1].split("x")))),
        ]
        if settings.IMAGEFIELD_VERSATILEIMAGEPROXY == "websafe":
            processors = websafe(processors)
        context = self.file._process_context(processors)
        key = cache_key(context.name)
        url = self.file.storage.url(context.name)
        if not cache.get(key):
            self.file.process(processors)
            cache.set(key, 1, timeout=cache_timeout())
        return url


_ProcessBase = namedtuple("_ProcessBase", "path basename")


class ImageFieldFile(files.ImageFieldFile):
    def __getattr__(self, item):
        # The "field" attribute is not there after unpickling. We cannot
        # help in this case so let's just raise an AttributeError and leave the
        # rest to the FileDescriptor
        if item == "field":
            raise AttributeError
        if not item.startswith("_") and item in self.field.formats:
            context = self._process_context(self.field.formats[item])
            url = self.storage.url(context.name) if context.name else ""
            setattr(self, item, url)
            return url
        elif settings.IMAGEFIELD_VERSATILEIMAGEPROXY and item in {"thumbnail", "crop"}:
            return VersatileImageProxy(self, item)
        raise AttributeError(f"Attribute '{item}' on '{self.field}' unknown")

    def _ppoi(self):
        if self.field.ppoi_field:
            try:
                return [
                    float(coord)
                    for coord in getattr(self.instance, self.field.ppoi_field).split(
                        "x"
                    )
                ]
            except Exception:
                pass
        return [0.5, 0.5]

    def _process_base(self, name):
        p1 = hashdigest(name)
        filename, _ = os.path.splitext(os.path.basename(name))
        bins = "/".join(
            p1[i : i + 3] for i in range(0, settings.IMAGEFIELD_BIN_DEPTH * 3, 3)
        )
        return _ProcessBase(f"__processed__/{bins}", f"{filename}-")

    def _process_context(self, processors):
        name = self.name or self.field._fallback
        context = Context(
            ppoi=self._ppoi(),
            save_kwargs={},
            extension=os.path.splitext(name)[1],
            processors=processors,
            name=name,
            source=name,
        )
        while callable(context.processors):
            context.processors(self, context)
        if context.name:
            base = self._process_base(context.name)
            spec = (
                "|".join(str(p) for p in context.processors) + "|" + str(context.ppoi)
            )
            p2 = hashdigest(spec)
            context.name = f"{base.path}/{base.basename}{p2[:12]}{context.extension}"
        context.seal()
        return context

    def process(self, spec, *, force=False):
        if isinstance(spec, list | tuple):
            processors = spec
            spec = "<ad hoc>"
        elif callable(spec):
            processors = spec  # Evaluated in _process_context
            spec = "<callable>"
        else:
            processors = self.field.formats[spec]

        context = self._process_context(processors)
        if not context.name:
            return

        logger.debug(
            'Processing image "%(image)s" as "%(key)s" with context %(context)s',
            {"image": self, "key": spec, "context": context},
        )

        already_exists = self.storage.exists(context.name)

        if not force and already_exists:
            return context.name

        try:
            buf = self._process(context=context)
        except Exception:
            logger.exception(
                'Exception while processing "%(context)s"', {"context": context}
            )
            if settings.IMAGEFIELD_SILENTFAILURE:
                return self.name
            raise

        if already_exists:
            self.storage.delete(context.name)
        self.storage.save(context.name, ContentFile(buf))

        logger.info('Saved "%(name)s" successfully', {"name": context.name})
        return context.name

    def _process(self, processors=None, context=None):
        assert bool(processors) != bool(context), "Pass exactly one, not both"

        if context is None:
            context = Context(
                ppoi=self._ppoi(),
                save_kwargs={},
                processors=processors,
                source=self.name,
            )
            context.seal()

        orig_name = self.name
        self.name = context.source
        try:
            backend = get_backend()
            with self.open("rb") as file:
                image = backend.open(file)
                context.save_kwargs.setdefault("format", backend.get_format(image))

                handler = build_handler(context.processors, registry=backend.processors)
                image = handler(image, context)

                with io.BytesIO() as buf:
                    # Extract format from save_kwargs to pass as positional arg
                    format_name = context.save_kwargs.pop("format")
                    backend.save(image, buf, format_name, **context.save_kwargs)
                    return buf.getvalue()

        finally:
            self.name = orig_name

    @property
    def _image(self):
        if self.name:
            backend = get_backend()
            original = io.BytesIO()
            if self.closed:
                self.open("rb")
            original.write(self.read())
            self.seek(0)
            original.seek(0)
            image = backend.open(original)
            backend.verify_supported(image)
            self.__dict__["_image"] = image

        return self.__dict__.get("_image")

    def save(self, name, content, save=True):  # noqa: FBT002
        if not settings.IMAGEFIELD_VALIDATE_ON_SAVE:
            super().save(name, content, save=True)
            return

        backend = get_backend()
        img = backend.open(content)
        backend.verify_supported(img)
        basename = os.path.splitext(name)[0]
        # Get proper file extension from backend
        format_name = backend.get_format(img)
        extension = backend.get_extension(format_name)
        name = f"{basename}.{extension}"

        name = self.field.generate_filename(self.instance, name)
        self.name = self.storage.save(name, content, max_length=self.field.max_length)
        setattr(self.instance, self.field.name, self.name)
        self._committed = True

        if save:
            self.instance.save()

    save.alters_data = True

    def delete(self, save=True):  # noqa: FBT002
        filename = self.name

        super().delete(save=save)

        self.field._clear_generated_files_for(self, filename)

    delete.alters_data = True


def raise_validation_error(field_name, exc):
    raise ValidationError(
        {
            field_name: _(
                "Error while handling image, maybe the file is corrupt"
                ' or the image format is unsupported. (Exception: "%s")'
            )
            % exc
        }
    )


class ImageField(models.ImageField):
    attr_class = ImageFieldFile

    def __init__(self, *args, **kwargs):
        self._auto_add_fields = kwargs.pop("auto_add_fields", False)
        self._fallback = kwargs.pop("fallback", "")
        self._formats = kwargs.pop("formats", {})
        self.ppoi_field = kwargs.pop("ppoi_field", None)
        super().__init__(*args, **kwargs)

    @cached_property
    def field_label(self):
        return (
            f"{self.model._meta.app_label}.{self.model._meta.model_name}.{self.name}"
        ).lower()

    @property
    def formats(self):
        return settings.IMAGEFIELD_FORMATS.get(self.field_label, self._formats)

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return (name, "django.db.models.ImageField", args, kwargs)

    def contribute_to_class(self, cls, name, **kwargs):
        if self._auto_add_fields:
            if self.width_field is None:
                self.width_field = "%s_width" % name
                models.PositiveIntegerField(
                    blank=True, null=True, editable=False
                ).contribute_to_class(cls, self.width_field)
            if self.height_field is None:
                self.height_field = "%s_height" % name
                models.PositiveIntegerField(
                    blank=True, null=True, editable=False
                ).contribute_to_class(cls, self.height_field)
            if self.ppoi_field is None:
                self.ppoi_field = "%s_ppoi" % name
                PPOIField().contribute_to_class(cls, self.ppoi_field)

        super().contribute_to_class(cls, name, **kwargs)

        if all((not cls._meta.abstract, not cls._meta.swapped)):
            IMAGEFIELDS.append(self)

    def formfield(self, **kwargs):
        kwargs["widget"] = with_preview_and_ppoi(
            kwargs.get("widget", ClearableFileInput),
            ppoi_field=self.ppoi_field,
            processors=self.formats.get(
                "preview", ["default", ("thumbnail", (300, 300))]
            ),
        )
        return super().formfield(**kwargs)

    def save_form_data(self, instance, data):
        try:
            super().save_form_data(instance, data)
        except Exception as exc:
            # The image was either of an unknown type or so corrupt Django
            # couldn't even begin to process it.
            super().save_form_data(instance, "")
            raise_validation_error(self.name, exc)

        if data is not None:
            f = getattr(instance, self.name)
            if f.name:
                try:
                    _read = f._image

                except Exception as exc:
                    super().save_form_data(instance, "")
                    raise_validation_error(self.name, exc)

            # Reset PPOI field if image field is cleared
            if not data and self.ppoi_field:
                setattr(instance, self.ppoi_field, "0.5x0.5")

    def _generate_files(self, instance, **kwargs):
        # Set by the process_imagefields management command
        if getattr(instance, "_skip_generate_files", False):
            return

        f = getattr(instance, self.name)

        if f.name:
            for spec in f.field.formats:
                f.process(spec)

    def _clear_generated_files(self, instance, **kwargs):
        self._clear_generated_files_for(getattr(instance, self.name), None)

    def _clear_generated_files_for(self, fieldfile, filename):
        filename = fieldfile.name if filename is None else filename

        if not filename:
            return

        key = (
            "imagefield-admin-thumb:%s"
            % hashlib.sha256(filename.encode("utf-8")).hexdigest()
        )
        cache.delete(key)

        base = fieldfile._process_base(filename)

        try:
            folders, files = fieldfile.storage.listdir(base.path)
        except FileNotFoundError:
            # Fine!
            return

        for file in files:
            if file.startswith(base.basename):
                fieldfile.storage.delete(os.path.join(base.path, file))

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        if not self.width_field or not self.height_field:
            errors.append(
                checks.Error(
                    "ImageField without width_field/height_field is slow!",
                    hint="auto_add_fields=True automatically adds the fields.",
                    obj=self,
                    id="imagefield.E001",
                )
            )
        if not self.ppoi_field:
            errors.append(
                checks.Info(
                    "ImageField without ppoi_field.",
                    hint="auto_add_fields=True automatically adds the field.",
                    obj=self,
                    id="imagefield.I001",
                )
            )
        if self.null is True:
            errors.append(
                checks.Info(
                    "ImageField shouldn't use null=True.",
                    hint=(
                        "String-based fields shouldn't use null=True, one way"
                        " to represent the absence of a value is enough."
                    ),
                    obj=self,
                    id="imagefield.I002",
                )
            )
        return errors


def _register_signal_handlers(sender, **kwargs):
    for field in IMAGEFIELDS:
        if issubclass(sender, field.model):
            autogenerate = settings.IMAGEFIELD_AUTOGENERATE
            if (
                autogenerate is True
                or autogenerate
                and field.field_label in autogenerate
            ):
                signals.post_save.connect(field._generate_files, sender=sender)


signals.class_prepared.connect(_register_signal_handlers)


class PPOIField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", "0.5x0.5")
        kwargs.setdefault("max_length", 20)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return (name, "django.db.models.CharField", args, kwargs)

    def formfield(self, **kwargs):
        kwargs["widget"] = PPOIWidget
        return super().formfield(**kwargs)
