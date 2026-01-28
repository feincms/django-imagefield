"""Abstract base class for image processing backends."""

from abc import ABC, abstractmethod
from typing import BinaryIO


# Standard format name to file extension mapping
FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "GIF": "gif",
    "TIFF": "tif",
    "TIF": "tif",
    "WEBP": "webp",
    "BMP": "bmp",
    "ICO": "ico",
    "PDF": "pdf",
    "SVG": "svg",
    "HEIF": "heif",
    "HEIC": "heic",
    "AVIF": "avif",
    "JP2": "jp2",
    "J2K": "j2k",
}


class ImageBackend(ABC):
    """Minimal backend interface for image I/O and validation.

    Backends provide core infrastructure for opening, saving, and validating images.
    Processors work directly with native image objects (PIL.Image or pyvips.Image).
    Each backend provides its own processor registry.
    """

    @abstractmethod
    def open(self, file: str | BinaryIO | bytes):
        """Open image and return native image object.

        Args:
            file: File path, file-like object, or bytes

        Returns:
            Native image object (PIL.Image.Image for Pillow, pyvips.Image for vips)

        Raises:
            IOError: If image cannot be opened or is invalid
        """

    @abstractmethod
    def save(self, image, fp: BinaryIO, format: str, **kwargs) -> None:
        """Save native image object to file-like object.

        Args:
            image: Native image object (PIL.Image.Image or pyvips.Image)
            fp: File-like object to write to
            format: Image format (JPEG, PNG, GIF, etc.)
            **kwargs: Format-specific save options (quality, optimize, etc.)

        Raises:
            IOError: If image cannot be saved
        """

    @abstractmethod
    def verify_supported(self, image) -> bool:
        """Verify image is valid and can be processed.

        Args:
            image: Native image object

        Returns:
            True if image is valid

        Raises:
            ValueError: If image is broken or unsupported
        """

    @abstractmethod
    def get_format(self, image) -> str:
        """Get standard format name from image.

        Args:
            image: Native image object

        Returns:
            Standard format name (JPEG, PNG, GIF, TIFF, WEBP, etc.)
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier.

        Returns:
            Backend name: 'pillow' or 'vips'
        """

    @property
    @abstractmethod
    def processors(self) -> dict:
        """Return the processor registry dict for this backend.

        Returns:
            Dictionary mapping processor names to processor functions
        """

    def get_extension(self, format_name: str) -> str:
        """Get file extension for a format name.

        Args:
            format_name: Standard format name (JPEG, PNG, etc.)

        Returns:
            File extension without dot (jpg, png, etc.)
        """
        return FORMAT_EXTENSIONS.get(format_name, format_name.lower())
