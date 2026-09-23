"""Resolves a capability id + params into a subprocess argv, per its binding
in `.jira2pr/capabilities.yaml` (see canonical/capabilities.yaml).
"""

from __future__ import annotations

import re

from assembler.model import (
    CapabilitySpec,
    CAPABILITY_HANDLER_SCRIPT_MAP,
    CAPABILITY_ARGS_MAP,
)

_PLACEHOLDER_RE = re.compile(r"^<(.+)>$")


class CapabilityError(Exception):
    """Raised for unbound capabilities or a params mismatch against the DSL."""


def resolve(cap: CapabilitySpec, repo_root: str, params: dict[str, str]) -> list[str]:
    """Return an argv (``["python3", "<script>", ...]``) for a script-backed capability.

    Every ``<placeholder>`` in the capability's args template must have a
    matching entry in *params*; unknown params are rejected too, so a caller
    can never smuggle extra positional arguments past what the DSL declared.
    """
    if cap.binding.kind != "script":
        raise CapabilityError(f"Capability '{cap.id}' has no script binding (kind={cap.binding.kind})")
    if not cap.binding.handler:
        raise CapabilityError(f"Capability '{cap.id}' binding is missing 'handler'")

    # Look up the script path from the handler
    if cap.binding.handler not in CAPABILITY_HANDLER_SCRIPT_MAP:
        raise CapabilityError(
            f"Capability '{cap.id}' handler '{cap.binding.handler}' not in CAPABILITY_HANDLER_SCRIPT_MAP"
        )
    script_path = CAPABILITY_HANDLER_SCRIPT_MAP[cap.binding.handler]

    # Look up the args template; default to empty list if not defined
    args_template = CAPABILITY_ARGS_MAP.get(cap.id, [])

    # Process args template, substituting parameters
    declared: set[str] = set()
    argv = ["python3", f"{repo_root.rstrip('/')}/{script_path}"]
    for arg in args_template:
        m = _PLACEHOLDER_RE.match(arg)
        if not m:
            argv.append(arg)
            continue
        # Extract parameter name from <name>
        name = m.group(1)
        declared.add(name)
        if name not in params:
            raise CapabilityError(f"Capability '{cap.id}' requires parameter '{name}'")
        argv.append(str(params[name]))

    # Reject any parameters that aren't in the declared set
    extra = set(params) - declared
    if extra:
        raise CapabilityError(f"Capability '{cap.id}' does not accept parameter(s): {sorted(extra)}")

    return argv
