"""Legacy compatibility shim for setuptools build frontends.

Project metadata lives in ``pyproject.toml``. Keeping this minimal module
allows older workflows that still invoke ``python setup.py`` to use the same
single source of truth without duplicating dependency or package metadata.
"""

from setuptools import setup


setup()
