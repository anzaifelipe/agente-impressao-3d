"""Ports implemented by infrastructure adapters."""

from pathlib import Path
from collections.abc import Iterator
from typing import Protocol

from .models import MeshInspection
from .overhang import FaceMetricsBatch


class MeshInspector(Protocol):
    """Inspects an STL mesh without applying application assumptions."""

    def inspect(self, source_path: Path) -> MeshInspection: ...


class FaceMetricsReader(Protocol):
    """Streams vectorized face metrics without exposing a geometry library."""

    def iter_face_metrics(
        self, source_path: Path, batch_size: int
    ) -> Iterator[FaceMetricsBatch]: ...
