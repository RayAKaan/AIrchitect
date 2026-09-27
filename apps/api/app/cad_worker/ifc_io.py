"""IFC4 export and inspection, owned exclusively by IfcOpenShell.

Division of responsibility in Phase 18: OCCT/FreeCAD own solid geometry and
tessellation; IfcOpenShell owns IFC. That is not a compromise for convenience --
IfcOpenShell's IFC schema handling, spatial structure, classification and property
sets are the parts of the BIM requirement that are genuinely hard to get right,
and duplicating them would create a second, worse implementation.

The API surface of ifcopenshell 0.8.x differs from the widely-copied 0.6/0.7
tutorials in ways that fail loudly rather than silently, all of which are
correctly handled here:

* ``project.create_file`` returns an **empty** file; it does not seed an
  ``IfcProject``, so one must be created explicitly.
* The keyword is ``file=``, not ``ifc_file=``.
* ``pset.add_pset`` takes ``product=``, not ``owner=``.
* ``IfcBuildingElementProxy.PredefinedType`` must be ``ELEMENT`` in IFC4;
  ``BUILDING_ELEMENT_PROXY`` is not a member of that enum.
* ``IfcEntity.GlobalId`` values come from ``ifcopenshell.guid.new()``; there is no
  ``guid`` API usecase.
* ``geometry.add_wall_representation`` *creates* the element rather than accepting
  ``elements=``.

A massing block is not a wall, so building masses are written as
``IfcBuildingElementProxy`` with an ``IfcArbitraryClosedProfileDef`` swept into an
``IfcExtrudedAreaSolid``. That is the correct IFC4 expression of a building mass
and it round-trips cleanly.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

Point2 = tuple[float, float]

#: Material classes mapped to a human-meaningful label recorded in the element's
#: property set.
#:
#: These deliberately do **not** feed ``IfcBuildingElementProxy.PredefinedType``.
#: In IFC4 that enum only admits ELEMENT, PARTIAL, PROVISION_FOR_VOID,
#: USERDEFINED and NOTDEFINED; writing "BUILDING_ELEMENT_PROXY" or "CORE" into it
#: raises ``RuntimeError: Unable to find keyword in schema``. Semantic
#: classification belongs in a property set, which is both valid IFC and what a
#: downstream BIM tool actually reads.
_CLASSIFICATION: dict[str, str] = {
    "conceptual_mass": "Building Mass",
    "floor_plate": "Floor Plate",
    "core": "Circulation Core",
    "site_boundary": "Site Boundary",
}

#: Preflight grid lines, as an IFC4 element class.
_GRID_CLASS = "IfcGridAxis"


class IfcError(RuntimeError):
    """Raised when IFC cannot be written or read."""


def _ifc() -> Any:
    """Import ifcopenshell lazily so this module is safe to import anywhere."""
    try:
        import ifcopenshell
    except ImportError as exc:  # pragma: no cover - depends on wrong venv
        raise IfcError(
            "the CAD worker must run under a virtualenv that has ifcopenshell installed"
        ) from exc
    return ifcopenshell


def _normalise_ring(points: Sequence[Point2]) -> list[Point2]:
    """Return *points* as floats, wound counter-clockwise, ready for a profile."""
    ring = [(float(x), float(y)) for x, y in points]
    total = 0.0
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    if total < 0:
        ring.reverse()
    return ring


def write_ifc(
    path: str,
    *,
    project_name: str,
    site_name: str,
    building_name: str,
    storey_name: str,
    masses: Sequence[dict[str, Any]],
    schema: str = "IFC4",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an IFC model of the given building masses and return a summary.

    *masses* entries require ``id``, ``footprint`` (a sequence of (x, y) pairs),
    ``base_elevation_m`` and ``height_m``; ``name``, ``material_class`` and
    ``storey_index`` are optional.

    Returns a dict describing what was written, which the API records as IFC
    provenance so a later run can prove the file corresponds to this geometry.
    """
    import ifcopenshell.api.project  # noqa: F401 - registers the usecase modules

    ifcopenshell = _ifc()

    run = ifcopenshell.api.run

    if not masses:
        raise IfcError("cannot write an IFC model with no masses")

    try:
        file = ifcopenshell.api.project.create_file(version=schema)
    except Exception as exc:  # pragma: no cover - upstream signature drift
        raise IfcError(f"could not create a {schema} file: {exc}") from exc

    project = run("root.create_entity", file=file, ifc_class="IfcProject", name=project_name)
    owner = file.by_type("IfcOwnerHistory")
    owner_ref = owner[0] if owner else None

    context = run("context.add_context", file=file, context_type="Model")
    site = run("root.create_entity", file=file, ifc_class="IfcSite", name=site_name)
    building = run("root.create_entity", file=file, ifc_class="IfcBuilding", name=building_name)
    storey = run("root.create_entity", file=file, ifc_class="IfcBuildingStorey", name=storey_name)

    run("aggregate.assign_object", file=file, relating_object=project, products=[site])
    run("aggregate.assign_object", file=file, relating_object=site, products=[building])
    run("aggregate.assign_object", file=file, relating_object=building, products=[storey])

    written: list[dict[str, Any]] = []
    for entry in masses:
        element = _add_mass(
            ifcopenshell,
            run,
            file,
            context,
            storey,
            owner_ref,
            name=entry.get("name") or entry["id"],
            footprint=entry["footprint"],
            base_elevation_m=float(entry.get("base_elevation_m", 0.0)),
            height_m=float(entry["height_m"]),
            material_class=entry.get("material_class", "conceptual_mass"),
        )
        written.append(
            {
                "id": entry["id"],
                "global_id": element.GlobalId,
                "entity": element.is_a(),
                "predefined_type": element.PredefinedType,
                "material_class": entry.get("material_class", "conceptual_mass"),
                "classification": _CLASSIFICATION.get(
                    entry.get("material_class", "conceptual_mass"), "Unclassified"
                ),
            }
        )

    summary = {
        "schema": schema,
        "entity_count": len(list(file)),
        "masses": written,
        "spatial_structure": {
            "project": project.GlobalId,
            "site": site.GlobalId,
            "building": building.GlobalId,
            "storey": storey.GlobalId,
        },
    }

    if metadata:
        pset = run("pset.add_pset", file=file, product=storey, name="Pset_AIrchitectMetadata")
        # IfcOpenShell accepts Python values; keep them to scalars so the written
        # file stays readable by tools that do not support complex IfcValue types.
        scalars = {
            key: value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool))
        }
        run("pset.edit_pset", file=file, pset=pset, properties=scalars)
        summary["metadata_pset"] = "Pset_AIrchitectMetadata"
        summary["metadata_keys"] = sorted(scalars)

    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    file.write(path)
    summary["bytes"] = os.path.getsize(path)
    summary["path"] = path
    return summary


