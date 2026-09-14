"""Platform registry — maps platform names to assembler classes.

OpenCode is intentionally excluded: it was written against the old
skills/prompts/instructions canonical layout and has not been ported to the
new workflow-driven DSL. Its source is kept at
``platforms/_opencode_quarantined.py`` (not imported by anything) as a
reference for a future port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assembler.base import PlatformAssembler

# Lazy imports to avoid circular dependencies at module level.

UNSUPPORTED_PLATFORMS = {"opencode"}


def _get_platforms() -> dict[str, type["PlatformAssembler"]]:
    from assembler.platforms.aider import AiderAssembler
    from assembler.platforms.copilot import CopilotAssembler
    return {
        "copilot": CopilotAssembler,
        "aider": AiderAssembler,
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
        if key in UNSUPPORTED_PLATFORMS:
            raise KeyError(
                f"Platform '{key}' is not supported. It predates the current "
                "canonical DSL and has not been ported. See "
                "platforms/_opencode_quarantined.py for the old implementation."
            )
        return self._ensure()[key]

    def __contains__(self, key: object) -> bool:
        if key in UNSUPPORTED_PLATFORMS:
            return False
        return key in self._ensure()

    def keys(self):  # noqa: ANN201
        return self._ensure().keys()

    def values(self):  # noqa: ANN201
        return self._ensure().values()

    def items(self):  # noqa: ANN201
        return self._ensure().items()


PLATFORMS = _PlatformRegistry()

