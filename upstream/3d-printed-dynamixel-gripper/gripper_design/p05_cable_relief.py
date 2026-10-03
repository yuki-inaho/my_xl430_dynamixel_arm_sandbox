"""Two local sidewall slots; diagnostic wires are not a qualified harness."""

import cadquery as cq

from gripper_design.build import _source_rows
from scripts.probe_pg3_wire_routes import quarter_route, terminal_centres

WINDOW_RADIUS_MM = 1.5
WINDOW_Y_MM = 151.0
WIRE_Z_MM = (176.2, 178.7, 181.2)
SIDE_WALLS_X_MM = ((14.05, 18.05), (-18.45, -14.45))


def original():
    return next(r.world for r in _source_rows() if r.name == "P05_wrist_XL430")


def change_mask():
    masks = []
    for lo, hi in SIDE_WALLS_X_MM:
        start, depth = lo - 1, hi - lo + 2
        ends = [
            cq.Solid.makeCylinder(WINDOW_RADIUS_MM, depth, (start, WINDOW_Y_MM, z), (1, 0, 0))
            for z in (WIRE_Z_MM[0], WIRE_Z_MM[-1])
        ]
        middle = cq.Solid.makeBox(
            depth,
            2 * WINDOW_RADIUS_MM,
            WIRE_Z_MM[-1] - WIRE_Z_MM[0],
            (start, WINDOW_Y_MM - WINDOW_RADIUS_MM, WIRE_Z_MM[0]),
        )
        masks.append(middle.fuse(*ends))
    return cq.Compound.makeCompound(masks)


def protected():
    # Preserve the existing hole neighbourhoods and the complete bridge/clamp region.
    regions = [cq.Solid.makeBox(100, 144.4, 300, (-50, 0, 0))]
    for lo, hi in SIDE_WALLS_X_MM:
        for y in (158.9, 170.9):
            for z in (168.6, 192.6):
                regions.append(cq.Solid.makeCylinder(1.2 + 2.5, hi - lo, (lo, y, z), (1, 0, 0)))
    return cq.Compound.makeCompound(regions)


def candidate():
    source = original()
    mask = change_mask()
    if source.intersect(mask).intersect(protected()).Volume() > 1e-4:
        raise ValueError("P05 mask enters a protected fastening or clamp region")
    shape = source.cut(mask)
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("P05 relief is invalid or disconnected")
    return shape


def diagnostic_wires(*, exit_y=WINDOW_Y_MM):
    rows = {r.name: r.world for r in _source_rows()}
    result = {}
    for port in (3, 4):
        points, pcb = terminal_centres(rows[f"M05_ref{port:02d}"])
        for index, point in enumerate(points):
            wire, _ = quarter_route(
                [point[0], pcb - 8.7, point[2]],
                1.9,
                1.2,
                exit_y,
                0,
                1 if port == 3 else -1,
                25 if port == 3 else -25.4,
            )
            result[f"WIRE_ASSUMED_port{port}_{index}"] = wire
    return result
