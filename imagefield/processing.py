"""Backward compatibility shim for processing module.

This module re-exports everything from processing_pillow for
backward compatibility with existing code.
"""

# Import everything from the new location
from imagefield.processing_pillow import (
    PILLOW_PROCESSORS,
    autorotate,
    build_handler,
    crop,
    default,
    preserve_icc_profile,
    process_gif,
    process_jpeg,
    process_png,
    register,
    thumbnail,
)


# Legacy alias for backward compatibility
PROCESSORS = PILLOW_PROCESSORS


__all__ = [
    "PILLOW_PROCESSORS",
    "PROCESSORS",
    "build_handler",
    "register",
    "autorotate",
    "crop",
    "default",
    "preserve_icc_profile",
    "process_gif",
    "process_jpeg",
    "process_png",
    "thumbnail",
]
