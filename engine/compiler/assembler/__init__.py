"""Assembler package — generates platform-specific agent setups from canonical definitions."""

__version__ = "2.0.0"

from assembler.base import PlatformAssembler
from assembler.platforms import PLATFORMS
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter

__all__ = ["PLATFORMS", "CanonicalRegistry", "FileWriter", "PlatformAssembler", "__version__"]
