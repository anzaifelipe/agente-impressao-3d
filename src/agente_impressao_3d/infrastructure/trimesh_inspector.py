"""Trimesh-backed implementation of the mesh-inspection port."""

from pathlib import Path

import trimesh

from agente_impressao_3d.domain.models import (
    AnalysisWarning,
    BoundingBox,
    GeometryFacts,
    MeshInspection,
    Vector3,
    Volume,
)


class TrimeshMeshInspector:
    """Reads an STL and translates trimesh details into domain models."""

    def inspect(self, source_path: Path) -> MeshInspection:
        # STL commonly repeats vertices per face.  Processing merges equivalent
        # vertices so topology-based facts such as watertightness are meaningful.
        mesh = trimesh.load_mesh(source_path, file_type="stl", process=True)
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Expected one mesh in STL file: {source_path}")

        bounds = mesh.bounds
        bounding_box = BoundingBox(
            minimum=Vector3(*map(float, bounds[0])),
            maximum=Vector3(*map(float, bounds[1])),
        )
        watertight = bool(mesh.is_watertight)
        volume_reliable = bool(mesh.is_volume)
        volume = Volume(
            cubic_units=float(mesh.volume) if volume_reliable else None,
            reliable=volume_reliable,
        )

        warnings: list[AnalysisWarning] = []
        if not watertight:
            warnings.append(
                AnalysisWarning(
                    code="MESH_NOT_WATERTIGHT",
                    message="The mesh is not closed; its enclosed volume is not reliable.",
                )
            )
        elif not volume_reliable:
            warnings.append(
                AnalysisWarning(
                    code="VOLUME_NOT_RELIABLE",
                    message=(
                        "The mesh is closed but does not satisfy the geometry library's "
                        "volume-validity checks."
                    ),
                )
            )

        return MeshInspection(
            facts=GeometryFacts(
                triangle_count=int(len(mesh.faces)),
                bounding_box=bounding_box,
                watertight=watertight,
                volume=volume,
            ),
            warnings=tuple(warnings),
        )
