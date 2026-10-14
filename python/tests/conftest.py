"""Pytest configuration and compatibility aliases for Soro.

Provides transparent backwards compatibility so legacy tests importing from
`veyra.*` seamlessly resolve to the exact identical objects in `soro.*`.
"""

import importlib
import importlib.machinery
import sys


class AliasLoader:
    def __init__(self, target: str):
        self.target = target

    def create_module(self, spec):
        mod = importlib.import_module(self.target)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class VeyraAliasFinder:
    """Redirects all `veyra.*` module imports to identical `soro.*` instances."""

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == "veyra" or fullname.startswith("veyra."):
            soro_name = "soro" + fullname[5:]
            return importlib.machinery.ModuleSpec(fullname, AliasLoader(soro_name))
        return None


if not any(isinstance(f, VeyraAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, VeyraAliasFinder())
