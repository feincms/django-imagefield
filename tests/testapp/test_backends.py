"""Tests for backend abstraction layer."""

import io

import pyvips
from django.test import TestCase, override_settings
from PIL import Image as PILImage

from imagefield.backends import get_backend, reset_backend
from imagefield.processing_vips import VIPS_PROCESSORS


class BackendTestCase(TestCase):
    """Test backend selection and switching."""

    def tearDown(self):
        """Reset backend after each test."""
        reset_backend()
        super().tearDown()

    def test_default_backend_is_pillow(self):
        """Default backend should be Pillow."""
        backend = get_backend()
        self.assertEqual(backend.name, "pillow")

    def test_backend_singleton(self):
        """Backend should be a singleton."""
        backend1 = get_backend()
        backend2 = get_backend()
        self.assertIs(backend1, backend2)

    def test_reset_backend(self):
        """reset_backend should clear the singleton."""
        backend1 = get_backend()
        reset_backend()
        backend2 = get_backend()
        # Different instances after reset
        self.assertIsNot(backend1, backend2)
        # But both should be same type
        self.assertEqual(backend1.name, backend2.name)

    @override_settings(IMAGEFIELD_BACKEND="pillow")
    def test_explicit_pillow_backend(self):
        """Explicitly selecting Pillow backend should work."""
        reset_backend()
        backend = get_backend()
        self.assertEqual(backend.name, "pillow")

    @override_settings(IMAGEFIELD_BACKEND="PILLOW")
    def test_pillow_backend_case_insensitive(self):
        """Backend selection should be case-insensitive."""
        reset_backend()
        backend = get_backend()
        self.assertEqual(backend.name, "pillow")

    @override_settings(IMAGEFIELD_BACKEND="unknown")
    def test_unknown_backend_raises_error(self):
        """Unknown backend should raise ValueError."""
        reset_backend()
        with self.assertRaises(ValueError) as cm:
            get_backend()
        self.assertIn("Unknown backend", str(cm.exception))

    def test_pillow_backend_has_processors(self):
        """Pillow backend should provide processor registry."""
        backend = get_backend()
        processors = backend.processors
        self.assertIsInstance(processors, dict)
        self.assertIn("default", processors)
        self.assertIn("thumbnail", processors)
        self.assertIn("crop", processors)


