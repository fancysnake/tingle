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
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

from tingle.pacts.config import MetricTemplate, TemplateLoader, TemplateNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


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
        (`pack.ruff.noqa`) or in a namespace inside one, and a package
        deciding which is free to change its mind.
        """
        parts = path.split(".")
        for cut in range(len(parts), 0, -1):
            if (module := self._imported(".".join(parts[:cut]))) is not None:
                return _walk(module, parts[cut:])
        msg = f"no importable module in {path!r}"
        raise TemplateNotFoundError(msg)

    def catalogue(self, package: str) -> dict[str, object]:
        """Every template-shaped object under a package, by dotted path."""
        if (root := self._imported(package)) is None:
            msg = f"no importable package {package!r}"
            raise TemplateNotFoundError(msg)
        found = dict(_exported(root, prefix=package))
        for info in pkgutil.iter_modules(
            getattr(root, "__path__", []), prefix=f"{package}."
        ):
            if (module := self._imported(info.name)) is not None:
                found.update(_exported(module, prefix=info.name))
        return dict(sorted(found.items()))

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
    """Yield the templates a module offers, descending one level of grouping.

    A pack may name its templates at module level or gather them into a
    `SimpleNamespace`, and a config naming one should not have to know
    which -- so both are walked, and the dotted path reads the same.
    """
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        if _templated(value):
            yield f"{prefix}.{name}", value
        elif isinstance(value, SimpleNamespace):
            yield from (
                (f"{prefix}.{name}.{inner}", template)
                for inner, template in vars(value).items()
                if not inner.startswith("_") and _templated(template)
            )


def _templated(value: object) -> bool:
    """Report whether this is a template exactly, subclasses excluded.

    Only a filter for listing; what makes a template usable is checked
    where templates are verified, not here.
    """
    return value.__class__ is MetricTemplate
