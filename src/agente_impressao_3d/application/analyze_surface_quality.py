"""Scalable deterministic FDM surface quality analysis (v3)."""
from __future__ import annotations
from dataclasses import dataclass
from math import cos, radians, sqrt
from pathlib import Path
import numpy as np
from agente_impressao_3d.domain.models import AnalysisWarning, BoundingBox, Vector3
from agente_impressao_3d.domain.ports import TriangleGeometryReader
from agente_impressao_3d.domain.surface_quality import ConsolidatedSurfaceRegion, CriticalSurfaceRegion, SurfaceQualityAnalysisResult, SurfaceQualityAssumptions, SurfaceQualityConfiguration, SurfaceQualityCostBenefit, SurfaceQualityFacts, SurfaceQualityRegion

@dataclass(frozen=True, slots=True)
class AnalyzeSurfaceQuality:
    """Uses bounded spatial cells; memory is O(number of cells), not O(edges)."""
    triangle_geometry_reader: TriangleGeometryReader
    def execute(self, source_path: Path, configuration: SurfaceQualityConfiguration | None = None) -> SurfaceQualityAnalysisResult:
        config=configuration or SurfaceQualityConfiguration(); allowed=config.allowed_layer_heights
        if not allowed: raise ValueError("no candidate_layer_heights are within the configured limits.")
        source=self.triangle_geometry_reader.open(source_path); bounds=_bounds(source,config.batch_size,config.scale_and_unit.scale_factor)
        if bounds is None: return _empty_result(source_path,config)
        low,high=bounds; shape,cell=_grid_shape(low,high,config); arrays=_CellArrays.create(int(np.prod(shape))); legacy=_LegacyBands.create(config.region_count); totals=np.zeros(3,dtype=np.int64)
        for batch in source.iter_triangle_batches(config.batch_size): _accumulate(batch.vertices*config.scale_and_unit.scale_factor,low,high,shape,cell,arrays,legacy,totals,config)
        regions=_legacy_regions(legacy,low[2],high[2],allowed,config); critical=_spatial_regions(arrays,arrays.area>0,shape,cell,low,high,allowed,config); consolidated=_consolidate_regions(critical,config); cost=_cost_benefit(critical,low[2],high[2],max(allowed)); consolidated_cost=_cost_benefit(consolidated,low[2],high[2],max(allowed))
        warnings=[]
        if totals[1]==0: warnings.append(AnalysisWarning("ZERO_VALID_SURFACE_AREA","No non-degenerate faces were available for surface-quality analysis."))
        elif not critical: warnings.append(AnalysisWarning("NO_GEOMETRICALLY_CRITICAL_PATCHES","No spatial patch exceeded target_geometric_error at the base layer height."))
        return SurfaceQualityAnalysisResult(source_path=str(source_path),configuration=config,assumptions=SurfaceQualityAssumptions(),facts=SurfaceQualityFacts(int(totals[0]),int(totals[1]),int(totals[2]),float(arrays.area.sum()),max(allowed),sum(r.critical for r in regions),len(critical)),regions=tuple(regions),critical_regions=critical,consolidated_regions=consolidated,cost_benefit=cost,consolidated_cost_benefit=consolidated_cost,warnings=tuple(warnings))

@dataclass(slots=True)
class _CellArrays:
    area: np.ndarray; count: np.ndarray; nz_sum: np.ndarray; nz_sq_sum: np.ndarray; z_sum: np.ndarray; z_sq_sum: np.ndarray; nz_z_sum: np.ndarray; min_x: np.ndarray; min_y: np.ndarray; min_z: np.ndarray; max_x: np.ndarray; max_y: np.ndarray; max_z: np.ndarray
    @classmethod
    def create(cls,size:int)->"_CellArrays": return cls(np.zeros(size),np.zeros(size,dtype=np.int64),np.zeros(size),np.zeros(size),np.zeros(size),np.zeros(size),np.zeros(size),*(np.full(size,np.inf) for _ in range(3)),*(np.full(size,-np.inf) for _ in range(3)))
@dataclass(slots=True)
class _LegacyBands:
    face_count: np.ndarray; area: np.ndarray; hist: np.ndarray
    @classmethod
    def create(cls,count:int)->"_LegacyBands": return cls(np.zeros(count,dtype=np.int64),np.zeros(count),np.zeros((count,256)))

