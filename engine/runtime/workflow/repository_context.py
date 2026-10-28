"""Repository context generation for Jira2PR workers.

Repository context gives non-editing workers, especially the planner, a
deterministic view of the repository without requiring Aider's repo-map
implementation.

The default provider uses:

- ``git ls-files`` for the authoritative tracked-file inventory
- Tree-sitter (``tree-sitter-language-pack``) for Python structure extraction
- ``ast`` for Python docstrings, signatures, and module-level constants
- PyYAML, ``json``, and ``tomllib`` for top-level keys of config files

The public provider abstraction is intentionally generic so another
implementation, such as an MCP repository mapper, can be introduced later
without changing ContextStrategy or worker invocation.

The generated repository map includes every non-hidden tracked file path.
Dot-prefixed folders are omitted, except ``.github/``, which holds workflow
configuration. Supported source files additionally include structural
information such as classes, functions, methods, imports, and docstrings.
"""

from __future__ import annotations

import ast
import json
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from runtime.logging_config import get_logger

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: TOML summaries are skipped.
    tomllib = None

logger = get_logger("workflow.repository_context")

DEFAULT_GIT_TIMEOUT_SECONDS = 30
DEFAULT_OUTPUT_FILENAME = "repository-map.txt"
DEFAULT_MAX_STRUCTURE_CHARS = 60_000
MAX_CONFIG_FILE_BYTES = 256 * 1024
MAX_CONFIG_KEYS = 50
MAX_DOCSTRING_CHARS = 120
MAX_SIGNATURE_CHARS = 160
ALLOWED_HIDDEN_DIRS = frozenset({".github"})
CONFIG_SUFFIXES = frozenset({".yaml", ".yml", ".json"}) | (
    frozenset({".toml"}) if tomllib is not None else frozenset()
)


class RepositoryContextError(RuntimeError):
    """Raised when repository context cannot be generated."""


@dataclass(frozen=True)
class RepositoryContextRequest:
    """Input for repository context generation."""

    repo_root: Path

    # Optional files that are especially relevant to the current task.
    # The basic Tree-sitter implementation does not rank by these yet, but
    # they are part of the provider-neutral API for future implementations.
    mentioned_files: tuple[Path, ...] = ()

    # Optional symbols or identifiers referenced by requirements or feedback.
    mentioned_idents: tuple[str, ...] = ()

    # Provider-specific metadata for future extensions.
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RepositoryContextResult:
    """Repository context produced by a provider."""

    provider: str
    content: str

    def is_empty(self) -> bool:
        """Return True when no usable repository context was produced."""

        return not self.content.strip()


class RepositoryContextProvider(ABC):
    """Abstract provider for repository context generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return a stable provider identifier."""

    @abstractmethod
    def generate(
        self,
        request: RepositoryContextRequest,
    ) -> RepositoryContextResult:
        """Generate repository context."""


