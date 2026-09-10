"""Ports implemented by infrastructure adapters."""

from pathlib import Path
from collections.abc import Iterator
from typing import Protocol

from .models import MeshInspection
from .overhang import FaceMetricsBatch
from .orientation import TriangleGeometryBatch


class MeshInspector(Protocol):
    """Inspects an STL mesh without applying application assumptions."""

    def inspect(self, source_path: Path) -> MeshInspection: ...


class FaceMetricsReader(Protocol):
    """Streams vectorized face metrics without exposing a geometry library."""

    def iter_face_metrics(
        self, source_path: Path, batch_size: int
    ) -> Iterator[FaceMetricsBatch]: ...


class TriangleGeometrySource(Protocol):
    """Provides repeatable, bounded-memory triangle batch iteration."""

    def iter_triangle_batches(self, batch_size: int) -> Iterator[TriangleGeometryBatch]: ...


class TriangleGeometryReader(Protocol):
    """Opens one geometry source without exposing an implementation library."""

    def open(self, source_path: Path) -> TriangleGeometrySource: ...
