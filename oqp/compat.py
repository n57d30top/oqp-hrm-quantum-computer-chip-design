"""Compatibility shims for current Python/scipy with Strawberry Fields 0.23."""

from __future__ import annotations

import sys
import types


def patch_strawberryfields_imports() -> None:
    """Patch legacy imports before importing Strawberry Fields."""
    if "pkg_resources" not in sys.modules:
        module = types.ModuleType("pkg_resources")
        module.resource_filename = lambda *args, **kwargs: ""
        sys.modules["pkg_resources"] = module

    import scipy.integrate

    if not hasattr(scipy.integrate, "simps") and hasattr(scipy.integrate, "simpson"):
        scipy.integrate.simps = scipy.integrate.simpson