def _add_mass(
    ifcopenshell: Any,
    run: Any,
    file: Any,
    context: Any,
    storey: Any,
    owner: Any,
    *,
    name: str,
    footprint: Sequence[Point2],
    base_elevation_m: float,
    height_m: float,
    material_class: str,
) -> Any:
    """Create one ``IfcBuildingElementProxy`` swept from an arbitrary profile."""
    ring = _normalise_ring(footprint)
    profile = file.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=name,
        OuterCurve=file.create_entity(
            "IfcPolyline",
            Points=[
                file.create_entity("IfcCartesianPoint", Coordinates=(x, y))
                for x, y in ring
            ]
            + [file.create_entity("IfcCartesianPoint", Coordinates=(ring[0][0], ring[0][1]))],
        ),
    )
    solid = file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=file.create_entity(
            "IfcAxis2Placement3D",
            Location=file.create_entity(
                "IfcCartesianPoint", Coordinates=(0.0, 0.0, base_elevation_m)
            ),
        ),
        ExtrudedDirection=file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=height_m,
    )
    representation = file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    product_shape = file.create_entity("IfcProductDefinitionShape", Representations=[representation])
    element = file.create_entity(
        "IfcBuildingElementProxy",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=owner,
        Name=name,
        # ELEMENT is the only PredefinedType that means "an ordinary built
        # element" in IFC4. The semantic material class travels in a property
        # set below instead of being forced into a type enum that cannot hold it.
        PredefinedType="ELEMENT",
        ObjectPlacement=file.create_entity(
            "IfcLocalPlacement",
            RelativePlacement=file.create_entity("IfcAxis2Placement3D"),
        ),
        Representation=product_shape,
    )
    run("spatial.assign_container", file=file, products=[element], relating_structure=storey)

    classification = _CLASSIFICATION.get(material_class)
    pset = run("pset.add_pset", file=file, product=element, name="Pset_AIrchitectElement")
    run(
        "pset.edit_pset",
        file=file,
        pset=pset,
        properties={
            "MaterialClass": material_class,
            "Classification": classification or "Unclassified",
            "BaseElevation_m": float(base_elevation_m),
            "Height_m": float(height_m),
        },
    )
    return element


def inspect_ifc(path: str) -> dict[str, Any]:
    """Re-open an IFC file and report its structure.

    This is the round-trip half of the IFC contract: a write that cannot be read
    back with its spatial tree, elements and property sets intact is not a
    successful export, and this is what proves otherwise.
    """
    ifcopenshell = _ifc()
    if not os.path.isfile(path):
        raise IfcError(f"IFC file not found: {path}")
    try:
        model = ifcopenshell.open(path)
    except Exception as exc:
        raise IfcError(f"could not parse {os.path.basename(path)}: {exc}") from exc

    counts: dict[str, int] = {}
    for ifc_class in (
        "IfcProject",
        "IfcSite",
        "IfcBuilding",
        "IfcBuildingStorey",
        "IfcBuildingElementProxy",
        "IfcExtrudedAreaSolid",
        "IfcArbitraryClosedProfileDef",
        "IfcPropertySet",
    ):
        counts[ifc_class] = len(model.by_type(ifc_class))

    psets: dict[str, int] = {}
    for pset in model.by_type("IfcPropertySet"):
        psets[pset.Name] = len(pset.HasProperties)

    return {
        "schema": model.schema_identifier,
        "schema_version": ".".join(str(p) for p in model.schema_version),
        "entity_counts": counts,
        "property_sets": psets,
        "element_names": sorted(
            e.Name for e in model.by_type("IfcBuildingElementProxy") if e.Name
        ),
        "bytes": os.path.getsize(path),
        "ifcopenshell_version": ifcopenshell.version,
    }


def library_version() -> str:
    """Return the IfcOpenShell version this worker is running."""
    return str(_ifc().version)
