import traceback
from time import sleep

from django.core.files import storage
from django.db import models
from django.utils.translation import gettext_lazy as _

from imagefield.fields import ImageField, PPOIField
from imagefield.websafe import websafe


class AbstractModel(models.Model):
    image = ImageField(
        _("image"),
        upload_to="images",
        width_field="width",
        height_field="height",
        ppoi_field="ppoi",
        formats={
            "thumb": ["default", ("crop", (300, 300))],
            "desktop": ["default", ("thumbnail", (300, 225))],
        },
        # Should have no effect, but not hurt either:
        auto_add_fields=True,
    )
    width = models.PositiveIntegerField(
        _("image width"), blank=True, null=True, editable=False
    )
    height = models.PositiveIntegerField(
        _("image height"), blank=True, null=True, editable=False
    )
    ppoi = PPOIField(_("primary point of interest"))

    class Meta:
        abstract = True


class Model(AbstractModel):
    pass


class ProxyModel(Model):
    class Meta:
        proxy = True


class ModelWithOptional(models.Model):
    image = ImageField(_("image"), upload_to="images", blank=True, auto_add_fields=True)


class SlowStorage(storage.FileSystemStorage):
    slow = False

    def _open(self, name, mode="rb"):
        if self.slow:
            sleep(1)
            traceback.print_stack()
        return super()._open(name, mode=mode)

    def _save(self, name, content):
        if self.slow:
            sleep(1)
            traceback.print_stack()
        return super()._save(name, content)


slow_storage = SlowStorage()


class SlowStorageImage(models.Model):
    image = ImageField(
        _("image"),
        upload_to="images",
        auto_add_fields=True,
        storage=slow_storage,
        formats={"thumb": ["default", ("crop", (20, 20))]},
    )


class NullableImage(models.Model):
    image = ImageField(
        _("image"),
        upload_to="images",
        blank=True,
        null=True,
        formats={"thumb": ["default", ("crop", (20, 20))]},
        auto_add_fields=False,
        width_field="image_width",
        height_field="image_height",
    )
    image_width = models.PositiveIntegerField(blank=True, null=True, editable=False)
    image_height = models.PositiveIntegerField(blank=True, null=True, editable=False)


class WebsafeImage(models.Model):
    image = ImageField(
        _("image"),
        upload_to="images",
        auto_add_fields=True,
        fallback="python-logo.tiff",
        formats={"preview": websafe(["default", ("crop", (300, 300))])},
    )
