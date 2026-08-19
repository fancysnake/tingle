"""Python-import adapter for the template library.

Reaching a template means importing whatever package holds it, so this
adapter does what a config file asks and nothing more: it returns the
object found at a path, unverified. Deciding whether that object is a
usable template is a rule, and rules live upstream of here.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.pacts.config import MetricTemplate, TemplateLoader, TemplateNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import ModuleType


@dataclass(frozen=True)
class PythonTemplateLoader(TemplateLoader):
    """Loads templates by importing the module that defines them.

    The import itself is injected, so a test can watch what was reached
    for without writing a package to disk first.
    """

    importer: Callable[[str], ModuleType] = importlib.import_module

    def load(self, path: str) -> object:
        """Return the object at a dotted path, importing what it takes.

        The path is split at the longest prefix that imports, and the rest
        is walked as attributes -- so a template may sit in a module
        (`pack.ruff.noqa`), in a subpackage below it, or behind whatever
        the module exposes it as, and moving it need not move the path.
        """
        parts = path.split(".")
        for cut in range(len(parts), 0, -1):
            if (module := self._imported(".".join(parts[:cut]))) is not None:
                return _walk(module, parts[cut:])
        msg = f"no importable module in {path!r}"
        raise TemplateNotFoundError(msg)

    def catalogue(self, package: str) -> dict[str, object]:
        """Every template-shaped object under a package, by dotted path.

        The walk goes as deep as the package nests, because `load` walks a
        dotted path of any length: a pack that groups its templates into
        subpackages would otherwise be fully usable and entirely invisible.
        """
        if (root := self._imported(package)) is None:
            msg = f"no importable package {package!r}"
            raise TemplateNotFoundError(msg)
        found = dict(_exported(root, prefix=package))
        self._descend(root, prefix=package, found=found)
        return dict(sorted(found.items()))

    def _descend(
        self, module: ModuleType, *, prefix: str, found: dict[str, object]
    ) -> None:
        for info in pkgutil.iter_modules(
            getattr(module, "__path__", []), prefix=f"{prefix}."
        ):
            if (child := self._imported(info.name)) is None:
                continue
            found.update(_exported(child, prefix=info.name))
            if info.ispkg:
                self._descend(child, prefix=info.name, found=found)

    def _imported(self, name: str) -> ModuleType | None:
        """Import a module, or None when there is no such module.

        A module that exists but fails on its own imports raises, rather
        than reading as absent: the difference between a typo in a config
        file and a broken package is one the reader needs.
        """
        try:
            return self.importer(name)
        except ModuleNotFoundError as exc:
            if _above(exc.name, name):
                return None
            raise


def _above(missing: str | None, name: str) -> bool:
    """Whether the module that went missing is `name` itself or above it.

    Any other name means the package is there and one of *its* imports
    failed -- a broken package, which is not what a typo looks like.
    """
    return missing is not None and (name == missing or name.startswith(f"{missing}."))


def _walk(module: ModuleType, attributes: list[str]) -> object:
    obj: object = module
    for attribute in attributes:
        try:
            obj = getattr(obj, attribute)
        except AttributeError:
            msg = f"no attribute {attribute!r} in {module.__name__!r}"
            raise TemplateNotFoundError(msg) from None
    return obj


def _exported(module: ModuleType, *, prefix: str) -> Iterator[tuple[str, object]]:
    """Yield the templates a module offers under the names it offers them by.

    `__all__` is the pack's own statement of what it exports, so it wins
    where a module makes one -- without it, a template re-exported by two
    modules is catalogued twice under two paths. It is still only a list
    of names from untrusted code, so what it names is filtered the same.
    """
    for name in _public(module):
        value = getattr(module, name, None)
        if _templated(value):
            yield f"{prefix}.{name}", value


def _public(module: ModuleType) -> Iterator[str]:
    listed = getattr(module, "__all__", None)
    if isinstance(listed, (list, tuple)):
        return (name for name in listed if isinstance(name, str))
    return (name for name in vars(module) if not name.startswith("_"))


def _templated(value: object) -> bool:
    """Report whether this is a template exactly, subclasses excluded.

    Only a filter for listing; what makes a template usable is checked
    where templates are verified, not here.
    """
    return value.__class__ is MetricTemplate
