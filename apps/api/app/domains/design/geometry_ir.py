from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field
from app.domains.design.config import DesignEngineConfig
from app.domains.design.strategies import DesignCandidate


class Transform(BaseModel):
    translation: tuple[float, float, float] = (0, 0, 0)
    rotation_degrees: tuple[float, float, float] = (0, 0, 0)
    scale: tuple[float, float, float] = (1, 1, 1)


class GeometryObject(BaseModel):
    id: str
    type: Literal["site_boundary", "setback_boundary", "building_mass", "floor_plate", "core", "structural_grid", "dimension"]
    parent_id: str | None = None
    transform: Transform = Field(default_factory=Transform)
    dimensions: dict[str, float]
    material_class: str
    source_reference: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeometryIR(BaseModel):
    schema_version: str = "1.0.0"
    units: Literal["m"] = "m"
    coordinate_system: str = "local_cartesian_z_up"
    site: GeometryObject
    setbacks: list[GeometryObject] = Field(default_factory=list)
    masses: list[GeometryObject]
    floor_plates: list[GeometryObject]
    cores: list[GeometryObject]
    structural_grids: list[GeometryObject]
    dimensions: list[GeometryObject]
    parking: dict[str, Any]
    orientation_degrees: float | None = None
    metadata: dict[str, Any]


class GeometryValidationResult(BaseModel):
    valid: bool
    checks: list[dict[str, Any]]
    errors: list[str]


class MassingGeometryEngine:
    name = "MassingGeometryEngine"

    def __init__(self, config: DesignEngineConfig): self.config = config

    def generate(self, candidate: DesignCandidate, alternative_ref: str, site_width: float, site_depth: float) -> GeometryIR:
        p, m = candidate.parameters, candidate.metrics
        width, depth = float(p["footprint_width_m"]), float(p["footprint_depth_m"])
        floors, floor_height = int(p["floor_count"]), float(p["floor_to_floor_height_m"])
        x, y = (site_width - width) / 2, (site_depth - depth) / 2
        source = f"design_alternative:{alternative_ref}"
        site = GeometryObject(id="site", type="site_boundary", dimensions={"width": site_width, "depth": site_depth, "area": site_width * site_depth},
            material_class="site", source_reference="resolved_design_context",
            metadata={"boundary_kind": "rectangle", "approximation": candidate.assumptions})
        setbacks = []
        setback = float(p.get("setback_m", 0))
        if setback > 0:
            setbacks.append(GeometryObject(id="setback", type="setback_boundary",
                transform=Transform(translation=(setback, setback, 0)),
                dimensions={"width": site_width - 2*setback, "depth": site_depth - 2*setback},
                material_class="constraint", source_reference="design_constraint:setback"))
        mass = GeometryObject(id="mass-1", type="building_mass", parent_id="site",
            transform=Transform(translation=(x, y, 0), rotation_degrees=(0, 0, float(p.get("orientation_degrees") or 0))),
            dimensions={"width": width, "depth": depth, "height": float(m["building_height_m"])},
            material_class="conceptual_mass", source_reference=source,
            metadata={"preliminary": True, "not_for_construction": True})
        plates = [GeometryObject(id=f"floor-{level}", type="floor_plate", parent_id="mass-1",
            transform=Transform(translation=(x, y, (level-1)*floor_height)),
            dimensions={"width": width, "depth": depth, "thickness": .25, "elevation": (level-1)*floor_height,
                        "area": width*depth}, material_class="floor_plate", source_reference=source,
            metadata={"level_number": level}) for level in range(1, floors+1)]
        core_ratio = float(p["core_ratio"]); core_width = width * core_ratio ** .5; core_depth = depth * core_ratio ** .5
        cores = [GeometryObject(id="core-1", type="core", parent_id="mass-1",
            transform=Transform(translation=(x+(width-core_width)/2, y+(depth-core_depth)/2, 0)),
            dimensions={"width": core_width, "depth": core_depth, "height": float(m["building_height_m"])},
            material_class="preliminary_core", source_reference=source,
            metadata={"preliminary": True, "not_engineering_approved": True})]
        grid = self._grid(x, y, width, depth, source)
        dims = [GeometryObject(id="dim-width", type="dimension", parent_id="mass-1", dimensions={"value": width},
                    material_class="annotation", source_reference=source, metadata={"axis":"x","label":f"{width:.2f} m"}),
                GeometryObject(id="dim-depth", type="dimension", parent_id="mass-1", dimensions={"value": depth},
                    material_class="annotation", source_reference=source, metadata={"axis":"y","label":f"{depth:.2f} m"}),
                GeometryObject(id="dim-height", type="dimension", parent_id="mass-1", dimensions={"value":float(m["building_height_m"])},
                    material_class="annotation", source_reference=source, metadata={"axis":"z","label":f"{float(m['building_height_m']):.2f} m"})]
        return GeometryIR(site=site, setbacks=setbacks, masses=[mass], floor_plates=plates, cores=cores,
            structural_grids=grid, dimensions=dims,
            parking={"capacity": m.get("parking_count"), "geometry_status": "NOT_GENERATED",
                "note": "Capacity metric only; no parking layout is claimed."},
            orientation_degrees=p.get("orientation_degrees"), metadata={"alternative_reference":alternative_ref,
                "geometry_engine_name":self.name, "geometry_engine_version":self.config.geometry_engine_version,
                "preliminary":True, "human_review_required":True})

    def _grid(self, x: float, y: float, width: float, depth: float, source: str) -> list[GeometryObject]:
        spacing = self.config.preliminary_grid_spacing_m
        x_bays=max(1,round(width/spacing)); y_bays=max(1,round(depth/spacing))
        x_spacing=width/x_bays; y_spacing=depth/y_bays
        return [GeometryObject(id="grid-1", type="structural_grid", parent_id="mass-1",
            transform=Transform(translation=(x,y,0)), dimensions={"width":width,"depth":depth,
                "x_bays":float(x_bays),"y_bays":float(y_bays),"x_spacing":x_spacing,"y_spacing":y_spacing},
            material_class="preliminary_design_grid", source_reference=f"{source}:engine_default_grid",
            metadata={"preliminary":True,"not_engineering_approved":True})]


