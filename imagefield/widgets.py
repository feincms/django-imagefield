import hashlib
import inspect

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.forms.boundfield import BoundField
from django.utils.html import format_html


def cache_key(name):
    return "imagefield-cache:%s" % hashlib.sha256(name.encode("utf-8")).hexdigest()


def cache_timeout():
    value = settings.IMAGEFIELD_CACHE_TIMEOUT
    return value() if callable(value) else value


class PPOIWidget(forms.HiddenInput):
    class Media:
        css = {"screen": ("imagefield/ppoi.css",)}
        js = ("imagefield/ppoi.js",)


class PreviewAndPPOIMixin:
    class Media:
        css = {"screen": ("imagefield/ppoi.css",)}
        js = ("imagefield/ppoi.js",)

    def render(self, name, value, attrs=None, **kwargs):
        attrs = attrs or {}
        # Can be dropped once we drop support for Django<2.1
        attrs.setdefault("accept", "image/*")
        widget = super().render(name, value, attrs=attrs, **kwargs)

        url = ""
        # name does not require a file, .url does
        if getattr(value, "name", "") and not isinstance(value, UploadedFile):
            processors = self._unbind_processors()
            context = value._process_context(processors)
            key = cache_key(context.name)
            url = value.storage.url(context.name)
            if not cache.get(key):
                try:
                    value.process(processors)
                    cache.set(key, 1, timeout=cache_timeout())
                except Exception:
                    # Avoid crashing here since it will not be possible to even
                    # replace corrupted images otherwise.
                    pass

        return format_html(
            '<div class="imagefield" data-ppoi-id="{ppoi}">'
            '<div class="imagefield-preview"{hidden}>'
            '<img class="imagefield-preview-image" src="{url}" alt=""/>'
            "</div>"
            '<div class="imagefield-widget">{widget}</div>'
            "</div>",
            widget=widget,
            # An empty but valid image source, replaced by ppoi.js when a file
            # is selected.
            url=url or "data:,",
            hidden="" if url else " hidden",
            ppoi=self._ppoi_id(),
        )

    def _ppoi_id(self):
        # Find our BoundField so that we may access the form instance to
        # finally determine the ID attribute of our PPOI field.
        frame = inspect.currentframe()
        while frame:
            boundfield = frame.f_locals.get("self")
            if isinstance(boundfield, BoundField):
                break
            frame = frame.f_back

        if frame is None:  # pragma: no cover
            # I have absolutely no idea why this would ever happen.
            return ""

        del frame

        try:
            return boundfield.form[boundfield.field.widget.ppoi_field].auto_id
        except (AttributeError, KeyError, TypeError):
            return ""

    def _unbind_processors(self):
        # Unwrap the original processors value. Callable processor specs are
        # converted into bound methods, but the machinery does not like the
        # additional ``self`` argument.
        return (
            self.processors.__func__ if callable(self.processors) else self.processors
        )


def with_preview_and_ppoi(widget, **attrs):
    return type(
        str("%sWithPreviewAndPPOI" % widget.__name__),
        (PreviewAndPPOIMixin, widget),
        dict(attrs, __module__="imagefield.widgets"),
    )
