"""pyvips backend for django-imagefield."""

import io
from typing import BinaryIO

import pyvips

from imagefield.backend_base import ImageBackend


class VipsBackend(ImageBackend):
    """pyvips backend implementation.

    Provides faster and more memory-efficient image processing using libvips.
    Optional backend that requires pyvips to be installed.
    """

    def open(self, file: str | BinaryIO | bytes):
        """Open image using pyvips.

        Args:
            file: File path, file-like object, or bytes

        Returns:
            pyvips.Image object

        Raises:
            IOError: If image cannot be opened or is invalid
        """
        if isinstance(file, str):
            return pyvips.Image.new_from_file(file)
        elif hasattr(file, "read"):
            # File-like object - read into bytes
            data = file.read()
            return pyvips.Image.new_from_buffer(data, "")
        else:
            # Assume bytes
            return pyvips.Image.new_from_buffer(file, "")

    def save(self, image, fp: BinaryIO, format: str, **kwargs) -> None:
        """Save vips image to file-like object.

        Maps PIL-style save parameters to pyvips equivalents.

        Args:
            image: pyvips.Image object
            fp: File-like object to write to
            format: Image format (JPEG, PNG, GIF, etc.)
            **kwargs: Format-specific save options

        Raises:
            IOError: If image cannot be saved
        """
        # Map format to vips suffix
        # vips uses file extensions to determine output format
        extension = self.get_extension(format.upper())
        suffix = f".{extension}"

        # Map PIL-style kwargs to vips-style kwargs
        vips_kwargs = {}

        if format.upper() == "JPEG":
            if "quality" in kwargs:
                vips_kwargs["Q"] = kwargs["quality"]
            if kwargs.get("progressive"):
                vips_kwargs["interlace"] = True
            if kwargs.get("optimize"):
                vips_kwargs["optimize_coding"] = True
        elif format.upper() == "PNG":
            if kwargs.get("optimize"):
                vips_kwargs["compression"] = 9
        elif format.upper() == "WEBP":
            if "quality" in kwargs:
                vips_kwargs["Q"] = kwargs["quality"]
            if kwargs.get("lossless"):
                vips_kwargs["lossless"] = True

        # Write to buffer
        data = image.write_to_buffer(suffix, **vips_kwargs)
        fp.write(data)

    def verify_supported(self, image) -> bool:
        """Verify image is valid by testing operations.

        Tests the image by creating a small thumbnail and attempting
        to save in multiple formats.

        Args:
            image: pyvips.Image object

        Returns:
            True if image is valid

        Raises:
            ValueError: If image is broken or unsupported
        """
        # Test basic operations to ensure image is valid
        thumb = image.thumbnail_image(10, height=10)
        thumb = thumb.colourspace("srgb")

        # Try saving in different formats
        with io.BytesIO() as target:
            # Use original format if available
            data = thumb.write_to_buffer(".jpg", Q=90)
            target.write(data)

        with io.BytesIO() as target:
            data = thumb.write_to_buffer(".png")
            target.write(data)

        with io.BytesIO() as target:
            data = thumb.write_to_buffer(".tif")
            target.write(data)

        return True

    def get_format(self, image) -> str:
        """Get format from vips image.

        Args:
            image: pyvips.Image object

        Returns:
            Standard format name (JPEG, PNG, GIF, etc.)
        """
        # Try to get vips-loader metadata
        try:
            loader = image.get("vips-loader")
            format_map = {
                "jpegload": "JPEG",
                "jpegload_buffer": "JPEG",
                "pngload": "PNG",
                "pngload_buffer": "PNG",
                "gifload": "GIF",
                "gifload_buffer": "GIF",
                "tiffload": "TIFF",
                "tiffload_buffer": "TIFF",
                "webpload": "WEBP",
                "webpload_buffer": "WEBP",
                "heifload": "HEIF",
                "heifload_buffer": "HEIF",
                "svgload": "SVG",
                "svgload_buffer": "SVG",
                "pdfload": "PDF",
                "pdfload_buffer": "PDF",
                "jp2kload": "JP2",
                "jp2kload_buffer": "JP2",
            }
            return format_map.get(loader, "JPEG")
        except pyvips.Error:
            # If vips-loader is not set, default to JPEG
            return "JPEG"

    @property
    def name(self) -> str:
        """Backend identifier."""
        return "vips"

    @property
    def processors(self) -> dict:
        """Return vips processor registry."""
        from imagefield.processing_vips import VIPS_PROCESSORS  # noqa: PLC0415

        return VIPS_PROCESSORS