class GeometryValidator:
    def __init__(self, config: DesignEngineConfig): self.config=config

    def validate(self, geometry: GeometryIR, candidate: DesignCandidate) -> GeometryValidationResult:
        checks=[]; errors=[]
        def check(code: str, passed: bool, actual: Any, expected: Any):
            checks.append({"code":code,"status":"PASS" if passed else "FAIL","actual":actual,"expected":expected})
            if not passed: errors.append(code)
        site=geometry.site.dimensions; mass=geometry.masses[0]; dims=mass.dimensions; p=candidate.parameters; metrics=candidate.metrics
        positive=all(float(v)>0 for v in (site["width"],site["depth"],dims["width"],dims["depth"],dims["height"]))
        check("positive_dimensions",positive,dims,"> 0")
        tx,ty,_=mass.transform.translation
        inside=tx>=-1e-6 and ty>=-1e-6 and tx+dims["width"]<=site["width"]+1e-6 and ty+dims["depth"]<=site["depth"]+1e-6
        check("building_inside_site",inside,{"x":tx,"y":ty,"width":dims["width"],"depth":dims["depth"]},site)
        check("floor_count_consistent",len(geometry.floor_plates)==int(p["floor_count"]),len(geometry.floor_plates),p["floor_count"])
        gfa=sum(float(f.dimensions["area"]) for f in geometry.floor_plates)
        check("gfa_consistent",abs(gfa-float(metrics["gross_floor_area_m2"]))<1e-4,gfa,metrics["gross_floor_area_m2"])
        footprint=float(dims["width"])*float(dims["depth"])
        check("footprint_consistent",abs(footprint-float(metrics["building_footprint_m2"]))<1e-4,footprint,metrics["building_footprint_m2"])
        coverage=footprint/(float(site["width"])*float(site["depth"]))
        check("coverage_consistent",abs(coverage-float(metrics["site_coverage_ratio"]))<1e-6,coverage,metrics["site_coverage_ratio"])
        expected_height=int(p["floor_count"])*float(p["floor_to_floor_height_m"])
        check("height_consistent",abs(float(dims["height"])-expected_height)<1e-6,dims["height"],expected_height)
        objects=1+len(geometry.setbacks)+len(geometry.masses)+len(geometry.floor_plates)+len(geometry.cores)+len(geometry.structural_grids)+len(geometry.dimensions)
        check("object_limit",objects<=self.config.max_scene_objects,objects,self.config.max_scene_objects)
        max_coord=max(float(site["width"]),float(site["depth"]),float(dims["height"]))
        check("coordinate_limit",max_coord<=self.config.max_coordinate_m,max_coord,self.config.max_coordinate_m)
        refs=all(obj.source_reference for group in [geometry.masses,geometry.floor_plates,geometry.cores,geometry.structural_grids] for obj in group)
        check("source_references_present",refs,refs,True)
        return GeometryValidationResult(valid=not errors,checks=checks,errors=errors)
