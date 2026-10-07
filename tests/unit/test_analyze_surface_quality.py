from pathlib import Path
import numpy as np
import pytest
from agente_impressao_3d.application.analyze_surface_quality import AnalyzeSurfaceQuality
from agente_impressao_3d.application.analyze_surface_quality import _grid_shape
from agente_impressao_3d.application.analyze_surface_quality import _consolidate_regions
from agente_impressao_3d.domain.models import BoundingBox, Vector3
from agente_impressao_3d.domain.surface_quality import CriticalSurfaceRegion
from agente_impressao_3d.domain.orientation import TriangleGeometryBatch
from agente_impressao_3d.domain.surface_quality import SurfaceQualityConfiguration

class Reader:
    def __init__(self, triangles): self.triangles=triangles
    def open(self, source_path): return self
    def iter_triangle_batches(self, batch_size): yield TriangleGeometryBatch(self.triangles)

def analyze(triangles, **kwargs):
    return AnalyzeSurfaceQuality(Reader(np.asarray(triangles,float))).execute(Path("synthetic.stl"),SurfaceQualityConfiguration(**kwargs))

def dome(radius=1.,rings=5,segments=24):
    points=[(0.,0.,radius)]; faces=[]
    for ring in range(1,rings+1):
        radial=radius*.95*ring/rings
        points += [(radial*np.cos(i*2*np.pi/segments),radial*np.sin(i*2*np.pi/segments),np.sqrt(radius*radius-radial*radial)) for i in range(segments)]
    for i in range(segments): faces.append((0,1+i,1+(i+1)%segments))
    for ring in range(1,rings):
        first=1+(ring-1)*segments; second=first+segments
        for i in range(segments): faces += [(first+i,second+i,second+(i+1)%segments),(first+i,second+(i+1)%segments,first+(i+1)%segments)]
    return np.asarray(points)[np.asarray(faces)]

def test_vertical_and_inclined_planes_are_not_automatically_high_risk():
    vertical=[[[0,0,0],[0,1,0],[0,0,2]]]
    inclined=[[[3,0,0],[4,0,1],[3,1,0]]]
    result=analyze(vertical+inclined,spatial_cell_size=.5)
    assert result.critical_regions == ()
    assert result.facts.inclined_face_count == 1

def test_dome_error_increases_quadratically_with_layer_height_and_can_recommend_012():
    result=analyze(dome(),spatial_cell_size=.5,target_geometric_error=.0018)
    assert result.critical_regions
    patch=result.critical_regions[0]
    risks={height:(risk,error) for height,risk,error in patch.risk_by_layer}
    assert risks[.16][1] > risks[.12][1] > risks[.10][1] > risks[.08][1]
    assert patch.recommended_layer_height == pytest.approx(.12)

def test_vertical_cylinder_has_no_build_z_curvature_risk():
    angles=np.linspace(0,2*np.pi,17); points=[]; faces=[]
    for z in (0.,3.): points += [(np.cos(a),np.sin(a),z) for a in angles[:-1]]
    for i in range(16): faces += [(i,(i+1)%16,16+(i+1)%16),(i,16+(i+1)%16,16+i)]
    result=analyze(np.asarray(points)[np.asarray(faces)],spatial_cell_size=.5)
    assert result.critical_regions == ()

def test_inclined_cylinder_is_not_marked_without_normal_z_variation():
    # Translating every ring in X with Z creates an inclined cylindrical wall,
    # while its normal_z remains locally constant along the extrusion.
    angles=np.linspace(0,2*np.pi,17); points=[]; faces=[]
    for z in (0.,3.): points += [(np.cos(a)+z*.4,np.sin(a),z) for a in angles[:-1]]
    for i in range(16): faces += [(i,(i+1)%16,16+(i+1)%16),(i,16+(i+1)%16,16+i)]
    assert analyze(np.asarray(points)[np.asarray(faces)],spatial_cell_size=.5).critical_regions == ()

def test_disconnected_curved_domes_in_same_z_remain_independent():
    first=dome(); second=dome()+np.array([10.,0.,0.])
    result=analyze(np.concatenate((first,second)),spatial_cell_size=.5,target_geometric_error=.0018)
    assert len(result.critical_regions) >= 2
    assert any(region.bounds.maximum.x < 5 for region in result.critical_regions)
    assert any(region.bounds.minimum.x > 5 for region in result.critical_regions)
    assert len(result.cost_benefit.critical_z_intervals) >= 2

def test_limits_are_respected_and_no_candidate_is_rejected():
    result=analyze(dome(),spatial_cell_size=.5,target_geometric_error=.0018,minimum_layer_height=.12,maximum_layer_height=.16)
    assert all(region.recommended_layer_height >= .12 for region in result.critical_regions)
    with pytest.raises(ValueError,match="no candidate_layer_heights"):
        analyze(dome(),minimum_layer_height=.17,maximum_layer_height=.18)

def test_spatial_grid_is_hard_capped_independently_of_triangle_count():
    config=SurfaceQualityConfiguration(spatial_cell_size=.001,maximum_spatial_cells=500)
    shape,_=_grid_shape(np.array([0.,0.,0.]),np.array([100.,80.,60.]),config)
    assert int(np.prod(shape)) <= 500

def patch(index,x0,x1,z0,z1,layer=.12,severity=2.):
    return CriticalSurfaceRegion(index,10,5.,BoundingBox(Vector3(x0,0.,z0),Vector3(x1,1.,z1)),.5,layer,.0005,severity,(0,),"test",((.16,severity,.001),),.2)

def test_consolidates_nearby_compatible_patches_and_preserves_audit_ids():
    regions=_consolidate_regions((patch(0,0,1,0,2),patch(1,2,3,1,3)),SurfaceQualityConfiguration(region_merge_distance=1.1))
    assert len(regions)==1
    assert regions[0].original_patch_indices == (0,1)
    assert regions[0].affected_surface_area == pytest.approx(10.)

def test_does_not_consolidate_separated_or_different_layer_patches():
    config=SurfaceQualityConfiguration(region_merge_distance=1.)
    assert len(_consolidate_regions((patch(0,0,1,0,2),patch(1,5,6,0,2)),config))==2
    assert len(_consolidate_regions((patch(0,0,1,0,2),patch(1,1.2,2,0,2,layer=.10)),config))==2

def test_consolidates_z_overlapping_patches_but_keeps_independent_same_z_regions():
    config=SurfaceQualityConfiguration(region_merge_distance=1.)
    merged=_consolidate_regions((patch(0,0,1,0,3),patch(1,1.5,2.5,2,5),patch(2,20,21,0,3)),config)
    assert len(merged)==2
    assert any(region.original_patch_indices == (0,1) for region in merged)
