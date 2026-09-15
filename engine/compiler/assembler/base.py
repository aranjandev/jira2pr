"""PlatformAssembler — abstract base class for platform-specific assemblers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from assembler.registry import CanonicalRegistry
from assembler.templates import substitute_vars
from assembler.writer import FileWriter


class PlatformAssembler(ABC):
    """Contract that every platform adapter implements."""

    name: str  # "copilot", "opencode", etc.

    # Template variables for {{VAR}} substitution in workflows / instructions.
    # Subclasses must define this.
    TEMPLATE_VARS: dict[str, str] = {}

    @property 
    def engine_root(self) -> Path:
        """Return the root directory of the engine."""
        return Path(__file__).resolve().parent

    @property 
    def runtime_root(self) -> Path:
        """Return the root directory of the runtime."""
        return self.engine_root / "runtime"

    @abstractmethod
    def assemble(self, registry: CanonicalRegistry, writer: FileWriter) -> None:
        """Generate all platform-specific files via *writer*."""

    def substitute(self, text: str) -> str:
        """Replace ``{{VAR}}`` placeholders using this platform's variables."""
        return substitute_vars(text, self.TEMPLATE_VARS)
