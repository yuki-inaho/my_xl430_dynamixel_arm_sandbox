"""Render actual B-rep tessellations; no image synthesis or proxy geometry."""

from pathlib import Path
from render_cad import render


def make_previews(build, out: Path):
    directory = out / "images"
    directory.mkdir(parents=True, exist_ok=True)
    part = build.parts["elbow_to_wrist_extension_round"]
    render(
        [(part, (0.35, 0.61, 0.71))], directory / "extension_isometric.png", (1, -1, 1)
    )
    for name, shape in [
        ("extension_before", build.local_sources["extension"]),
        ("extension_after", part),
    ]:
        render(
            [(shape, (0.64, 0.70, 0.78))],
            directory / f"{name}.png",
            (1, 0, 0),
            focus=(0, 8.6, 8.5),
            scale=16,
        )
    render(
        [(build.parts["elbow_to_wrist_standoff"], (0.35, 0.61, 0.71))],
        directory / "wrist_standoffs.png",
        (1, -1, -1),
    )
    render(
        [(build.parts["base_idler_clearance"], (0.35, 0.61, 0.71))],
        directory / "base_clearance.png",
        (1, 1, -1),
    )
    shapes = [
        (node.obj.moved(node.loc), node.color.toTuple())
        for node in build.assembly.children
        if node.obj.Solids()
    ]
    render(shapes, directory / "assembly.png", (1, -1, 0.7), size=(1400, 1200))
