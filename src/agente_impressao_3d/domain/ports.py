"""Ports implemented by infrastructure adapters."""

from pathlib import Path
from typing import Protocol

from .models import MeshInspection


class MeshInspector(Protocol):
    """Inspects an STL mesh without applying application assumptions."""

    def inspect(self, source_path: Path) -> MeshInspection: ...
