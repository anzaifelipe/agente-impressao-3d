"""Trimesh-backed triangle batches for principal-axis orientation analysis."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from agente_impressao_3d.domain.orientation import TriangleGeometryBatch


@dataclass(slots=True)
class _TrimeshTriangleGeometrySource:
    """Keeps one unprocessed mesh loaded while exposing temporary triangle batches."""

    mesh: trimesh.Trimesh

    def iter_triangle_batches(self, batch_size: int) -> Iterator[TriangleGeometryBatch]:
        vertices = np.asarray(self.mesh.vertices, dtype=np.float64)
        faces = np.asarray(self.mesh.faces)
        for start in range(0, len(faces), batch_size):
            triangles = np.asarray(vertices[faces[start : start + batch_size]], dtype=np.float64)
            yield TriangleGeometryBatch(vertices=triangles)


class TrimeshTriangleGeometryReader:
    """Loads an STL once and provides repeatable NumPy triangle batches.

    The source mesh remains in memory for the analysis lifetime.  This avoids
    reloading the STL and avoids one full mesh copy per orientation, but is not
    a fully streaming STL reader.
    """

    def open(self, source_path: Path) -> _TrimeshTriangleGeometrySource:
        mesh = trimesh.load_mesh(source_path, file_type="stl", process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Expected one mesh in STL file: {source_path}")
        return _TrimeshTriangleGeometrySource(mesh=mesh)
