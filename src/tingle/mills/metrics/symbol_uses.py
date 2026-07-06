"""AST-based counting of references to a function or class.

Static analysis only: re-exports, string references, and getattr are
invisible. Bare symbols count every same-named name/attribute in scope.
An occurrence is attributed to the line where the reference starts.
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

from tingle.pacts.diff import DiffMetricContext, DiffResult
from tingle.pacts.metrics import MetricContext, MetricResult

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet
    from pathlib import PurePath


def symbol_uses(ctx: MetricContext) -> MetricResult:
    """Count references to the `symbol` param across the Python files."""
    parts = tuple(ctx.params["symbol"].split("."))
    total = 0
    details: dict[str, int] = {}
    warnings: list[str] = []

    for path in ctx.files:
        if path.suffix != ".py":
            continue
        text = ctx.read(path)
        if text is None:
            warnings.append(f"{path}: skipped (binary, unreadable, or missing)")
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            warnings.append(f"{path}: skipped (syntax error: {exc.msg})")
            continue

        lines, star_fallback = _occurrence_lines(tree, parts)
        if star_fallback:
            warnings.append(
                f"{path}: star import: falling back to bare-name counting"
            )
        if lines:
            details[str(path)] = len(lines)
        total += len(lines)

    return MetricResult(value=total, details=details, warnings=tuple(warnings))


def symbol_uses_diff(ctx: DiffMetricContext) -> DiffResult:
    """Count references on lines the branch added vs lines it removed."""
    parts = tuple(ctx.params["symbol"].split("."))
    added = 0
    removed = 0
    details: dict[str, int] = {}
    warnings: list[str] = []

    for file in ctx.files:
        if file.path.suffix != ".py":
            continue
        file_added, added_warnings = _side_count(
            ctx.read, file.path, parts, file.added_lines, "current"
        )
        file_removed, removed_warnings = _side_count(
            ctx.read_base, file.path, parts, file.removed_lines, "base"
        )
        warnings.extend(added_warnings)
        warnings.extend(removed_warnings)
        added += file_added
        removed += file_removed
        if file_added - file_removed:
            details[str(file.path)] = file_added - file_removed

    return DiffResult(
        net=added - removed,
        added=added,
        removed=removed,
        details=details,
        warnings=tuple(warnings),
    )


def validate_params(params: Mapping[str, Any]) -> list[str]:
    """Check that `symbol` is a bare or dotted Python name."""
    symbol = params.get("symbol")
    if (
        not isinstance(symbol, str)
        or not symbol
        or not all(part.isidentifier() for part in symbol.split("."))
    ):
        return ["symbol must be a Python name like OldClient or pkg.mod.OldClient"]
    return []


def _side_count(
    reader: Callable[[PurePath], str | None],
    path: PurePath,
    parts: tuple[str, ...],
    touched: AbstractSet[int],
    side: str,
) -> tuple[int, list[str]]:
    """Count occurrences starting on the touched lines of one diff side."""
    if not touched:
        return 0, []
    text = reader(path)
    if text is None:
        return 0, [f"{path}: {side} side unreadable"]
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return 0, [f"{path}: {side} side skipped (syntax error: {exc.msg})"]
    lines, star_fallback = _occurrence_lines(tree, parts)
    warnings = (
        [f"{path}: {side} side: star import: falling back to bare-name counting"]
        if star_fallback
        else []
    )
    return sum(1 for line in lines if line in touched), warnings


def _occurrence_lines(
    tree: ast.AST, parts: tuple[str, ...]
) -> tuple[list[int], bool]:
    """Line numbers of every occurrence; flag = star-import fallback used."""
    if len(parts) == 1:
        return _bare_occurrences(tree, parts[0]), False

    bindings, import_lines, has_star_import = _collect_bindings(tree, parts)
    if has_star_import:
        return _bare_occurrences(tree, parts[-1]), True

    counter = _DottedCounter(bindings)
    counter.visit(tree)
    return [*import_lines, *counter.lines], False


def _collect_bindings(
    tree: ast.AST, parts: tuple[str, ...]
) -> tuple[dict[str, tuple[str, ...]], list[int], bool]:
    """Map local names to the attribute suffix still needed to reach the symbol.

    An empty suffix means the name is the symbol itself; every such
    binding created by an import counts as one use of the symbol, at the
    import statement's line.
    """
    bindings: dict[str, tuple[str, ...]] = {}
    import_lines: list[int] = []
    has_star_import = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _bind_plain_import(node, parts, bindings)
        elif isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                has_star_import = True
            else:
                import_lines.extend(_bind_from_import(node, parts, bindings))

    return bindings, import_lines, has_star_import


def _bind_plain_import(
    node: ast.Import, parts: tuple[str, ...], bindings: dict[str, tuple[str, ...]]
) -> None:
    for alias in node.names:
        module = tuple(alias.name.split("."))
        if alias.asname is None:
            if module[0] == parts[0]:
                bindings[module[0]] = parts[1:]
        else:
            suffix = _align_prefix(module, parts)
            if suffix is not None:
                bindings[alias.asname] = suffix


def _bind_from_import(
    node: ast.ImportFrom,
    parts: tuple[str, ...],
    bindings: dict[str, tuple[str, ...]],
) -> list[int]:
    """Bind from-imported names; return lines that import the symbol itself."""
    module = tuple(node.module.split(".")) if node.module else ()
    use_lines: list[int] = []
    for alias in node.names:
        chain = (*module, alias.name)
        if node.level == 0:
            suffix = _align_prefix(chain, parts)
        else:
            suffix = _align_anywhere(chain, parts)
        if suffix is not None:
            bindings[alias.asname or alias.name] = suffix
            if not suffix:
                use_lines.append(node.lineno)
    return use_lines


def _align_prefix(
    chain: tuple[str, ...], parts: tuple[str, ...]
) -> tuple[str, ...] | None:
    if len(chain) < len(parts) + 1 and parts[: len(chain)] == chain:
        return parts[len(chain) :]
    return None


def _align_anywhere(
    chain: tuple[str, ...], parts: tuple[str, ...]
) -> tuple[str, ...] | None:
    """Best-effort alignment for relative imports, package unknown."""
    for start in range(len(parts)):
        if parts[start : start + len(chain)] == chain:
            return parts[start + len(chain) :]
    return None


class _DottedCounter(ast.NodeVisitor):
    def __init__(self, bindings: Mapping[str, tuple[str, ...]]) -> None:
        self._bindings = bindings
        self.lines: list[int] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        chain = _attribute_chain(node)
        if chain is not None and self._matches(chain):
            self.lines.append(node.lineno)
            return  # the whole chain is one use; do not descend
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self._bindings.get(node.id) == ():
            self.lines.append(node.lineno)

    def _matches(self, chain: tuple[str, ...]) -> bool:
        suffix = self._bindings.get(chain[0])
        if suffix is None or len(chain) < 1 + len(suffix):
            return False
        return chain[1 : 1 + len(suffix)] == suffix


def _attribute_chain(node: ast.Attribute) -> tuple[str, ...] | None:
    names: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        names.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    names.append(current.id)
    return tuple(reversed(names))


def _bare_occurrences(tree: ast.AST, name: str) -> list[int]:
    counter = _BareCounter(name)
    counter.visit(tree)
    return counter.lines


class _BareCounter(ast.NodeVisitor):
    def __init__(self, name: str) -> None:
        self._name = name
        self.lines: list[int] = []

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == self._name:
            self.lines.append(node.lineno)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == self._name:
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._name in (alias.name.split(".")[-1], alias.asname):
                self.lines.append(node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if self._name in (alias.name, alias.asname):
                self.lines.append(node.lineno)
