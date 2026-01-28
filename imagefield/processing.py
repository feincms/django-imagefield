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
    register_pillow,
    thumbnail,
)


# Legacy aliases for backward compatibility
PROCESSORS = PILLOW_PROCESSORS
register = register_pillow  # Backward compatibility alias


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