def _bounds(source,batch_size:int,scale:float):
    low=np.full(3,np.inf); high=np.full(3,-np.inf); found=False
    for batch in source.iter_triangle_batches(batch_size):
        if batch.face_count:
            points=batch.vertices*scale; low=np.minimum(low,points.min(axis=(0,1))); high=np.maximum(high,points.max(axis=(0,1))); found=True
    return (low,high) if found else None
def _grid_shape(low,high,config):
    extent=np.maximum(high-low,config.spatial_cell_size); cell=config.spatial_cell_size; shape=np.maximum(2,np.ceil(extent/cell).astype(int)+1)
    if int(np.prod(shape))>config.maximum_spatial_cells:
        cell*=(int(np.prod(shape))/config.maximum_spatial_cells)**(1/3); shape=np.maximum(2,np.ceil(extent/cell).astype(int)+1)
        while int(np.prod(shape))>config.maximum_spatial_cells:
            cell*=1.05; shape=np.maximum(2,np.ceil(extent/cell).astype(int)+1)
    return shape,cell
def _accumulate(t,low,high,shape,cell,a,legacy,totals,config):
    if not len(t): return
    totals[0]+=len(t); cross=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]); twice=np.linalg.norm(cross,axis=1); area=twice*.5; valid=np.isfinite(twice)&(twice>0); totals[1]+=valid.sum()
    nz=np.zeros(len(t)); np.divide(np.abs(cross[:,2]),twice,out=nz,where=valid); inclined=valid&(nz<cos(radians(config.horizontal_tolerance_degrees)))&(nz>np.sin(radians(config.vertical_tolerance_degrees))); totals[2]+=inclined.sum()
    centroid=t.mean(axis=1); coord=np.minimum(((centroid-low)/cell).astype(int),shape-1); coord=np.maximum(coord,0); flat=coord[:,0]+shape[0]*(coord[:,1]+shape[1]*coord[:,2]); size=len(a.area); weight=np.where(valid,area,0.)
    a.area+=np.bincount(flat,weights=weight,minlength=size); a.count+=np.bincount(flat,weights=valid,minlength=size).astype(np.int64); a.nz_sum+=np.bincount(flat,weights=weight*nz,minlength=size); a.nz_sq_sum+=np.bincount(flat,weights=weight*nz*nz,minlength=size); a.z_sum+=np.bincount(flat,weights=weight*centroid[:,2],minlength=size); a.z_sq_sum+=np.bincount(flat,weights=weight*centroid[:,2]*centroid[:,2],minlength=size); a.nz_z_sum+=np.bincount(flat,weights=weight*nz*centroid[:,2],minlength=size)
    minimum=t.min(axis=1); maximum=t.max(axis=1)
    for target,values in zip((a.min_x,a.min_y,a.min_z),minimum.T,strict=True): np.minimum.at(target,flat[valid],values[valid])
    for target,values in zip((a.max_x,a.max_y,a.max_z),maximum.T,strict=True): np.maximum.at(target,flat[valid],values[valid])
    band=np.minimum(((centroid[:,2]-low[2])/max(high[2]-low[2],1e-12)*config.region_count).astype(int),config.region_count-1); band=np.maximum(band,0); bucket=np.minimum((nz*255).astype(int),255)
    for index in range(config.region_count):
        mask=inclined&(band==index); legacy.face_count[index]+=np.count_nonzero(band==index); legacy.area[index]+=area[mask].sum(); legacy.hist[index]+=np.bincount(bucket[mask],weights=area[mask],minlength=256)
def _legacy_regions(legacy,zlow,zhigh,allowed,config):
    edges=np.linspace(zlow,zhigh,config.region_count+1); out=[]
    for index in range(config.region_count):
        hist=legacy.hist[index]; p90=None if hist.sum()==0 else float(np.searchsorted(np.cumsum(hist),hist.sum()*.9,side="left")/255); layer=max(allowed) if p90 is None else _legacy_layer(p90,allowed,config.target_normal_step)
        out.append(SurfaceQualityRegion(index,float(edges[index]),float(edges[index+1]),int(legacy.face_count[index]),float(legacy.area[index]),p90,None,layer,0. if p90 is None else layer*p90,layer<max(allowed),"Legacy orientation diagnostic; v3 selection uses geometric error patches."))
    return out
