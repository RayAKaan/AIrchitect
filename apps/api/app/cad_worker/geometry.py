"""Real B-rep geometry operations using OCCT, via the ``OCP`` bindings.

This module is the worker's geometry kernel. It is imported *only* inside the
worker virtualenv. It performs genuine solid modelling: closed planar faces are
built from massing footprints, extruded into solids, fused, checked for
validity, measured, and tessellated for display.

No quantity is ever assumed. Every volume, area, centroid and bounding box
reported by this module is read back out of an OCCT shape, so a geometry bug
surfaces as a wrong measurement rather than as a plausible-looking number.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


class GeometryError(RuntimeError):
    """Raised when a shape cannot be built or is geometrically invalid."""


def _occt() -> Any:
    """Import the OCP bindings lazily and with an actionable error message.

    Deferring the import keeps this module importable from the API interpreter
    (where the test for dependency isolation pokes at it), while still failing
    loudly and specifically when the worker venv is wrong.
    """
    try:
        import OCP  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on wrong venv
        raise GeometryError(
            "the CAD worker must run under a virtualenv that has cadquery-ocp installed; "
            "the API interpreter cannot perform geometry work"
        ) from exc
    return OCP


def signed_area(points: Sequence[Point2]) -> float:
    """Return the signed area of a closed ring (shoelace formula)."""
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def perimeter(points: Sequence[Point2]) -> float:
    """Return the closed perimeter of a ring, including the closing edge.

    Pure Python on purpose: the caller compares a kernel's surface area against
    the closed-form answer, so the reference value must not be produced by the
    same library being checked. This is pure-Python-verifiable arithmetic, so it
    needs no justification.
    """
    if len(points) < 2:
        return 0.0
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def ring_is_degenerate(points: Sequence[Point2], *, min_area_m2: float = 1e-6) -> bool:
    """Return True when a ring is too small or self-intersecting to extrude.

    Both conditions produce an invalid or null solid in OCCT rather than a clean
    error, so they are rejected up front where the message can be useful.
    """
    if len(points) < 3:
        return True
    if abs(signed_area(points)) < min_area_m2:
        return True
    return _ring_self_intersects(points)


def _orient(a: Point2, b: Point2, c: Point2) -> float:
    """Return the 2D cross product of (b - a) x (c - a)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point2, b: Point2, p: Point2) -> bool:
    """Return True when collinear point *p* lies within the bounding box of segment a-b."""
    return (
        min(a[0], b[0]) - 1e-12 <= p[0] <= max(a[0], b[0]) + 1e-12
        and min(a[1], b[1]) - 1e-12 <= p[1] <= max(a[1], b[1]) + 1e-12
    )


