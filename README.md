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

## Scale and unit analysis

`AnalyzeScaleAndUnit` reuses an existing `StlAnalysisResult`; it does not read
the STL again. It preserves dimensions observed in model coordinates and
applies a caller-provided scale factor to produce physical dimensions. STL does
not declare its unit, so `physical_unit` is an explicit interpretation, never
a detected or confirmed property of the file.

```python
from agente_impressao_3d.application.analyze_scale_and_unit import (
    AnalyzeScaleAndUnit,
)
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration

stl_result = AnalyzeStl(TrimeshMeshInspector()).execute(Path("model.stl"))
result = AnalyzeScaleAndUnit().execute(
    stl_result,
    ScaleAndUnitConfiguration(scale_factor=100, physical_unit="mm"),
)
print(result.to_dict())
```

## Overhang analysis

`AnalyzeOverhang` analyzes the STL in its supplied orientation. It streams
vectorized normal-Z and area batches, so it does not create one Python object
per face. The initial adapter preserves triangle winding and does not repair or
reorient the mesh.

The build direction is `(0, 0, 1)`. For unit face normal `n`, it defines
`theta = acos(clamp(dot(n, build_direction), -1, 1))`. A face is an overhang
when `dot(n, build_direction) < 0` and `theta >= 90 + threshold_degrees`; the
threshold boundary is included. The implementation uses the equivalent
vectorized test `normal_z < 0 and normal_z <= -sin(threshold_degrees)`.

The result always includes `NORMAL_ORIENTATION_UNVERIFIED`: classification
assumes winding-derived normals point outward, but version one neither verifies
nor corrects their orientation.

```python
from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import (
    TrimeshFaceMetricsReader,
)

result = AnalyzeOverhang(TrimeshFaceMetricsReader()).execute(Path("model.stl"))
print(result.to_dict())
```