def _legacy_layer(nz,allowed,target):
    for height in sorted(allowed,reverse=True):
        if height*nz<=target:return height
    return min(allowed)
def _spatial_regions(a,occupied,shape,cell,low,high,allowed,config):
    ids=np.flatnonzero(occupied); mean=a.nz_sum[ids]/a.area[ids]; zmean=a.z_sum[ids]/a.area[ids]; zvariance=np.maximum(a.z_sq_sum[ids]/a.area[ids]-zmean*zmean,0); covariance=a.nz_z_sum[ids]/a.area[ids]-mean*zmean; kappa=np.abs(covariance)/np.maximum(zvariance,(cell*.25)**2/12); base=max(allowed); keep=kappa*base*base/8>config.target_geometric_error; ids=ids[keep]; mean=mean[keep]; kappa=kappa[keep]
    if not len(ids): return ()
    labels=_cell_labels(ids,mean,shape); unique,inverse=np.unique(labels,return_inverse=True); count=len(unique); area=np.bincount(inverse,weights=a.area[ids],minlength=count); faces=np.bincount(inverse,weights=a.count[ids],minlength=count).astype(int); kpatch=np.bincount(inverse,weights=a.area[ids]*kappa,minlength=count)/area
    mins=[np.full(count,np.inf) for _ in range(3)]; maxs=[np.full(count,-np.inf) for _ in range(3)]
    for target,values in zip(mins,(a.min_x[ids],a.min_y[ids],a.min_z[ids]),strict=True):np.minimum.at(target,inverse,values)
    for target,values in zip(maxs,(a.max_x[ids],a.max_y[ids],a.max_z[ids]),strict=True):np.maximum.at(target,inverse,values)
    order=np.lexsort((mins[2],mins[1],mins[0],-area)); out=[]; height=max(high[2]-low[2],1e-12)
    for output,index in enumerate(order):
        risks=tuple((h,kpatch[index]*h*h/8/config.target_geometric_error,kpatch[index]*h*h/8) for h in sorted(allowed,reverse=True)); recommended=next((h for h,risk,_ in risks if risk<=1),min(allowed)); bands=tuple(range(max(0,int(np.floor((mins[2][index]-low[2])/height*config.region_count))),min(config.region_count,int(np.floor((maxs[2][index]-low[2])/height*config.region_count))+1)))
        out.append(CriticalSurfaceRegion(output,int(faces[index]),float(area[index]),BoundingBox(Vector3(*map(float,(mins[0][index],mins[1][index],mins[2][index]))),Vector3(*map(float,(maxs[0][index],maxs[1][index],maxs[2][index])))),float(mean[index]),float(recommended),float(kpatch[index]*recommended*recommended/8),float(risks[0][1]),bands,"V3 spatial patch: local normal-Z variation estimates build-Z curvature proxy.",risks,float(kpatch[index])))
    return tuple(out)
