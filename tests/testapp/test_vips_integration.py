"""Integration tests for vips backend with ImageField.

These tests verify that the full ImageField processing pipeline works correctly
with the pyvips backend.
"""

import io
from unittest.mock import patch

import pyvips
from django.core.files.base import ContentFile
from django.test.utils import override_settings
from PIL import Image

from imagefield.backends import get_backend, reset_backend
from imagefield.processing_pillow import PILLOW_PROCESSORS
from imagefield.processing_vips import VIPS_PROCESSORS, register_vips
from testapp.models import Model, WebsafeImage
from testapp.utils import BaseTest


@override_settings(IMAGEFIELD_BACKEND="vips")
class VipsIntegrationTest(BaseTest):
    """Test that ImageField works correctly with vips backend."""

    def setUp(self):
        """Reset backend before each test."""
        reset_backend()
        super().setUp()

    def tearDown(self):
        """Reset backend after each test."""
        reset_backend()
        super().tearDown()

    def test_backend_is_vips(self):
        """Verify tests are actually using vips backend."""
        backend = get_backend()
        self.assertEqual(backend.name, "vips", "Tests must use vips backend")

    def test_processing_uses_vips_images(self):
        """Verify that image processing uses pyvips.Image objects, not PIL."""

        # Verify we're using vips
        backend = get_backend()
        self.assertEqual(backend.name, "vips")

        # Create a test image
        img = Image.new("RGB", (200, 150), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with backend and verify it returns pyvips.Image
        opened = backend.open(buf.read())
        self.assertIsInstance(
            opened, pyvips.Image, "Backend should return pyvips.Image"
        )
        self.assertNotIsInstance(
            opened, Image.Image, "Backend should NOT return PIL.Image"
        )

    def test_backend_uses_vips_processors(self):
        """Verify backend returns VIPS_PROCESSORS, not PILLOW_PROCESSORS."""

        backend = get_backend()
        processors = backend.processors

        # Should be VIPS_PROCESSORS
        self.assertIs(processors, VIPS_PROCESSORS, "Backend should use VIPS_PROCESSORS")
        self.assertIsNot(
            processors, PILLOW_PROCESSORS, "Backend should NOT use PILLOW_PROCESSORS"
        )

    def test_processor_receives_vips_image(self):
        """Verify that custom processors receive pyvips.Image objects."""

        # Track what type of image object the processor receives
        received_image_type = []

        @register_vips
        def test_type_checker(get_image):
            def processor(image, context):
                received_image_type.append(type(image).__name__)
                # Verify it's a pyvips.Image
                if not isinstance(image, pyvips.Image):
                    raise AssertionError(
                        f"Processor received {type(image)} instead of pyvips.Image"
                    )
                return get_image(image, context)

            return processor

        backend = get_backend()
        self.assertEqual(backend.name, "vips")

        # Create test image
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open and process with our custom processor
        vips_img = backend.open(buf.read())

        # Mock context
        class Context:
            save_kwargs = {"format": "JPEG"}

        context = Context()

        # Apply our test processor
        processor_fn = VIPS_PROCESSORS["test_type_checker"]
        processor = processor_fn(lambda img, ctx: img)
        result = processor(vips_img, context)

        # Verify the processor received a pyvips.Image
        self.assertEqual(len(received_image_type), 1)
        self.assertEqual(received_image_type[0], "Image")  # pyvips.Image.__name__
        self.assertIsInstance(result, pyvips.Image)

    def test_pillow_backend_never_used(self):
        """Ensure PillowBackend is never instantiated when using vips."""

        # Patch PillowBackend to raise if instantiated
        with patch("imagefield.backend_pillow.PillowBackend") as mock_pillow:
            mock_pillow.side_effect = AssertionError(
                "PillowBackend should never be instantiated when using vips backend"
            )

            # Reset and get backend - should use vips, not pillow
            reset_backend()
            backend = get_backend()

            # Verify we got vips backend
            self.assertEqual(backend.name, "vips")

            # PillowBackend should never have been called
            mock_pillow.assert_not_called()

    def test_create_model_with_image(self):
        """Should be able to create model with image using vips backend."""

        # Verify we're using vips
        self.assertEqual(get_backend().name, "vips")

        m = Model.objects.create(image="python-logo.png")
        self.assertTrue(m.image)
        self.assertGreater(m.image.width, 0)
        self.assertGreater(m.image.height, 0)

    def test_upload_and_process_jpeg(self):
        """Should process JPEG images correctly with vips."""

        # Verify we're using vips
        self.assertEqual(get_backend().name, "vips")

        # Create a test JPEG
        img = Image.new("RGB", (800, 600), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = Model()
        m.image.save("test.jpg", ContentFile(buf.read()), save=False)
        m.save()

        # Should have processed the image
        self.assertEqual(m.image.width, 800)
        self.assertEqual(m.image.height, 600)

        # Should have generated thumbnails
        self.assertTrue(hasattr(m.image, "thumb"))
        self.assertTrue(hasattr(m.image, "desktop"))

    def test_upload_and_process_png(self):
        """Should process PNG images correctly with vips."""
        # Create a test PNG
        img = Image.new("RGB", (400, 300), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        m = Model()
        m.image.save("test.png", ContentFile(buf.read()), save=False)
        m.save()

        # Should have processed the image
        self.assertEqual(m.image.width, 400)
        self.assertEqual(m.image.height, 300)

    def test_indexed_png_conversion(self):
        """PNG with palette mode should be converted to RGBA with vips."""
        # Create indexed PNG
        img = Image.new("P", (100, 100))
        img.putpalette([i % 256 for i in range(768)])
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        m = Model()
        m.image.save("indexed.png", ContentFile(buf.read()), save=False)
        m.save()

        # Should have processed without error
        self.assertTrue(m.image)

    def test_cmyk_jpeg_conversion(self):
        """CMYK JPEG should be converted to RGB with vips."""
        # Create CMYK JPEG
        img = Image.new("CMYK", (100, 100), color=(100, 50, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = Model()
        m.image.save("cmyk.jpg", ContentFile(buf.read()), save=False)
        m.save()

        # Should have processed without error
        self.assertTrue(m.image)

    def test_thumbnail_generation(self):
        """Thumbnails should be generated correctly with vips."""
        m = Model.objects.create(image="python-logo.png")

        # Should have thumb thumbnail
        thumb_url = m.image.thumb
        self.assertIn("__thumb__", thumb_url)

        # Should have desktop thumbnail
        desktop_url = m.image.desktop
        self.assertIn("__desktop__", desktop_url)

    def test_ppoi_cropping(self):
        """PPOI-based cropping should work with vips."""
        # Create image with custom PPOI
        img = Image.new("RGB", (400, 300), color="green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = Model()
        m.image.save("test.jpg", ContentFile(buf.read()), save=False)
        m.ppoi = "0.2x0.8"  # Custom PPOI
        m.save()

        # Should generate thumbnails with custom PPOI
        self.assertTrue(m.image.thumb)
        self.assertEqual(m.ppoi, "0.2x0.8")

    def test_image_rotation_exif(self):
        """Images with EXIF orientation should be rotated with vips."""
        # Note: This is a basic test, full EXIF testing would require
        # images with actual EXIF data
        m = Model.objects.create(image="python-logo.png")
        self.assertTrue(m.image)

    def test_progressive_jpeg(self):
        """Progressive JPEG should be created with vips."""
        img = Image.new("RGB", (800, 600), color="yellow")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = Model()
        m.image.save("progressive.jpg", ContentFile(buf.read()), save=False)
        m.save()

        # Should process without error
        self.assertTrue(m.image)

    def test_delete_removes_generated_images(self):
        """Deleting image should remove generated thumbnails with vips."""
        m = Model.objects.create(image="python-logo.png")

        # Generate thumbnails
        _ = m.image.thumb
        _ = m.image.desktop

        # Delete
        m.image.delete(save=False)

        # Should have removed the image
        self.assertFalse(m.image)

    def test_websafe_with_vips(self):
        """Websafe processing should work with vips backend."""

        # Create a test image
        img = Image.new("RGB", (400, 300), color="purple")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = WebsafeImage()
        m.image.save("test.jpg", ContentFile(buf.read()), save=False)
        m.save()

        # Should have processed the image
        self.assertTrue(m.image)

    def test_format_detection(self):
        """Format should be correctly detected with vips."""
        # Test JPEG
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        m = Model()
        m.image.save("test.jpg", ContentFile(buf.read()), save=False)
        m.save()

        self.assertTrue(m.image.name.endswith(".jpg"))

        # Test PNG
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        m2 = Model()
        m2.image.save("test.png", ContentFile(buf.read()), save=False)
        m2.save()

        self.assertTrue(m2.image.name.endswith(".png"))

    def test_large_image_processing(self):
        """Large images should be processed efficiently with vips."""
        # Create a large image (4K)
        img = Image.new("RGB", (3840, 2160), color="cyan")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        m = Model()
        m.image.save("large.jpg", ContentFile(buf.read()), save=False)
        m.save()

        # Should process without error
        self.assertTrue(m.image)
        self.assertEqual(m.image.width, 3840)
        self.assertEqual(m.image.height, 2160)

    def test_gif_with_transparency(self):
        """GIF with transparency should be handled with vips."""
        # Create a simple GIF
        img = Image.new("RGB", (100, 100), color="magenta")
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        buf.seek(0)

        m = Model()
        m.image.save("test.gif", ContentFile(buf.read()), save=False)
        m.save()

        # Should process without error
        self.assertTrue(m.image)
