import io
import os
import pickle
import re
import sys
import time
from unittest import expectedFailure, skipIf
from unittest.mock import PropertyMock, patch

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models
from django.test import Client
from django.test.utils import isolate_apps, override_settings
from django.urls import reverse
from PIL import Image

from imagefield.fields import (
    IMAGEFIELDS,
    Context,
    ImageField,
    ImageFieldFile,
    _SealableAttribute,
)
from testapp.models import (
    Model,
    ModelWithOptional,
    NullableImage,
    ProxyModel,
    SlowStorageImage,
    WebsafeImage,
    slow_storage,
)
from testapp.utils import BaseTest, contents, openimage


class Test(BaseTest):
    def login(self):
        self.user = User.objects.create_superuser("admin", "admin@test.ch", "blabla")
        client = Client()
        client.force_login(self.user)
        return client

    def test_model(self):
        """Behavior of model with ImageField(blank=False)"""
        m = Model.objects.create(image="python-logo.png")

        client = self.login()
        response = client.get(reverse("admin:testapp_model_change", args=(m.id,)))

        self.assertContains(response, 'value="0.5x0.5"')
        self.assertContains(response, 'src="/static/imagefield/ppoi.js"')
        self.assertContains(response, '<div class="imagefield" data-ppoi-id="id_ppoi">')

        self.assertContains(
            response,
            '<img class="imagefield-preview-image"'
            ' src="/media/__processed__/beb/python-logo-6e3df744dc82.png"'
            ' alt=""/>',
        )

    def test_proxy_model(self):
        """Proxy models should also automatically process images"""

        ProxyModel.objects.create(image="python-logo.png")
        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.png", "python-logo-e6a99ea713c8.png"],
        )

    def test_no_ppoi_admin(self):
        client = self.login()
        m = NullableImage.objects.create(image="python-logo.png")
        response = client.get(
            reverse("admin:testapp_nullableimage_change", args=(m.id,))
        )
        self.assertContains(response, 'data-ppoi-id=""')

    def test_model_with_optional(self):
        """Behavior of model with ImageField(blank=True)"""
        client = self.login()
        response = client.get("/admin/testapp/modelwithoptional/add/")
        self.assertContains(response, 'src="/static/imagefield/ppoi.js"')

        m = ModelWithOptional.objects.create()
        response = client.get(
            reverse("admin:testapp_modelwithoptional_change", args=(m.id,))
        )
        self.assertContains(
            response,
            '<input type="file" name="image" id="id_image" accept="image/*"/>',
            html=True,
        )

    def test_upload(self):
        """Adding and updating images creates thumbs"""
        client = self.login()
        self.assertEqual(contents("__processed__"), [])

        with openimage("python-logo.png") as f:
            response = client.post(
                "/admin/testapp/model/add/", {"image": f, "ppoi": "0.5x0.5"}
            )
            self.assertRedirects(response, "/admin/testapp/model/")

        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.png", "python-logo-e6a99ea713c8.png"],
        )

        m = Model.objects.get()
        self.assertTrue(m.image.name)
        self.assertEqual(
            m.image.thumb, "/media/__processed__/02a/python-logo-24f8702383e7.png"
        )
        with self.assertRaises(AttributeError) as cm:
            _read = m.image.not_exists

        self.assertEqual(
            "Attribute 'not_exists' on 'testapp.Model.image' unknown", str(cm.exception)
        )

        response = client.post(
            reverse("admin:testapp_model_change", args=(m.pk,)),
            {"image": "", "ppoi": "0x0"},
        )
        self.assertRedirects(response, "/admin/testapp/model/")
        self.assertEqual(
            contents("__processed__"),
            [
                "python-logo-096bade32f42.png",
                "python-logo-24f8702383e7.png",
                "python-logo-2f5189af7eb3.png",
                "python-logo-e6a99ea713c8.png",
            ],
        )

    def test_autorotate(self):
        """Images are automatically rotated according to EXIF data"""
        field = Model._meta.get_field("image")

        for image in ["Landscape_3.jpg", "Landscape_6.jpg", "Landscape_8.jpg"]:
            m = Model(image="exif-orientation-examples/%s" % image, ppoi="0.5x0.5")
            path = os.path.join(settings.MEDIA_ROOT, m.image.process("desktop"))
            with Image.open(path) as im:
                self.assertEqual(im.size, (300, 225))

            self.assertEqual(len(contents("__processed__")), 1)
            field._clear_generated_files(m)
            self.assertEqual(contents("__processed__"), [])

    def test_cmyk(self):
        """JPEG in CMYK is converted to RGB"""
        field = Model._meta.get_field("image")

        m = Model(image="cmyk.jpg", ppoi="0.5x0.5")
        path = os.path.join(settings.MEDIA_ROOT, m.image.process("desktop"))
        with Image.open(path) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.mode, "RGB")

        self.assertEqual(contents("__processed__"), ["cmyk-e6a99ea713c8.jpg"])
        field._clear_generated_files(m)
        self.assertEqual(contents("__processed__"), [])

    def test_indexed_png(self):
        """PNG with P(alette) is converted to RGBA"""
        field = Model._meta.get_field("image")

        m = Model(image="python-logo-indexed.png", ppoi="0.5x0.5")
        path = os.path.join(settings.MEDIA_ROOT, m.image.process("desktop"))
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGBA")

        self.assertEqual(
            contents("__processed__"), ["python-logo-indexed-e6a99ea713c8.png"]
        )
        field._clear_generated_files(m)
        self.assertEqual(contents("__processed__"), [])

    def test_empty(self):
        """Model without an imagefield does not crash when accessing props"""
        m = Model()
        self.assertEqual(m.image.name, "")
        self.assertEqual(m.image.desktop, "")

    def test_ppoi_reset(self):
        """PPOI field reverts to default when image field is cleared"""
        client = self.login()
        with openimage("python-logo.png") as f:
            response = client.post(
                "/admin/testapp/modelwithoptional/add/",
                {"image": f, "image_ppoi": "0.25x0.25"},
            )
            self.assertRedirects(response, "/admin/testapp/modelwithoptional/")

        m = ModelWithOptional.objects.get()
        self.assertEqual(m.image._ppoi(), [0.25, 0.25])

        response = client.post(
            reverse("admin:testapp_modelwithoptional_change", args=(m.pk,)),
            {"image-clear": "1", "image_ppoi": "0.25x0.25"},
        )

        self.assertRedirects(response, "/admin/testapp/modelwithoptional/")

        m = ModelWithOptional.objects.get()
        self.assertEqual(m.image.name, "")
        self.assertEqual(m.image_ppoi, "0.5x0.5")

    def test_broken(self):
        """Broken images are rejected early"""
        with self.assertRaises((IOError, OSError)):
            Model.objects.create(image="broken.png")

        client = self.login()
        with openimage("broken.png") as f:
            response = client.post(
                "/admin/testapp/model/add/", {"image": f, "ppoi": "0.5x0.5"}
            )

        self.assertContains(
            response,
            "Upload a valid image. The file you uploaded was either"
            " not an image or a corrupted image.",
        )

        with openimage("python-logo.jpg") as f:
            response = client.post(
                "/admin/testapp/model/add/", {"image": f, "ppoi": "0.5x0.5"}
            )
            self.assertRedirects(response, "/admin/testapp/model/")

            f.seek(0)
            with io.BytesIO(f.read()[:-1000]) as buf:
                buf.name = "python-logo.jpg"
                response = client.post(
                    "/admin/testapp/model/add/", {"image": buf, "ppoi": "0.5x0.5"}
                )
                self.assertTrue(
                    re.search(
                        r"image file is truncated \([0-9]+ bytes not processed\)",
                        response.content.decode("utf-8"),
                    )
                )

    def test_no_validate_on_save(self):
        """Broken images are rejected early"""
        with override_settings(IMAGEFIELD_VALIDATE_ON_SAVE=False):
            m = Model(image="broken.png")
            m._skip_generate_files = True
            m.save()  # Doesn't crash

    def test_no_validate_on_unchanged(self):
        """
        Saving a form without changing the image should not run
        extended validation (not call _image).
        """
        client = self.login()
        m = Model.objects.create(image="python-logo.png")

        with patch.object(
            ImageFieldFile, "_image", new_callable=PropertyMock
        ) as mock_image:
            response = client.post(
                reverse("admin:testapp_model_change", args=(m.pk,)),
                {"ppoi": "0.3x0.3"},
            )
            self.assertRedirects(response, "/admin/testapp/model/")
            self.assertFalse(mock_image.called, "_image should not be accessed")

    def test_no_validate_on_clear(self):
        """
        Clearing an optional image field should not run
        extended validation (not call _image).
        """
        client = self.login()
        m = ModelWithOptional.objects.create(image="python-logo.png")

        with patch.object(
            ImageFieldFile, "_image", new_callable=PropertyMock
        ) as mock_image:
            response = client.post(
                reverse("admin:testapp_modelwithoptional_change", args=(m.pk,)),
                {"image-clear": "1", "image_ppoi": "0.5x0.5"},
            )
            self.assertRedirects(response, "/admin/testapp/modelwithoptional/")
            self.assertFalse(mock_image.called, "_image should not be accessed")
            m.refresh_from_db()
            self.assertFalse(m.image)

    def test_silent_failure(self):
        Model.objects.create(image="python-logo.jpg")
        Model.objects.update(image="broken.png")  # DB-only update
        m = Model.objects.get()

        with self.assertRaisesRegex(Exception, "cannot identify image file"):
            m.image.process("desktop")

        with override_settings(IMAGEFIELD_SILENTFAILURE=True):
            self.assertEqual(m.image.process("desktop"), "broken.png")

    def test_cmyk_validation(self):
        """
        Test that the image verification can handle CMYK images.
        """
        client = self.login()
        with openimage("preview_LoxdQ3U.jpg") as f:
            response = client.post(
                "/admin/testapp/model/add/", {"image": f, "ppoi": "0.5x0.5"}
            )

        self.assertRedirects(response, "/admin/testapp/model/")

    def test_adhoc(self):
        """Ad-hoc processing pipelines may be built and executed"""
        m = Model.objects.create(image="python-logo.jpg")
        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.jpg", "python-logo-e6a99ea713c8.jpg"],
        )
        self.assertEqual(
            m.image.process([("thumbnail", (20, 20))]),
            "__processed__/d00/python-logo-43feb031c1be.jpg",
        )

        # Same result when using a callable as processor spec:
        def spec(fieldfile, context):
            context.processors = [("thumbnail", (20, 20))]

        self.assertEqual(
            m.image.process(spec), "__processed__/d00/python-logo-43feb031c1be.jpg"
        )
        self.assertEqual(
            contents("__processed__"),
            [
                "python-logo-24f8702383e7.jpg",
                "python-logo-43feb031c1be.jpg",
                "python-logo-e6a99ea713c8.jpg",
            ],
        )

    def test_adhoc_lowlevel(self):
        """Low-level processing pipelines; no saving of generated images"""
        m = Model.objects.create(image="python-logo.jpg")
        m.image._process(processors=[("thumbnail", (20, 20))])
        # New thumb is not saved; still only "desktop" and "thumbnail" images
        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.jpg", "python-logo-e6a99ea713c8.jpg"],
        )

    @skipIf(sys.version_info[0] < 3, "time.monotonic only with Python>=3.3")
    def test_fast(self):
        """Loading models and generating URLs is not slowed by storages"""
        # Generate thumbs, cache width/height in DB fields
        SlowStorageImage.objects.create(image="python-logo.jpg")

        slow_storage.slow = True

        start = time.monotonic()
        m = SlowStorageImage.objects.get()
        self.assertEqual(
            m.image.thumb, "/media/__processed__/d00/python-logo-10c070f1761f.jpg"
        )
        duration = time.monotonic() - start
        # No opens, no saves
        self.assertTrue(duration < 0.1)

    def test_imagefields(self):
        self.assertEqual(
            {f.field_label for f in IMAGEFIELDS},
            {
                "testapp.model.image",
                "testapp.slowstorageimage.image",
                "testapp.modelwithoptional.image",
                "testapp.nullableimage.image",
                "testapp.websafeimage.image",
            },
        )

    def test_versatileimageproxy(self):
        m = Model.objects.create(image="python-logo.jpg")
        thumb = m.image.thumbnail["20x20"]
        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.jpg", "python-logo-e6a99ea713c8.jpg"],
        )
        self.assertEqual(thumb.items, ["thumbnail", "20x20"])
        self.assertEqual(
            f"{thumb}", "/media/__processed__/d00/python-logo-f26eb6811b04.jpg"
        )
        self.assertEqual(
            contents("__processed__"),
            [
                "python-logo-24f8702383e7.jpg",
                "python-logo-e6a99ea713c8.jpg",
                "python-logo-f26eb6811b04.jpg",
            ],
        )

    def test_nullableimage(self):
        m = NullableImage.objects.create()
        m.image.process("thumb")
        self.assertEqual(contents("__processed__"), [])

    def test_already_websafe(self):
        # Same as above!
        WebsafeImage.objects.create(image="python-logo.jpg")
        self.assertEqual(contents("__processed__"), ["python-logo-24f8702383e7.jpg"])

    def test_websafe_force_jpeg(self):
        WebsafeImage.objects.create(image="python-logo.tiff")
        self.assertEqual(contents("__processed__"), ["python-logo-2ebc6e32bcdb.jpg"])

    def test_websafe_gif(self):
        WebsafeImage.objects.create(image="python-logo.gif")
        self.assertEqual(contents("__processed__"), ["python-logo-24f8702383e7.gif"])

    def test_callable_preview_spec(self):
        """Callable ``preview`` specs work"""
        client = self.login()
        m = WebsafeImage.objects.create(image="python-logo.gif")
        response = client.get(
            reverse("admin:testapp_websafeimage_change", args=(m.id,))
        )
        self.assertContains(response, 'value="0.5x0.5"')  # Does not crash
        # print(response, response.content.decode("utf-8"))

    @override_settings(IMAGEFIELD_VERSATILEIMAGEPROXY="websafe")
    def test_websafe_versatileimageproxy(self):
        m = WebsafeImage.objects.create(image="python-logo.tiff")
        self.assertEqual(
            "{}".format(m.image.crop["300x300"]),
            "/media/__processed__/639/python-logo-2ebc6e32bcdb.jpg",
        )

    def test_force_does_overwrite(self):
        m = Model(image="python-logo.jpg")
        m.image.process("thumb")
        self.assertEqual(contents("__processed__"), ["python-logo-24f8702383e7.jpg"])
        m.image.process("thumb", force=True)
        self.assertEqual(contents("__processed__"), ["python-logo-24f8702383e7.jpg"])

    def test_completely_bogus(self):
        client = self.login()
        buf = io.BytesIO(b"anything")
        buf.name = "bogus.jpg"
        response = client.post(
            "/admin/testapp/model/add/", {"image": buf, "ppoi": "0.5x0.5"}
        )
        self.assertContains(response, "Upload a valid image.")

    def test_wrong_extension(self):
        client = self.login()
        self.assertEqual(contents("__processed__"), [])

        with openimage("python-logo.png") as f, io.BytesIO() as buf:
            buf.write(f.read())
            buf.seek(0)
            buf.name = "python-logo.gif"
            response = client.post(
                "/admin/testapp/model/add/", {"image": buf, "ppoi": "0.5x0.5"}
            )
            self.assertRedirects(response, "/admin/testapp/model/")

        self.assertEqual(
            contents("__processed__"),
            ["python-logo-24f8702383e7.png", "python-logo-e6a99ea713c8.png"],
        )

    def test_pickle(self):
        """Pickling and unpickling shouldn't crash or produce max recursion errors"""
        m1 = WebsafeImage.objects.create(image="python-logo.jpg")
        m2 = pickle.loads(pickle.dumps(m1))
        self.assertEqual(m1.image, m2.image)

    @expectedFailure
    def test_deferred_imagefields(self):
        """Deferring imagefields shouldn't leave old processed images on the disk"""
        WebsafeImage.objects.create(image="python-logo.jpg")
        self.assertEqual(contents("__processed__"), ["python-logo-24f8702383e7.jpg"])

        m1 = WebsafeImage.objects.defer("image").get()
        m1.image = "cmyk.jpg"
        m1.save()
        self.assertEqual(contents("__processed__"), ["cmyk-24f8702383e7.jpg"])
        # ["cmyk-24f8702383e7.jpg", "python-logo-24f8702383e7.jpg"],

    def test_context(self):
        self.assertTrue(isinstance(Context.ppoi, _SealableAttribute))
        self.assertEqual(f"{Context()}", "Context(_is_sealed=False)")

    def test_image_property(self):
        m = Model()
        self.assertIsNone(m.image._image)

    @override_settings(IMAGEFIELD_AUTOGENERATE=set())
    @isolate_apps("testapp")
    def test_no_autogenerate(self):
        class ModelWithOptional(models.Model):
            image = ImageField(
                auto_add_fields=True,
                formats={"thumb": ["default", ("crop", (300, 300))]},
            )

            class Meta:
                app_label = "testapp"

        ModelWithOptional.objects.create(image="python-logo.jpg")
        self.assertEqual(contents("__processed__"), [])

    def test_bogus_without_formats(self):
        with override_settings(IMAGEFIELD_FORMATS={"testapp.model.image": {}}):
            m = Model(image="python-logo.tiff")
            with self.assertRaisesRegex(Exception, "cannot identify image file"):
                m.image.save("stuff.jpg", io.BytesIO(b"anything"), save=True)

        with openimage("python-logo.tiff") as f:
            m = Model()
            m.image.save("stuff.png", ContentFile(f.read()), save=True)

    def test_empty_image(self):
        m = Model()
        with self.assertRaisesRegex(Exception, "cannot identify image file"):
            m.image.save("stuff.png", ContentFile(b""), save=True)

    def test_invalid_ppoi(self):
        m = Model(image="python-logo.png")

        m.ppoi = "abcdef"
        self.assertEqual(m.image._ppoi(), [0.5, 0.5])

        m.ppoi = None
        self.assertEqual(m.image._ppoi(), [0.5, 0.5])

    def test_deletion_cleanup(self):
        """Deleting the image file also deletes processed images"""
        with openimage("python-logo.png") as f:
            m = Model()
            m.image.save("stuff.png", ContentFile(f.read()), save=True)

        self.assertEqual(
            contents("__processed__"),
            ["stuff-24f8702383e7.png", "stuff-e6a99ea713c8.png"],
        )

        m.image.delete()
        self.assertEqual(contents("__processed__"), [])

    def test_custom_widget_with_preview(self):
        """Custom widget can be used while keeping preview functionality"""
        # When specifying a custom widget in formfield(),
        # pass the class not an instance
        field = Model._meta.get_field("image")
        form_field = field.formfield(widget=forms.FileInput)

        # The widget should be wrapped with preview functionality
        self.assertIn("WithPreviewAndPPOI", form_field.widget.__class__.__name__)
        self.assertTrue(hasattr(form_field.widget, "ppoi_field"))

    def test_custom_widget_without_preview(self):
        """Override form field entirely to disable preview functionality"""

        class CustomForm(forms.ModelForm):
            # Override the field entirely to use a plain ImageField
            image = forms.ImageField(widget=forms.FileInput())

            class Meta:
                model = Model
                fields = ["image", "ppoi"]

        form = CustomForm()
        # This should be a plain FileInput without preview functionality
        self.assertIsInstance(form.fields["image"].widget, forms.FileInput)
        self.assertNotIn(
            "WithPreviewAndPPOI", form.fields["image"].widget.__class__.__name__
        )

    def test_custom_widget_via_meta_widgets(self):
        """Using Meta.widgets with a custom widget class"""

        class CustomForm(forms.ModelForm):
            class Meta:
                model = Model
                fields = ["image", "ppoi"]
                # Django's ModelForm will instantiate the widget class,
                # but formfield() expects a class for with_preview_and_ppoi
                widgets = {
                    "image": forms.FileInput,
                }

        form = CustomForm()
        # This should work - the widget gets wrapped with preview functionality
        self.assertIn(
            "WithPreviewAndPPOI", form.fields["image"].widget.__class__.__name__
        )
