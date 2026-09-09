# agente-impressao-3d

Deterministic STL analysis intended to become the geometry foundation for a
future FDM 3D-printing recommendation agent.

The current capability reports triangle count, an axis-aligned bounding box,
dimensions, watertight status, and volume when the mesh passes the geometry
library's volume-validity checks. It deliberately makes no print-setting or
LLM recommendations.

## Architecture

- `domain`: dependency-free dataclasses and the `MeshInspector` port.
- `application`: the `AnalyzeStl` use case, which attaches explicit analysis
  assumptions to geometry facts.
- `infrastructure`: `TrimeshMeshInspector`, the only component that imports
  `trimesh`.

## Units

STL does not formally define units. The default analysis assumption interprets
coordinates as millimetres, and exposes that assumption in every structured
result. Thus linear measurements are in mm and a reliable volume is in mm³.

## Example

```python
from pathlib import Path

from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.infrastructure.trimesh_inspector import TrimeshMeshInspector

result = AnalyzeStl(TrimeshMeshInspector()).execute(Path("model.stl"))
print(result.to_dict())
```
