"""Platform registry — maps platform names to assembler classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assembler.base import PlatformAssembler

# Lazy imports to avoid circular dependencies at module level.


def _get_platforms() -> dict[str, type["PlatformAssembler"]]:
    from assembler.platforms.copilot import CopilotAssembler
    from assembler.platforms.claude import ClaudeAssembler
    return {
        "copilot": CopilotAssembler,
        "claude": ClaudeAssembler,
    }


# Expose as a lazy-evaluated dict-like for the CLI.
class _PlatformRegistry:
    """Lazy platform registry that imports assemblers on first access."""

    def __init__(self) -> None:
        self._loaded: dict[str, type["PlatformAssembler"]] | None = None

    def _ensure(self) -> dict[str, type["PlatformAssembler"]]:
        if self._loaded is None:
            self._loaded = _get_platforms()
        return self._loaded

    def __getitem__(self, key: str) -> type["PlatformAssembler"]:
        return self._ensure()[key]

    def __contains__(self, key: object) -> bool:
        return key in self._ensure()

    def keys(self):  # noqa: ANN201
        return self._ensure().keys()

    def values(self):  # noqa: ANN201
        return self._ensure().values()

    def items(self):  # noqa: ANN201
        return self._ensure().items()


PLATFORMS = _PlatformRegistry()
