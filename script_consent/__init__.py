"""Reusable Django app for explicit script consent (strict mode)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-script-consent")
except PackageNotFoundError:  # pragma: no cover - raw path / pre-install
    __version__ = "0.3.0"
