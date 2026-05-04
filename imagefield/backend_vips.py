"""pyvips backend for django-imagefield."""

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
            # Try to get a file path to avoid reading into memory
            if hasattr(file, "name") and isinstance(file.name, str):
                try:
                    # Django File objects and similar have .name with file path
                    return pyvips.Image.new_from_file(file.name)
                except (pyvips.Error, OSError):
                    # Fall back to buffer if path doesn't work
                    pass

            # File-like object without usable path - read into bytes
            data = file.read()
            # Rewind file for potential subsequent operations
            if hasattr(file, "seek"):
                file.seek(0)
            return pyvips.Image.new_from_buffer(data, "")
        else:
            # Assume bytes
            return pyvips.Image.new_from_buffer(file, "")

    def _vips_save_args(self, format: str, kwargs: dict) -> tuple[str, dict]:
        """Return (suffix, vips_kwargs) for the given PIL-style format and kwargs."""
        suffix = f".{self.get_extension(format.upper())}"
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
        return suffix, vips_kwargs

    def save_to_bytes(self, image, format: str, **kwargs) -> bytes:
        suffix, vips_kwargs = self._vips_save_args(format, kwargs)
        return image.write_to_buffer(suffix, **vips_kwargs)

    def save(self, image, fp: BinaryIO, format: str, **kwargs) -> None:
        fp.write(self.save_to_bytes(image, format, **kwargs))

    def verify_supported(self, image) -> bool:
        thumb = image.thumbnail_image(10, height=10).colourspace("srgb")
        thumb.write_to_buffer(".jpg", Q=90)
        thumb.write_to_buffer(".png")
        thumb.write_to_buffer(".tif")
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