class TreeSitterRepositoryContextProvider(RepositoryContextProvider):
    """Generate repository context using Git and Tree-sitter.

    All tracked repository paths are discovered through ``git ls-files`` and
    written into the map.

    Python files are parsed with Tree-sitter for structure and with ``ast``
    for docstrings and signatures. Config files contribute their top-level
    keys. Structural sections share ``max_structure_chars``; the file
    inventory is never truncated.

    Other languages can be added later by registering additional language
    parsers without changing the public provider interface.
    """

    def __init__(
        self,
        *,
        git_timeout: int = DEFAULT_GIT_TIMEOUT_SECONDS,
        max_structure_chars: int = DEFAULT_MAX_STRUCTURE_CHARS,
    ) -> None:
        self._git_timeout = git_timeout
        self._max_structure_chars = max_structure_chars

    @property
    def name(self) -> str:
        return "tree-sitter"

    def generate(
        self,
        request: RepositoryContextRequest,
    ) -> RepositoryContextResult:
        """Generate repository context for a Git repository."""

        repo_root = request.repo_root.resolve()

        if not repo_root.is_dir():
            raise RepositoryContextError(
                f"Repository root does not exist: {repo_root}"
            )

        tracked_files = [
            path
            for path in self._git_ls_files(repo_root)
            if _is_mapped_path(path)
        ]

        if not tracked_files:
            raise RepositoryContextError(
                f"No tracked files found in repository: {repo_root}"
            )

        logger.info(
            "Building repository context from %d tracked file(s)",
            len(tracked_files),
        )

        sections: list[str] = []

        sections.append(
            self._render_header(
                repo_root=repo_root,
                file_count=len(tracked_files),
            )
        )

        sections.append(
            self._render_file_inventory(
                tracked_files
            )
        )

        structure = self._render_source_structure(
            repo_root=repo_root,
            tracked_files=tracked_files,
        )

        if structure:
            sections.append(
                structure
            )

        content = "\n\n".join(
            section.rstrip()
            for section in sections
            if section.strip()
        )

        content = content.rstrip() + "\n"

        logger.info(
            "Repository context generated: provider=%s chars=%d",
            self.name,
            len(content),
        )

        return RepositoryContextResult(
            provider=self.name,
            content=content,
        )

    def _git_ls_files(
        self,
        repo_root: Path,
    ) -> list[Path]:
        """Return every Git-tracked file as a repository-relative Path."""

        command = [
            "git",
            "ls-files",
            "-z",
        ]

        logger.debug(
            "Discovering tracked repository files: %s",
            " ".join(command),
        )

        try:
            result = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                timeout=self._git_timeout,
                check=False,
            )

        except subprocess.TimeoutExpired as exc:
            raise RepositoryContextError(
                f"git ls-files timed out after "
                f"{self._git_timeout} seconds"
            ) from exc

        except FileNotFoundError as exc:
            raise RepositoryContextError(
                "Unable to execute git. Ensure Git is installed "
                "and available on PATH."
            ) from exc

        except OSError as exc:
            raise RepositoryContextError(
                f"Unable to execute git ls-files: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()

            raise RepositoryContextError(
                f"git ls-files exited with status "
                f"{result.returncode}"
                + (
                    f": {stderr}"
                    if stderr
                    else ""
                )
            )

        entries = result.stdout.split(b"\0")

        files: list[Path] = []

        for entry in entries:
            if not entry:
                continue

            value = entry.decode(
                "utf-8",
                errors="surrogateescape",
            )

            files.append(
                Path(value)
            )

        files.sort(
            key=lambda path: path.as_posix()
        )

        return files

    def _render_header(
        self,
        *,
        repo_root: Path,
        file_count: int,
    ) -> str:
        """Render repository-map metadata and usage guidance."""

        return "\n".join(
            [
                "# Repository Context",
                "",
                f"provider: {self.name}",
                f"repository_root: {repo_root}",
                f"tracked_files: {file_count}",
                "",
                "The Repository Files section below is the authoritative",
                "inventory of non-hidden Git-tracked paths for this repository",
                "snapshot. Dot-prefixed folders are omitted, except .github/.",
                "",
                "When selecting an existing file, use a path listed in that",
                "section. Do not infer that an unlisted path already exists.",
                "",
                "The Source Structure and Config Structure sections summarize",
                "supported source and configuration files and are intended to",
                "help identify where changes belong.",
            ]
        )

    def _render_file_inventory(
        self,
        tracked_files: Sequence[Path],
    ) -> str:
        """Render the complete tracked-file inventory."""

        lines = [
            "## Repository Files",
            "",
        ]

        for path in tracked_files:
            lines.append(
                path.as_posix()
            )

        return "\n".join(
            lines
        )

    def _render_source_structure(
        self,
        *,
        repo_root: Path,
        tracked_files: Sequence[Path],
    ) -> str:
        """Render structural summaries for supported files within budget."""

        python_files = [
            path
            for path in tracked_files
            if path.suffix == ".py"
        ]

        config_files = [
            path
            for path in tracked_files
            if path.suffix.lower() in CONFIG_SUFFIXES
        ]

        if not python_files and not config_files:
            return ""

        parser = _create_python_parser() if python_files else None

        python_blocks = self._python_blocks(
            repo_root=repo_root,
            python_files=python_files,
            parser=parser,
        )

        config_blocks = self._config_blocks(
            repo_root=repo_root,
            config_files=config_files,
        )

        python_kept, used = _fit_blocks(
            python_blocks,
            self._max_structure_chars,
        )

        config_kept, _ = _fit_blocks(
            config_blocks,
            self._max_structure_chars - used,
        )

        omitted = (
            len(python_blocks)
            - len(python_kept)
            + len(config_blocks)
            - len(config_kept)
        )

        logger.debug(
            "Structure summaries: python=%d/%d config=%d/%d omitted=%d",
            len(python_kept),
            len(python_blocks),
            len(config_kept),
            len(config_blocks),
            omitted,
        )

        sections: list[str] = []

        if python_kept:
            sections.append(
                "\n\n".join(
                    ["## Source Structure", *python_kept]
                )
            )

        if config_kept:
            sections.append(
                "\n\n".join(
                    ["## Config Structure", *config_kept]
                )
            )

        if omitted:
            sections.append(
                f"{omitted} file summar"
                f"{'y' if omitted == 1 else 'ies'} omitted to stay within "
                f"the {self._max_structure_chars} character structure budget."
            )

        return "\n\n".join(sections)

    def _python_blocks(
        self,
        *,
        repo_root: Path,
        python_files: Sequence[Path],
        parser,
    ) -> list[str]:
        """Render one structural block per parseable Python file."""

        blocks: list[str] = []

        for relative_path in python_files:
            absolute_path = (
                repo_root
                / relative_path
            )

            if not absolute_path.is_file():
                continue

            try:
                summary = _summarize_python_file(
                    parser=parser,
                    path=absolute_path,
                )

            except (OSError, UnicodeError) as exc:
                logger.warning(
                    "Unable to inspect Python file %s: %s",
                    relative_path,
                    exc,
                )
                continue

            except RuntimeError as exc:
                logger.warning(
                    "Tree-sitter failed to inspect %s: %s",
                    relative_path,
                    exc,
                )
                continue

            if summary is None:
                continue

            blocks.append(
                _render_python_summary(
                    relative_path=relative_path,
                    summary=summary,
                )
            )

        return blocks

    def _config_blocks(
        self,
        *,
        repo_root: Path,
        config_files: Sequence[Path],
    ) -> list[str]:
        """Render one block per config file with parseable top-level keys."""

        blocks: list[str] = []

        for relative_path in config_files:
            absolute_path = repo_root / relative_path

            if not absolute_path.is_file():
                continue

            keys = _summarize_config_file(absolute_path)

            if not keys:
                continue

            blocks.append(
                _render_config_summary(
                    relative_path=relative_path,
                    keys=keys,
                )
            )

        return blocks


@dataclass(frozen=True)
class PythonSymbolDetail:
    """Signature and docstring summary for one Python symbol."""

    signature: str | None
    docstring: str | None


@dataclass(frozen=True)
class PythonFileSummary:
    """Structural summary extracted from one Python source file."""

    classes: tuple[str, ...]
    functions: tuple[str, ...]
    methods: tuple[str, ...]
    imports: tuple[str, ...]
    module_docstring: str | None = None
    constants: tuple[str, ...] = ()
    details: Mapping[str, PythonSymbolDetail] = field(
        default_factory=dict
    )


def _create_python_parser():
    """Create a Tree-sitter parser configured for Python."""

    try:
        from tree_sitter_language_pack import get_parser

    except ImportError as exc:
        raise RepositoryContextError(
            "Tree-sitter language pack is not installed. "
            "Install it with: uv add tree-sitter-language-pack"
        ) from exc

    try:
        return get_parser("python")

    except Exception as exc:
        raise RepositoryContextError(
            f"Unable to initialize Tree-sitter Python parser: {exc}"
        ) from exc


def _summarize_python_file(
    *,
    parser,
    path: Path,
) -> PythonFileSummary | None:
    """Extract useful structural information from a Python source file."""

    source = path.read_bytes()

    if not source:
        return None

    tree = parser.parse(
        source
    )

    root = tree.root_node

    classes: list[str] = []
    functions: list[str] = []
    methods: list[str] = []
    imports: list[str] = []

    _walk_python_node(
        node=root,
        source=source,
        classes=classes,
        functions=functions,
        methods=methods,
        imports=imports,
        inside_class=False,
    )

    module_docstring, constants, details = _extract_python_ast_details(
        source
    ) or (None, (), {})

    if not (
        classes
        or functions
        or methods
        or imports
        or constants
        or module_docstring
    ):
        return None

    return PythonFileSummary(
        module_docstring=module_docstring,
        constants=constants,
        details=details,
        classes=tuple(
            _unique_preserving_order(
                classes
            )
        ),
        functions=tuple(
            _unique_preserving_order(
                functions
            )
        ),
        methods=tuple(
            _unique_preserving_order(
                methods
            )
        ),
        imports=tuple(
            _unique_preserving_order(
                imports
            )
        ),
    )


def _walk_python_node(
    *,
    node,
    source: bytes,
    classes: list[str],
    functions: list[str],
    methods: list[str],
    imports: list[str],
    inside_class: bool,
) -> None:
    """Walk a Python Tree-sitter AST and collect structural elements."""

    node_type = node.type

    if node_type == "class_definition":
        name = _node_field_text(
            node=node,
            field_name="name",
            source=source,
        )

        if name:
            classes.append(
                name
            )

        for child in node.children:
            _walk_python_node(
                node=child,
                source=source,
                classes=classes,
                functions=functions,
                methods=methods,
                imports=imports,
                inside_class=True,
            )

        return

    if node_type == "function_definition":
        name = _node_field_text(
            node=node,
            field_name="name",
            source=source,
        )

        if name:
            if inside_class:
                methods.append(
                    name
                )
            else:
                functions.append(
                    name
                )

        # Do not recursively treat nested functions as module-level
        # functions. Their names generally add noise to repository maps.
        return

    if node_type in {
        "import_statement",
        "import_from_statement",
    }:
        text = _node_text(
            node=node,
            source=source,
        )

        if text:
            imports.append(
                _compact_whitespace(
                    text
                )
            )

        return

    for child in node.children:
        _walk_python_node(
            node=child,
            source=source,
            classes=classes,
            functions=functions,
            methods=methods,
            imports=imports,
            inside_class=inside_class,
        )


def _node_field_text(
    *,
    node,
    field_name: str,
    source: bytes,
) -> str | None:
    """Return UTF-8 text for a named Tree-sitter field."""

    field = node.child_by_field_name(
        field_name
    )

    if field is None:
        return None

    return _node_text(
        node=field,
        source=source,
    )


def _node_text(
    *,
    node,
    source: bytes,
) -> str:
    """Extract source text represented by a Tree-sitter node."""

    raw = source[
        node.start_byte:node.end_byte
    ]

    return raw.decode(
        "utf-8",
        errors="replace",
    ).strip()


def _compact_whitespace(
    text: str,
) -> str:
    """Collapse multiline syntax into one compact line."""

    return " ".join(
        text.split()
    )


def _is_mapped_path(path: Path) -> bool:
    """Return False when a path lives under a hidden (dot-prefixed) folder."""

    return not any(
        part.startswith(".") and part not in ALLOWED_HIDDEN_DIRS
        for part in path.parts[:-1]
    )


def _fit_blocks(
    blocks: Sequence[str],
    budget: int,
) -> tuple[list[str], int]:
    """Keep leading blocks that fit within budget.

    Returns the kept blocks and the number of characters they consume.
    """

    kept: list[str] = []
    used = 0

    for block in blocks:
        cost = len(block) + 2

        if used + cost > budget:
            break

        kept.append(block)
        used += cost

    return kept, used


def _summarize_config_file(path: Path) -> tuple[str, ...] | None:
    """Return top-level keys of a YAML, JSON, or TOML mapping file."""

    try:
        if path.stat().st_size > MAX_CONFIG_FILE_BYTES:
            return None

        text = path.read_text(encoding="utf-8")

    except (OSError, UnicodeError) as exc:
        logger.warning("Unable to read config file %s: %s", path, exc)
        return None

    suffix = path.suffix.lower()

    try:
        if suffix == ".json":
            data = json.loads(text)

        elif suffix == ".toml":
            data = tomllib.loads(text)

        else:
            data = next(yaml.safe_load_all(text), None)

    except (ValueError, yaml.YAMLError) as exc:
        logger.warning("Unable to parse config file %s: %s", path, exc)
        return None

    if not isinstance(data, dict):
        return None

    return tuple(
        str(key)
        for key in list(data)[:MAX_CONFIG_KEYS]
    )


def _render_config_summary(
    *,
    relative_path: Path,
    keys: Sequence[str],
) -> str:
    """Render top-level keys for one config file."""

    return "\n".join(
        [
            f"### {relative_path.as_posix()}",
            f"keys: {', '.join(keys)}",
        ]
    )


def _extract_python_ast_details(
    source: bytes,
) -> tuple[str | None, tuple[str, ...], dict[str, PythonSymbolDetail]] | None:
    """Collect docstrings, signatures, and constants using the ast module.

    Returns None when the source cannot be parsed by the running Python
    version, so callers fall back to the Tree-sitter-only summary.
    """

    try:
        module = ast.parse(source)

    except (SyntaxError, ValueError) as exc:
        logger.debug("ast could not parse Python source: %s", exc)
        return None

    constants: list[str] = []

    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets

        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]

        else:
            continue

        for target in targets:
            if (
                isinstance(target, ast.Name)
                and _is_constant_name(target.id)
                and target.id not in constants
            ):
                constants.append(target.id)

    details: dict[str, PythonSymbolDetail] = {}
    _collect_python_definitions(module.body, details)

    return (
        _first_line(ast.get_docstring(module)),
        tuple(constants),
        details,
    )