class PillowBackendTestCase(TestCase):
    """Test Pillow backend functionality."""

    @override_settings(IMAGEFIELD_BACKEND="pillow")
    def setUp(self):
        """Set up Pillow backend for tests."""
        reset_backend()
        self.backend = get_backend()

    def tearDown(self):
        """Reset backend after each test."""
        reset_backend()
        super().tearDown()

    def test_backend_name(self):
        """Backend name should be 'pillow'."""
        self.assertEqual(self.backend.name, "pillow")

    def test_open_image(self):
        """Backend should open images."""
        # Create a test image
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with backend
        opened = self.backend.open(buf)
        self.assertIsInstance(opened, PILImage.Image)
        self.assertEqual(opened.size, (100, 100))

    def test_get_format(self):
        """Backend should detect image format."""
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        opened = self.backend.open(buf)
        format_name = self.backend.get_format(opened)
        self.assertEqual(format_name, "JPEG")

    def test_save_image(self):
        """Backend should save images."""
        img = PILImage.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()

        self.backend.save(img, buf, "JPEG", quality=90)
        self.assertGreater(len(buf.getvalue()), 0)

    def test_verify_supported(self):
        """Backend should verify valid images."""
        img = PILImage.new("RGB", (100, 100), color="green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        opened = self.backend.open(buf)
        # Should not raise
        self.assertTrue(self.backend.verify_supported(opened))


class VipsBackendTestCase(TestCase):
    """Test pyvips backend functionality."""

    @override_settings(IMAGEFIELD_BACKEND="vips")
    def setUp(self):
        """Set up vips backend for tests."""
        reset_backend()
        self.backend = get_backend()

    def tearDown(self):
        """Reset backend after each test."""
        reset_backend()
        super().tearDown()

    def test_backend_name(self):
        """Backend name should be 'vips'."""
        self.assertEqual(self.backend.name, "vips")

    def test_open_image_from_bytes(self):
        """Backend should open images from bytes."""

        # Create a test image with PIL and convert to bytes
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        data = buf.read()

        # Open with vips backend
        opened = self.backend.open(data)
        self.assertIsInstance(opened, pyvips.Image)
        self.assertEqual(opened.width, 100)
        self.assertEqual(opened.height, 100)

    def test_open_image_from_file_like(self):
        """Backend should open images from file-like objects."""
        # Create a test image
        img = PILImage.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with backend
        opened = self.backend.open(buf)
        self.assertIsInstance(opened, pyvips.Image)
        self.assertEqual(opened.width, 100)
        self.assertEqual(opened.height, 100)

    def test_get_format_jpeg(self):
        """Backend should detect JPEG format."""
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        opened = self.backend.open(buf)
        format_name = self.backend.get_format(opened)
        self.assertEqual(format_name, "JPEG")

    def test_get_format_png(self):
        """Backend should detect PNG format."""
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        opened = self.backend.open(buf)
        format_name = self.backend.get_format(opened)
        self.assertEqual(format_name, "PNG")

    def test_save_jpeg(self):
        """Backend should save JPEG images."""
        img = PILImage.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with vips and save
        vips_img = self.backend.open(buf)
        out_buf = io.BytesIO()
        self.backend.save(vips_img, out_buf, "JPEG", quality=90)
        self.assertGreater(len(out_buf.getvalue()), 0)

        # Verify it's a valid JPEG
        out_buf.seek(0)
        verified = PILImage.open(out_buf)
        self.assertEqual(verified.format, "JPEG")

    def test_save_png(self):
        """Backend should save PNG images."""
        img = PILImage.new("RGB", (100, 100), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        # Open with vips and save
        vips_img = self.backend.open(buf)
        out_buf = io.BytesIO()
        self.backend.save(vips_img, out_buf, "PNG")
        self.assertGreater(len(out_buf.getvalue()), 0)

        # Verify it's a valid PNG
        out_buf.seek(0)
        verified = PILImage.open(out_buf)
        self.assertEqual(verified.format, "PNG")

    def test_verify_supported(self):
        """Backend should verify valid images."""
        img = PILImage.new("RGB", (100, 100), color="green")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        opened = self.backend.open(buf)
        # Should not raise
        self.assertTrue(self.backend.verify_supported(opened))

    def test_has_processors(self):
        """Vips backend should provide processor registry."""
        processors = self.backend.processors
        self.assertIsInstance(processors, dict)
        self.assertIn("default", processors)
        self.assertIn("thumbnail", processors)
        self.assertIn("crop", processors)
        self.assertIn("autorotate", processors)

    def test_thumbnail_processor(self):
        """Thumbnail processor should resize images."""

        # Create a test image
        img = PILImage.new("RGB", (400, 300), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with vips
        vips_img = self.backend.open(buf)

        # Mock context
        class Context:
            ppoi = (0.5, 0.5)
            save_kwargs = {}

        context = Context()

        # Apply thumbnail processor
        thumbnail_fn = VIPS_PROCESSORS["thumbnail"]
        processor = thumbnail_fn(lambda img, ctx: img, (200, 150))
        result = processor(vips_img, context)

        # Should be resized to fit within 200x150
        self.assertLessEqual(result.width, 200)
        self.assertLessEqual(result.height, 150)

    def test_autorotate_processor(self):
        """Autorotate processor should handle EXIF orientation."""

        # Create a test image
        img = PILImage.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with vips
        vips_img = self.backend.open(buf)

        # Mock context
        class Context:
            save_kwargs = {}

        context = Context()

        # Apply autorotate processor (should not raise)
        autorotate_fn = VIPS_PROCESSORS["autorotate"]
        processor = autorotate_fn(lambda img, ctx: img)
        result = processor(vips_img, context)

        self.assertIsNotNone(result)

    def test_process_jpeg_processor(self):
        """process_jpeg should set quality and progressive."""

        # Create a test image
        img = PILImage.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        # Open with vips
        vips_img = self.backend.open(buf)

        # Mock context
        class Context:
            save_kwargs = {"format": "JPEG"}

        context = Context()

        # Apply process_jpeg processor
        process_jpeg_fn = VIPS_PROCESSORS["process_jpeg"]
        processor = process_jpeg_fn(lambda img, ctx: img)
        processor(vips_img, context)

        # Should set quality and progressive
        self.assertEqual(context.save_kwargs["quality"], 90)
        self.assertTrue(context.save_kwargs["progressive"])
