"""Batched trimesh adapter for face normals and areas.

This adapter intentionally preserves input vertex order and does not repair,
merge, or reorient geometry.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import trimesh

from agente_impressao_3d.domain.overhang import FaceMetricsBatch


class TrimeshFaceMetricsReader:
    """Streams normal-Z components and face areas from an STL in NumPy batches."""

    def iter_face_metrics(
        self, source_path: Path, batch_size: int
    ) -> Iterator[FaceMetricsBatch]:
        # process=False preserves the source mesh's triangle winding and avoids
        # automatic merging or repair that could alter the analyzed topology.
        mesh = trimesh.load_mesh(source_path, file_type="stl", process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Expected one mesh in STL file: {source_path}")

        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces)
        for start in range(0, len(faces), batch_size):
            face_indices = faces[start : start + batch_size]
            triangles = vertices[face_indices]
            first_edge = triangles[:, 1] - triangles[:, 0]
            second_edge = triangles[:, 2] - triangles[:, 0]
            cross_product = np.cross(first_edge, second_edge)
            doubled_area = np.sqrt(np.einsum("ij,ij->i", cross_product, cross_product))

            area = doubled_area * 0.5
            normal_z = np.full(area.shape, np.nan, dtype=np.float64)
            valid_normal = np.isfinite(doubled_area) & (doubled_area > 0.0)
            np.divide(
                cross_product[:, 2],
                doubled_area,
                out=normal_z,
                where=valid_normal,
            )

            # Keep only the two compact arrays alive while the caller processes
            # this batch; no per-face Python records or global normal matrix exist.
            del triangles, first_edge, second_edge, cross_product, doubled_area
            yield FaceMetricsBatch(normal_z=normal_z, area=area)