def _collect_python_definitions(
    nodes: Sequence[ast.AST],
    details: dict[str, PythonSymbolDetail],
) -> None:
    """Record the first signature and docstring seen for each symbol name."""

    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            details.setdefault(
                node.name,
                PythonSymbolDetail(
                    signature=_format_signature(node),
                    docstring=_first_line(ast.get_docstring(node)),
                ),
            )
            # Nested functions are not summarized; skip their bodies.
            continue

        if isinstance(node, ast.ClassDef):
            details.setdefault(
                node.name,
                PythonSymbolDetail(
                    signature=None,
                    docstring=_first_line(ast.get_docstring(node)),
                ),
            )
            _collect_python_definitions(node.body, details)
            continue

        _collect_python_definitions(
            [
                child
                for child in ast.iter_child_nodes(node)
                if isinstance(child, (ast.stmt, ast.excepthandler))
            ],
            details,
        )


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return the parameter list and return annotation of a function."""

    arguments = ast.unparse(node.args)
    returns = (
        f" -> {ast.unparse(node.returns)}"
        if node.returns is not None
        else ""
    )

    return _truncate(f"({arguments}){returns}", MAX_SIGNATURE_CHARS)


def _first_line(docstring: str | None) -> str | None:
    """Return the first non-empty line of a docstring, truncated."""

    if not docstring:
        return None

    for line in docstring.splitlines():
        stripped = line.strip()

        if stripped:
            return _truncate(stripped, MAX_DOCSTRING_CHARS)

    return None


def _truncate(text: str, limit: int) -> str:
    """Shorten text to limit characters, marking truncation with '...'."""

    if len(text) <= limit:
        return text

    return text[: limit - 3].rstrip() + "..."


def _is_constant_name(name: str) -> bool:
    """Return True for UPPER_CASE names such as MAX_RETRIES."""

    return name == name.upper() and any(char.isalpha() for char in name)


def _render_symbol_lines(
    names: Sequence[str],
    details: Mapping[str, PythonSymbolDetail],
) -> list[str]:
    """Render symbol names with optional signature and docstring."""

    lines: list[str] = []

    for name in names:
        text = f"  - {name}"
        detail = details.get(name)

        if detail is not None:
            if detail.signature:
                text += detail.signature

            if detail.docstring:
                text += f": {detail.docstring}"

        lines.append(text)

    return lines


def _unique_preserving_order(
    values: Sequence[str],
) -> list[str]:
    """Return unique strings while preserving their original order."""

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value in seen:
            continue

        seen.add(
            value
        )

        result.append(
            value
        )

    return result


def _render_python_summary(
    *,
    relative_path: Path,
    summary: PythonFileSummary,
) -> str:
    """Render a compact structural summary for one Python file."""

    lines = [
        f"### {relative_path.as_posix()}",
    ]

    if summary.module_docstring:
        lines.append(f"docstring: {summary.module_docstring}")

    if summary.constants:
        lines.extend(
            [
                "",
                "constants:",
            ]
        )

        lines.extend(
            f"  - {name}"
            for name in summary.constants
        )

    if summary.classes:
        lines.extend(
            [
                "",
                "classes:",
            ]
        )

        lines.extend(
            _render_symbol_lines(summary.classes, summary.details)
        )

    if summary.functions:
        lines.extend(
            [
                "",
                "functions:",
            ]
        )

        lines.extend(
            _render_symbol_lines(summary.functions, summary.details)
        )

    if summary.methods:
        lines.extend(
            [
                "",
                "methods:",
            ]
        )

        lines.extend(
            _render_symbol_lines(summary.methods, summary.details)
        )

    if summary.imports:
        lines.extend(
            [
                "",
                "imports:",
            ]
        )

        lines.extend(
            f"  - {value}"
            for value in summary.imports
        )

    return "\n".join(
        lines
    )


class MCPRepositoryContextProvider(RepositoryContextProvider):
    """Extension point for a future MCP repository mapping provider.

    Jira2PR intentionally does not depend on a specific MCP client library or
    repository-map tool schema here.

    A future concrete implementation can translate RepositoryContextRequest
    into an MCP tool invocation while ContextStrategy continues to depend only
    on RepositoryContextProvider.
    """

    def __init__(
        self,
        *,
        provider_name: str = "mcp",
    ) -> None:
        self._provider_name = provider_name

    @property
    def name(self) -> str:
        return self._provider_name

    def generate(
        self,
        request: RepositoryContextRequest,
    ) -> RepositoryContextResult:
        payload = {
            "repo_root": str(
                request.repo_root.resolve()
            ),
            "mentioned_files": [
                str(path)
                for path in request.mentioned_files
            ],
            "mentioned_idents": list(
                request.mentioned_idents
            ),
            "metadata": dict(
                request.metadata or {}
            ),
        }

        content = self._call_repository_map_tool(
            payload
        )

        if not isinstance(content, str):
            raise RepositoryContextError(
                "MCP repository context provider returned non-text content"
            )

        content = content.strip()

        if not content:
            raise RepositoryContextError(
                "MCP repository context provider returned empty context"
            )

        return RepositoryContextResult(
            provider=self.name,
            content=content,
        )

    def _call_repository_map_tool(
        self,
        payload: Mapping[str, Any],
    ) -> str:
        """Invoke the configured MCP repository-map tool."""

        raise NotImplementedError(
            "No MCP repository mapping client is configured"
        )


def create_repository_context_provider(
    provider: str,
) -> RepositoryContextProvider:
    """Create a repository context provider by name."""

    normalized = provider.strip().lower()

    if normalized in {
        "tree-sitter",
        "treesitter",
    }:
        return TreeSitterRepositoryContextProvider()

    if normalized == "mcp":
        return MCPRepositoryContextProvider()

    raise ValueError(
        f"Unsupported repository context provider: {provider!r}"
    )


def repository_context_path(
    *,
    context_dir: Path,
) -> Path:
    """Return the standard materialized repository-map path."""

    return (
        context_dir
        / DEFAULT_OUTPUT_FILENAME
    )


def materialize_repository_context(
    *,
    provider: RepositoryContextProvider,
    request: RepositoryContextRequest,
    output_path: Path,
) -> Path:
    """Generate and atomically write repository context to disk."""

    result = provider.generate(
        request
    )

    if result.is_empty():
        raise RepositoryContextError(
            f"Repository context provider "
            f"{result.provider!r} produced empty context"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f".{output_path.name}.tmp"
    )

    try:
        temporary_path.write_text(
            result.content.rstrip() + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(
            output_path
        )

    finally:
        temporary_path.unlink(
            missing_ok=True
        )

    logger.info(
        "Repository context written to: %s",
        output_path,
    )

    return output_path