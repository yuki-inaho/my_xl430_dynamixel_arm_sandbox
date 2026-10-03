"""Negative geometry tests for the cable-routing concept, not a motion approval."""
from pathlib import Path
import sys
from types import SimpleNamespace

import cadquery as cq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "studies/xl430_lowcost"))
from cable_routing import (
    port_frame, cable_envelope, curve_metrics, intersections, rounded_path,
    straight_driver_envelopes,
    sampled_insertion,
)


def test_port_uses_transformed_header_axis():
    row = SimpleNamespace(loc=cq.Location(cq.Vector(10, 20, 30), cq.Vector(0, 0, 1), 90))
    point, direction = port_frame(row, 8.1)
    assert point.toTuple() == pytest.approx((1.9, 20, 30))
    assert direction.toTuple() == pytest.approx((-1, 0, 0))


def test_wire_through_solid_is_rejected_but_clear_route_is_not():
    edge = cq.Edge.makeLine(cq.Vector(-10, 0, 0), cq.Vector(10, 0, 0))
    tube = cable_envelope(edge, 2)
    block = cq.Workplane().box(4, 4, 4).val()
    assert intersections(tube, {"block": block})[0]["volume_mm3"] > 1
    assert intersections(tube.translate((0, 10, 0)), {"block": block}) == []


def test_small_bend_fails_concept_radius_without_changing_threshold():
    edge = cq.Edge.makeCircle(5)
    metrics = curve_metrics(edge, minimum_radius_mm=15)
    assert metrics["minimum_sampled_radius_mm"] == pytest.approx(5)
    assert metrics["bend_radius_pass"] is False


def test_center_bolt_is_not_a_cable_passage():
    from parts.emergency_center_bolt_idler import make_reference_bolt
    edge = cq.Edge.makeLine(cq.Vector(-6, 0, 0), cq.Vector(12, 0, 0))
    assert intersections(cable_envelope(edge, 3), {"center_bolt": make_reference_bolt().val()})


def test_rounded_path_keeps_radius_and_rejects_short_legs():
    points = [cq.Vector(0, 0, 0), cq.Vector(50, 0, 0), cq.Vector(50, 50, 0)]
    path = rounded_path(points, 15)
    assert curve_metrics(path, 15)["bend_radius_pass"]
    assert curve_metrics(path, 15)["minimum_sampled_radius_mm"] == pytest.approx(15)
    with pytest.raises(ValueError, match="too short"):
        rounded_path([p * 0.1 for p in points], 15)


def driver_parameters():
    return dict(drive_af_mm=2.5, shaft_length_mm=60, handle_diameter_mm=24,
                handle_length_mm=80, withdrawal_mm=40,
                shaft_margin_mm=1, hand_radial_margin_mm=15)


def test_tool_access_rejects_shaft_obstruction_and_grip_obstruction():
    zones = straight_driver_envelopes(cq.Vector(), cq.Vector(1, 0, 0), **driver_parameters())
    shaft_block = cq.Workplane().box(2, 2, 2).translate((20, 0, 0)).val()
    hand_block = cq.Workplane().box(2, 2, 2).translate((100, 20, 0)).val()
    assert intersections(zones["shaft_with_margin"], {"blocked": shaft_block})
    assert intersections(zones["handle_and_hand"], {"blocked": hand_block})
    assert intersections(zones["shaft_with_margin"], {"hand_only": hand_block}) == []
    assert intersections(zones["handle_and_hand"], {"far": hand_block.translate((0, 40, 0))}) == []


def test_tool_access_has_explicit_axis_and_withdrawal_extent():
    zones = straight_driver_envelopes(cq.Vector(10, 20, 30), cq.Vector(0, 0, 1), **driver_parameters())
    shaft, hand = zones["shaft_with_margin"].BoundingBox(), zones["handle_and_hand"].BoundingBox()
    assert (shaft.zmin, shaft.zmax) == pytest.approx((30, 130))
    assert (hand.zmin, hand.zmax) == pytest.approx((90, 210))
    assert shaft.xlen == pytest.approx(2 * (2.5 / (3 ** 0.5) + 1))
    assert hand.xlen == pytest.approx(54)
    with pytest.raises(ValueError):
        straight_driver_envelopes(cq.Vector(), cq.Vector(), **driver_parameters())


def test_cable_can_block_tool_access_even_without_touching_the_bolt():
    zones = straight_driver_envelopes(cq.Vector(), cq.Vector(1, 0, 0), **driver_parameters())
    cable = cable_envelope(cq.Edge.makeLine(cq.Vector(30, -15, 0), cq.Vector(30, 15, 0)), 3)
    assert intersections(zones["shaft_with_margin"], {"harness": cable})


def test_seated_fit_does_not_prove_insertion_path_clear():
    part = cq.Workplane().box(1, 1, 1).val()
    obstacle = part.translate((5, 0, 0))
    assert intersections(part, {"intermediate_wall": obstacle}) == []
    result = sampled_insertion(part, {"intermediate_wall": obstacle}, cq.Vector(1, 0, 0), 10, 1)
    assert result["sampled_clear"] is False
    assert any(pose["offset_mm"] == 5 for pose in result["colliding_samples"])
    assert sampled_insertion(part, {"far": obstacle.translate((0, 3, 0))},
                             cq.Vector(1, 0, 0), 10, 1)["sampled_clear"] is True