def _cell_labels(ids,mean,shape):
    n=len(ids); labels=np.arange(n); x=ids%shape[0]; y=(ids//shape[0])%shape[1]; z=ids//(shape[0]*shape[1]); pairs=[]
    for delta,valid in ((1,x+1<shape[0]),(shape[0],y+1<shape[1]),(shape[0]*shape[1],z+1<shape[2])):
        pos=np.searchsorted(ids,ids+delta); match=valid&(pos<n)&(ids[np.minimum(pos,n-1)]==ids+delta); left=np.flatnonzero(match); right=pos[match]; ok=np.abs(mean[left]-mean[right])<=.35; pairs.append((left[ok],right[ok]))
    for _ in range(max(shape)):
        before=labels.copy()
        for left,right in pairs:
            value=np.minimum(labels[left],labels[right]);np.minimum.at(labels,left,value);np.minimum.at(labels,right,value)
        if np.array_equal(before,labels):break
    return labels
def _consolidate_regions(regions,config):
    """Merge only patch-level AABBs; no triangle or mesh-edge structure is used."""
    if not regions:return ()
    count=len(regions); parent=list(range(count))
    def root(index):
        while parent[index]!=index: parent[index]=parent[parent[index]];index=parent[index]
        return index
    def join(left,right):
        left,right=root(left),root(right)
        if left!=right:parent[max(left,right)]=min(left,right)
    ordered=sorted(range(count),key=lambda index:regions[index].bounds.minimum.x); active=[]; distance=config.region_merge_distance
    for index in ordered:
        current=regions[index]; active=[other for other in active if regions[other].bounds.maximum.x+distance>=current.bounds.minimum.x]
        for other in active:
            candidate=regions[other]
            if candidate.recommended_layer_height!=current.recommended_layer_height:continue
            low=max(min(candidate.severity,current.severity),1e-12); high=max(candidate.severity,current.severity)
            if high/low>config.region_merge_severity_ratio:continue
            gap=_bounds_gap(candidate.bounds,current.bounds)
            if gap[2]>distance or float(np.linalg.norm(gap))>distance:continue
            join(index,other)
        active.append(index)
    groups={}
    for index in range(count):groups.setdefault(root(index),[]).append(index)
    merged=[]
    for members in groups.values():
        patches=[regions[index] for index in members]; area=np.asarray([patch.affected_surface_area for patch in patches]); total=float(area.sum()); severity=np.asarray([patch.severity for patch in patches]); error=np.asarray([patch.estimated_normal_step for patch in patches])
        minimum=np.array([[patch.bounds.minimum.x,patch.bounds.minimum.y,patch.bounds.minimum.z] for patch in patches]).min(axis=0); maximum=np.array([[patch.bounds.maximum.x,patch.bounds.maximum.y,patch.bounds.maximum.z] for patch in patches]).max(axis=0)
        merged.append((total,ConsolidatedSurfaceRegion(0,tuple(sorted(patch.index for patch in patches)),BoundingBox(Vector3(*map(float,minimum)),Vector3(*map(float,maximum))),total,float(severity.max()),float(np.average(severity,weights=area)),patches[0].recommended_layer_height,float(error.max()),float(np.average(error,weights=area)))))
    merged.sort(key=lambda item:(-item[0],item[1].bounds.minimum.x,item[1].bounds.minimum.y,item[1].bounds.minimum.z))
    return tuple(ConsolidatedSurfaceRegion(index,region.original_patch_indices,region.bounds,region.affected_surface_area,region.severity_maximum,region.severity_average,region.recommended_layer_height,region.estimated_geometric_error_maximum,region.estimated_geometric_error_average) for index,(_,region) in enumerate(merged))
def _bounds_gap(left,right):
    return np.array([max(0.,right.minimum.x-left.maximum.x,left.minimum.x-right.maximum.x),max(0.,right.minimum.y-left.maximum.y,left.minimum.y-right.maximum.y),max(0.,right.minimum.z-left.maximum.z,left.minimum.z-right.maximum.z)])
def _cost_benefit(regions,zlow,zhigh,base):
    height=max(0.,zhigh-zlow)
    if not regions or height==0:return SurfaceQualityCostBenefit(None,height,0.,(),None,None,None,None,"No geometrically critical spatial patch requires a variable-layer estimate.")
    ends=sorted({zlow,zhigh,*[v for r in regions for v in (r.bounds.minimum.z,r.bounds.maximum.z)]}); schedule=[]; adaptive=0.
    for lo,hi in zip(ends,ends[1:]):
        active=[r for r in regions if r.bounds.minimum.z<=lo and r.bounds.maximum.z>=hi]; layer=min((r.recommended_layer_height for r in active),default=base);adaptive+=(hi-lo)/layer;schedule.append((lo,hi,layer))
    fine=min(r.recommended_layer_height for r in regions);full=height/fine;intervals=tuple((r.bounds.minimum.z,r.bounds.maximum.z) for r in regions)
    return SurfaceQualityCostBenefit(fine,height,sum(hi-lo for lo,hi,layer in schedule if layer<base),intervals,adaptive,full,full-adaptive,(full-adaptive)/full*100,"Each patch is retained separately; the aggregate schedule resolves overlapping patch Z intervals using the finest active layer. This is geometric layer-equivalent cost, not slicer time.")
def _empty_result(source_path,config):
    base=max(config.allowed_layer_heights);return SurfaceQualityAnalysisResult(source_path=str(source_path),configuration=config,assumptions=SurfaceQualityAssumptions(),facts=SurfaceQualityFacts(0,0,0,0.,base,0,0),regions=(),warnings=(AnalysisWarning("EMPTY_MESH","No faces were found in the STL file."),))