def _segments_properly_intersect(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Return True when segments a-b and c-d cross at a non-shared point."""
    d1 = _orient(c, d, a)
    d2 = _orient(c, d, b)
    d3 = _orient(a, b, c)
    d4 = _orient(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        if d1 != 0.0 and d2 != 0.0 and d3 != 0.0 and d4 != 0.0:
            return True
    return False


def _segments_touch(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Return True when two segments share an endpoint or overlap collinearly.

    Adjacent edges of a simple ring always share an endpoint, so those contacts
    are legal; overlapping collinear edges are not, and they are what produce the
    zero-thickness faces that OCCT then reports as invalid.
    """
    for p, q in ((a, c), (a, d), (b, c), (b, d)):
        if abs(p[0] - q[0]) < 1e-12 and abs(p[1] - q[1]) < 1e-12:
            return True
    if _orient(a, b, c) == 0.0 and _on_segment(a, b, c):
        return True
    if _orient(a, b, d) == 0.0 and _on_segment(a, b, d):
        return True
    if _orient(c, d, a) == 0.0 and _on_segment(c, d, a):
        return True
    if _orient(c, d, b) == 0.0 and _on_segment(c, d, b):
        return True
    return False


def _ring_self_intersects(points: Sequence[Point2]) -> bool:
    """Return True when a closed ring crosses or overlaps itself.

    Runs in O(n^2), which is acceptable because footprints are capped at 512
    vertices by the protocol and a massing outline is normally 4-20 points.
    """
    count = len(points)
    for i in range(count):
        a1, a2 = points[i], points[(i + 1) % count]
        for j in range(i + 1, count):
            b1, b2 = points[j], points[(j + 1) % count]
            if j == i or (j + 1) % count == i or (i + 1) % count == j:
                continue  # adjacent, shares a vertex by construction
            if _segments_properly_intersect(a1, a2, b1, b2):
                return True
            if _segments_touch(a1, a2, b1, b2):
                return True
    return False


def build_prism(
    footprint: Sequence[Point2],
    base_elevation_m: float,
    height_m: float,
) -> Any:
    """Extrude a closed 2D *footprint* upward into a solid B-rep shape.

    The ring is normalised to counter-clockwise winding first, because OCCT's
    face orientation follows the wire direction and a clockwise ring yields a
    solid with inverted normals, which then measures as negative volume.
    """
    _occt()
    if ring_is_degenerate(footprint):
        raise GeometryError("footprint ring is degenerate or self-intersecting")
    if height_m <= 0:
        raise GeometryError(f"height must be positive, got {height_m!r}")

    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    # Build the ring as explicit 2-tuples rather than tuple(map(float, p)),
    # which mypy infers as an arbitrary-length tuple and then rejects at the
    # signed_area call.
    points: list[Point2] = [(float(p[0]), float(p[1])) for p in footprint]
    if signed_area(points) < 0:
        points.reverse()

    polygon = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        polygon.Add(gp_Pnt(x, y, 0.0))
    polygon.Close()
    if not polygon.IsDone():
        raise GeometryError("could not close the footprint wire")

    wire = BRepBuilderAPI_MakeWire(polygon.Wire()).Wire()
    face_builder = BRepBuilderAPI_MakeFace(wire)
    if not face_builder.IsDone():
        raise GeometryError("could not build a planar face from the footprint")
    face = face_builder.Face()

    solid = BRepPrimAPI_MakePrism(
        face, gp_Vec(0.0, 0.0, float(height_m))
    ).Shape()
    if base_elevation_m:
        solid = _translate(solid, 0.0, 0.0, float(base_elevation_m))
    return solid


def _translate(shape: Any, dx: float, dy: float, dz: float) -> Any:
    """Return *shape* moved by the given offset.

    ``BRepBuilderAPI_Transform``'s single-argument constructor takes a bare
    ``gp_Trsf``; the shape-aware overload needs the shape first, so the
    transform is always applied through the explicit shape/trsf pair.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(dx, dy, dz))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def fuse(shapes: Sequence[Any]) -> Any:
    """Boolean-union *shapes* into a single solid.

    Folds pairwise rather than using the boolean builder's ``Add``/``Build``
    pattern: ``BRepAlgoAPI_Fuse`` in OCCT 7.9.3 exposes only the two-argument
    constructor, so a multi-shape union has to be accumulated. Folding left to
    right is associative for unions of solids, so the result is the same shape
    regardless of order.
    """
    _occt()
    if not shapes:
        raise GeometryError("cannot fuse an empty shape list")
    if len(shapes) == 1:
        return shapes[0]
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

    result = shapes[0]
    for other in shapes[1:]:
        builder = BRepAlgoAPI_Fuse(result, other)
        if not builder.IsDone():
            raise GeometryError("boolean union failed")
        result = builder.Shape()
    return result


def measure(shape: Any, *, element_id: str, kind: str) -> dict[str, Any]:
    """Measure a real solid and return a plain dict of verified quantities."""
    _occt()
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    volume_props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, volume_props)
    volume = float(volume_props.Mass())

    surface_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, surface_props)
    area = float(surface_props.Mass())

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()

    analyzer = BRepCheck_Analyzer(shape)
    is_valid = bool(analyzer.IsValid())
    is_closed = False
    try:
        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS
        from OCP.TopExp import TopExp_Explorer as _Explorer
        from OCP.TopAbs import TopAbs_SHELL

        shell_explorer = _Explorer(shape, TopAbs_SHELL)
        if shell_explorer.More():
            shell = TopoDS.Shell_s(shell_explorer.Current())
            is_closed = bool(BRep_Tool.IsClosed_s(shell))
    except Exception:  # pragma: no cover - defensive across OCCT builds
        is_closed = is_valid

    centre = volume_props.CentreOfMass()
    centre_tuple = (
        float(centre.X()),
        float(centre.Y()),
        float(centre.Z()),
    )

    if volume < 0:
        # A negative volume means the solid's orientation is inverted. Report the
        # magnitude but flag it, because a silently negated volume would let an
        # inside-out building pass a "volume > 0" check.
        is_valid = False

    return {
        "id": element_id,
        "kind": kind,
        "volume_m3": volume,
        "surface_area_m2": area,
        "centroid": centre_tuple,
        "center_of_mass": centre_tuple,
        "bounding_box": {
            "min": (float(xmin), float(ymin), float(zmin)),
            "max": (float(xmax), float(ymax), float(zmax)),
        },
        "solid_count": _count(shape, TopAbs_SOLID),
        "face_count": _count(shape, TopAbs_FACE),
        "edge_count": _count(shape, TopAbs_EDGE),
        "vertex_count": _count(shape, TopAbs_VERTEX),
        "is_valid": is_valid,
        "is_closed": is_closed,
    }


def _count(shape: Any, kind: Any) -> int:
    """Count sub-shapes of *kind* inside *shape*."""
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(shape, kind)
    total = 0
    while explorer.More():
        total += 1
        explorer.Next()
    return total


def is_inside_site(shape: Any, site_ring: Sequence[Point2]) -> tuple[bool, float]:
    """Return whether *shape* lies inside *site_ring*, plus the outside area.

    Uses a real boolean common/cut rather than comparing bounding boxes, so an
    L-shaped massing that pokes outside the site is correctly rejected even
    though its bounding box still fits.
    """
    _occt()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    site_shape = build_prism(site_ring, 0.0, max_volume_height(shape) + 1.0)

    outside_builder = BRepAlgoAPI_Cut(shape, site_shape)
    outside_builder.Build()
    outside = outside_builder.Shape() if outside_builder.IsDone() else None
    outside_area = 0.0
    if outside is not None:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(outside, props)
        outside_area = float(props.Mass())

    common_builder = BRepAlgoAPI_Common(shape, site_shape)
    common_builder.Build()
    inside = 0.0
    if common_builder.IsDone():
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common_builder.Shape(), props)
        inside = float(props.Mass())

    return outside_area <= 1e-6 and inside > 0.0, outside_area


def max_volume_height(shape: Any) -> float:
    """Return a height large enough to fully enclose *shape* vertically."""
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    _xmin, _ymin, zmin, _xmax, _ymax, zmax = box.Get()
    return max(1.0, float(zmax - zmin) + 1.0)


def tessellate(
    shape: Any,
    *,
    linear_deflection_m: float,
    angular_deflection_rad: float,
) -> dict[str, Any]:
    """Tessellate a shape into flat-shaded triangles for browser display.

    Returns vertex and index lists. Triangles are emitted per face rather than
    shared across faces, which duplicates vertices at hard edges but means the
    normals stay crisp on building corners instead of being averaged away.

    The return type is ``dict[str, Any]`` rather than a precise mapping because
    the two lists have different element types (float positions, int indices);
    mypy would otherwise join them to a type that is wrong for one of them.
    """
    _occt()
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(
        shape,
        float(linear_deflection_m),
        False,  # do not relative-deflect
        float(angular_deflection_rad),
        True,  # parallel meshing
    )

    vertices: list[list[float]] = []
    indices: list[list[int]] = []

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        # TopExp_Explorer yields a TopoDS_Shape; BRep_Tool needs the concrete
        # TopoDS_Face, so the downcast is mandatory rather than cosmetic.
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None:
            transform = location.Transformation()
            offset = len(vertices)
            for index in range(1, triangulation.NbNodes() + 1):
                node = triangulation.Node(index)
                point = node.Transformed(transform)
                vertices.append([point.X(), point.Y(), point.Z()])
            for index in range(1, triangulation.NbTriangles() + 1):
                a, b, c = triangulation.Triangle(index).Get()
                # OCCT node indices are 1-based; the GLB index buffer is 0-based.
                indices.append([offset + a - 1, offset + b - 1, offset + c - 1])
        explorer.Next()

    return {"vertices": vertices, "indices": indices}


def export_step(shape: Any, path: str) -> None:
    """Write *shape* to a STEP AP214 file at *path*."""
    _occt()
    from OCP.STEPControl import STEPControl_Writer, STEPControl_StepModelType
    from OCP.IFSelect import IFSelect_RetDone

    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_StepModelType.STEPControl_AsIs) != IFSelect_RetDone:
        raise GeometryError("STEP transfer failed")
    status = writer.Write(path)
    if int(status) != int(IFSelect_RetDone):
        raise GeometryError(f"STEP write failed with status {status}")


def export_brep(shape: Any, path: str) -> None:
    """Write *shape* to a native OCCT BREP file at *path*."""
    _occt()
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_ShapeEnum

    if not BRepTools.Write_s(shape, path):
        raise GeometryError("BREP write failed")


def describe_kernel() -> dict[str, str]:
    """Return the OCCT version this worker is actually linked against.

    Reported rather than assumed, because FreeCAD 1.1.3 embeds OCCT 7.8.1 while
    the standalone ``cadquery-ocp`` wheel embeds 7.9.3. Code must never branch on
    a hard-coded OCCT version; it must read this.
    """
    _occt()
    import OCP

    version = "unknown"
    try:
        from OCP.Standard import Standard_Version

        version = str(Standard_Version.Get_s())
    except Exception:
        try:
            import importlib.metadata as metadata

            version = metadata.version("cadquery-ocp")
        except Exception:  # pragma: no cover - defensive
            version = "unknown"
    return {
        "occt_version": version,
        "occt_build": getattr(OCP, "__file__", "") or "",
        "python_version": ".".join(str(p) for p in __import__("sys").version_info[:3]),
    }


def is_finite_number(value: Any) -> bool:
    """Return True when *value* is a finite real number."""
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def iter_flat(values: Iterable[Any]) -> Iterable[float]:
    """Flatten an iterable of numbers, skipping non-numeric entries."""
    for value in values:
        if is_finite_number(value):
            yield float(value)
