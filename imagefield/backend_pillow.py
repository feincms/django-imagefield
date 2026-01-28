"""Pillow backend for django-imagefield."""

import io
from typing import BinaryIO

from PIL import Image, ImageFile

from imagefield.backend_base import ImageBackend


class PillowBackend(ImageBackend):
    """Pillow (PIL) backend implementation.

    Default backend that provides 100% backward compatibility with existing code.
    """

    def open(self, file: str | BinaryIO | bytes):
        """Open image using PIL.Image.open.

        Args:
            file: File path, file-like object, or bytes

        Returns:
            PIL.Image.Image object

        Raises:
            IOError: If image cannot be opened or is invalid
        """
        return Image.open(file)

    def save(self, image, fp: BinaryIO, format: str, **kwargs) -> None:
        """Save PIL image to file-like object with MAXBLOCK workaround.

        Implements workaround for large images by temporarily increasing
        MAXBLOCK if initial save fails. See:
        https://github.com/python-imaging/Pillow/issues/148

        Args:
            image: PIL.Image.Image object
            fp: File-like object to write to
            format: Image format (JPEG, PNG, GIF, etc.)
            **kwargs: Format-specific save options (quality, optimize, etc.)

        Raises:
            IOError: If image cannot be saved
        """
        original = ImageFile.MAXBLOCK

        try:
            try:
                image.save(fp, format=format, **kwargs)
            except OSError:
                # Increase MAXBLOCK temporarily and try again.
                # See https://github.com/python-imaging/Pillow/issues/148
                ImageFile.MAXBLOCK *= 16
                image.save(fp, format=format, **kwargs)
        finally:
            ImageFile.MAXBLOCK = original

    def verify_supported(self, image) -> bool:
        """Verify image is valid by exercising PIL machinery.

        Tests the image by resizing to small thumbnail and attempting
        to save in multiple formats to ensure it's not broken.

        Args:
            image: PIL.Image.Image object

        Returns:
            True if image is valid

        Raises:
            ValueError: If image is broken or unsupported
        """
        # Anything which exercises the machinery so that we may
        # find out whether the image works at all (or not)
        thumb = image.resize((10, 10)).convert("RGB")
        with io.BytesIO() as target:
            self.save(thumb, target, format=image.format or "JPEG")
            self.save(thumb, target, format="PNG")
            self.save(thumb, target, format="TIFF")
        return True

    def get_format(self, image) -> str:
        """Get format from PIL image.

        Args:
            image: PIL.Image.Image object

        Returns:
            Standard format name (JPEG, PNG, GIF, etc.)
        """
        return image.format or "JPEG"

    @property
    def name(self) -> str:
        """Backend identifier."""
        return "pillow"

    @property
    def processors(self) -> dict:
        """Return Pillow processor registry."""
        from imagefield.processing_pillow import PILLOW_PROCESSORS  # noqa: PLC0415

        return PILLOW_PROCESSORS
