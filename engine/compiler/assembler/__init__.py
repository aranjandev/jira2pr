"""Assembler package — generates platform-specific agent setups from canonical definitions."""

__version__ = "2.0.0"

from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from assembler.base import PlatformAssembler
from assembler.platforms import PLATFORMS

__all__ = ["CanonicalRegistry", "FileWriter", "PlatformAssembler", "PLATFORMS", "__version__"]
