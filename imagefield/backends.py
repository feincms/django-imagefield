"""Backend manager for django-imagefield image processing.

Provides factory function to get the configured backend (Pillow or pyvips).
"""

from django.conf import settings


_backend_instance = None


def get_backend():
    """Get current backend singleton.

    Returns the configured backend based on settings.IMAGEFIELD_BACKEND.
    Defaults to Pillow backend for backward compatibility.

    Returns:
        ImageBackend: The active backend instance (PillowBackend or VipsBackend)

    Raises:
        ImportError: If pyvips backend is selected but pyvips is not installed
        ValueError: If unknown backend name is specified
    """
    global _backend_instance  # noqa: PLW0603
    if _backend_instance is None:
        backend_name = settings.IMAGEFIELD_BACKEND.lower()

        if backend_name == "pillow":
            from imagefield.backend_pillow import PillowBackend  # noqa: PLC0415

            _backend_instance = PillowBackend()
        elif backend_name == "vips":
            try:
                from imagefield.backend_vips import VipsBackend  # noqa: PLC0415

                _backend_instance = VipsBackend()
            except ImportError as e:
                raise ImportError(
                    "pyvips not installed. Install with: pip install pyvips"
                ) from e
        else:
            raise ValueError(
                f"Unknown backend: {backend_name}. Valid options are: 'pillow', 'vips'"
            )

    return _backend_instance


def reset_backend():
    """Reset backend singleton.

    Used for testing to allow switching backends within test suite.
    """
    global _backend_instance  # noqa: PLW0603
    _backend_instance = None


__all__ = ["get_backend", "reset_backend"]
