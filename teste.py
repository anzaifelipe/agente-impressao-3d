from pathlib import Path

from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.infrastructure.trimesh_inspector import (
    TrimeshMeshInspector,
)

analyzer = AnalyzeStl(
    TrimeshMeshInspector()
)

result = analyzer.execute(
    Path("/Users/felipeanzai/Downloads/Hi3D_Untitled_allparts_20260821_081332.stl")
)

print(result.to_dict())
