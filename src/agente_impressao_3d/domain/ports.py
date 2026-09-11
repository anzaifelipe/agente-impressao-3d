"""Ports implemented by infrastructure adapters."""

from pathlib import Path
from collections.abc import Iterator
from typing import Protocol

from .models import MeshInspection
from .overhang import FaceMetricsBatch
from .orientation import TriangleGeometryBatch
from .printer_profile import PrinterProfile, PrinterProfileEntry
from .cli_configuration import CliConfiguration


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


class PrinterProfileReader(Protocol):
    """Looks up reusable printer profiles without exposing their storage."""

    def get_profile(self, profile_id: str) -> PrinterProfile | None: ...

    def list_profiles(self) -> tuple[PrinterProfileEntry, ...]: ...


class CliConfigurationStore(Protocol):
    """Persists domain configuration without exposing serialization details."""

    def load(self) -> CliConfiguration | None: ...

    def initialize(self, configuration: CliConfiguration) -> bool: ...

    def save(self, configuration: CliConfiguration) -> None: ...
