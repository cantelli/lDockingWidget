"""High-level activation and diagnostics for ldocking fallback mode."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from types import ModuleType

import PySide6.QtWidgets as _qw

from . import monkey

_ENV_VAR = "LDOCKING_PATCH"
_FALSE_VALUES = {"0", "false", "off", "no"}
_TRUE_VALUES = {"1", "true", "on", "yes"}
_SKIP_MODULE_PREFIXES = ("PySide6", "shiboken6", "ldocking")


@dataclass(frozen=True)
class BindingLeak:
    """A module-global reference to a native Qt docking class."""

    module: str
    attr: str
    qt_name: str


@dataclass(frozen=True)
class ActivationReport:
    """Current ldocking activation status and any detected import-order leaks."""

    requested: bool
    patched: bool
    stylesheet_translation_active: bool
    import_order_ok: bool
    env_value: str | None
    leaks: tuple[BindingLeak, ...]

    def format(self) -> str:
        status = "patched" if self.patched else "unpatched"
        lines = [
            f"ldocking status: {status}",
            f"stylesheet translation active: {self.stylesheet_translation_active}",
            f"import order clean: {self.import_order_ok}",
        ]
        if self.env_value is not None:
            lines.append(f"{_ENV_VAR}={self.env_value!r}")
        if self.leaks:
            lines.append("native bindings still referenced by:")
            lines.extend(
                f"  - {leak.module}.{leak.attr} -> {leak.qt_name}"
                for leak in self.leaks
            )
        return "\n".join(lines)


def _parse_env_flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _iter_scan_modules(exclude_prefixes: tuple[str, ...] = ()) -> list[tuple[str, ModuleType]]:
    modules: list[tuple[str, ModuleType]] = []
    for name, module in sys.modules.items():
        if (
            module is None
            or name.startswith(_SKIP_MODULE_PREFIXES)
            or name.startswith(exclude_prefixes)
        ):
            continue
        modules.append((name, module))
    return modules


def find_native_binding_leaks(
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> tuple[BindingLeak, ...]:
    """Return module globals that still reference the original Qt classes."""
    orig_main = monkey._ORIG["QMainWindow"]
    orig_dock = monkey._ORIG["QDockWidget"]
    leaks: list[BindingLeak] = []
    for module_name, module in _iter_scan_modules(exclude_prefixes):
        try:
            namespace = vars(module)
        except TypeError:
            continue
        for attr, value in namespace.items():
            if value is orig_main:
                leaks.append(BindingLeak(module_name, attr, "QMainWindow"))
            elif value is orig_dock:
                leaks.append(BindingLeak(module_name, attr, "QDockWidget"))
    leaks.sort(key=lambda leak: (leak.module, leak.attr, leak.qt_name))
    return tuple(leaks)


def describe_runtime(
    requested: bool | None = None,
    env_value: str | None = None,
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> ActivationReport:
    """Report current patch state and import-order health without changing it."""
    leaks = (
        find_native_binding_leaks(exclude_prefixes=exclude_prefixes)
        if monkey.is_patched()
        else ()
    )
    stylesheet_translation_active = (
        _qw.QApplication.setStyleSheet is not monkey._ORIG["QApplication.setStyleSheet"]
    )
    patched = monkey.is_patched()
    return ActivationReport(
        requested=patched if requested is None else requested,
        patched=patched,
        stylesheet_translation_active=stylesheet_translation_active,
        import_order_ok=not leaks,
        env_value=env_value,
        leaks=leaks,
    )


def activate(
    *,
    validate: bool = True,
    strict: bool = False,
    exclude_prefixes: tuple[str, ...] = (),
) -> ActivationReport:
    """Enable ldocking patching and optionally validate import ordering."""
    monkey.patch()
    report = describe_runtime(requested=True, exclude_prefixes=exclude_prefixes)
    if validate and strict and report.leaks:
        raise RuntimeError(report.format())
    return report


def deactivate(*, exclude_prefixes: tuple[str, ...] = ()) -> ActivationReport:
    """Disable ldocking patching and return the resulting runtime report."""
    monkey.unpatch()
    return describe_runtime(requested=False, exclude_prefixes=exclude_prefixes)


def activate_from_env(
    *,
    default: bool = True,
    validate: bool = True,
    strict: bool = False,
    exclude_prefixes: tuple[str, ...] = (),
) -> ActivationReport:
    """Enable or disable ldocking using the ``LDOCKING_PATCH`` env var."""
    raw = os.getenv(_ENV_VAR)
    enabled = _parse_env_flag(raw, default)
    if enabled:
        report = activate(
            validate=validate,
            strict=strict,
            exclude_prefixes=exclude_prefixes,
        )
        return ActivationReport(
            requested=True,
            patched=report.patched,
            stylesheet_translation_active=report.stylesheet_translation_active,
            import_order_ok=report.import_order_ok,
            env_value=raw,
            leaks=report.leaks,
        )
    monkey.unpatch()
    report = describe_runtime(
        requested=False,
        env_value=raw,
        exclude_prefixes=exclude_prefixes,
    )
    return report
