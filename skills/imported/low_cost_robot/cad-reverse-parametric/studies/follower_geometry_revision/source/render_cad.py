from pathlib import Path
import cadquery as cq
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
import numpy as np


def render(
    shapes, path, direction=(1, 1, 1), size=(1300, 1000), focus=None, scale=None
):
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.965, 0.973, 0.985)
    for s, col in shapes:
        v, f = s.tessellate(0.05, 0.1)
        v = np.array([p.toTuple() for p in v])
        f = np.array(f, dtype=np.int64)
        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(v, deep=True))
        faces = vtk.vtkCellArray()
        faces.SetCells(
            len(f),
            numpy_to_vtkIdTypeArray(np.c_[np.full(len(f), 3), f].ravel(), deep=True),
        )
        data = vtk.vtkPolyData()
        data.SetPoints(points)
        data.SetPolys(faces)
        norms = vtk.vtkPolyDataNormals()
        norms.SetInputData(data)
        norms.ComputePointNormalsOn()
        norms.SetFeatureAngle(35)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(norms.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*col[:3])
        actor.GetProperty().SetOpacity(col[3] if len(col) > 3 else 1.0)
        actor.GetProperty().SetAmbient(0.25)
        actor.GetProperty().SetDiffuse(0.75)
        actor.GetProperty().SetSpecular(0.16)
        actor.GetProperty().SetSpecularPower(30)
        renderer.AddActor(actor)
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    renderer.ResetCamera()
    b = renderer.ComputeVisiblePropBounds()
    c = (
        np.array([(b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2])
        if focus is None
        else np.array(focus)
    )
    d = np.array(direction, dtype=float)
    d /= np.linalg.norm(d)
    camera.SetFocalPoint(c)
    camera.SetPosition(c + d * 800)
    camera.SetViewUp((0, 0, 1) if abs(d[2]) < 0.95 else (0, 1, 0))
    renderer.ResetCamera()
    if focus is not None:
        camera.SetFocalPoint(c)
        camera.SetPosition(c + d * 800)
    if scale:
        camera.SetParallelScale(scale)
    renderer.ResetCameraClippingRange()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(True)
    window.SetSize(*size)
    window.AddRenderer(renderer)
    window.SetMultiSamples(4)
    window.Render()
    im = vtk.vtkWindowToImageFilter()
    im.SetInput(window)
    im.SetScale(1)
    im.ReadFrontBufferOff()
    im.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(im.GetOutputPort())
    writer.Write()
    window.Finalize()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a supplied STEP to a PNG using its real B-rep."
    )
    parser.add_argument("step", type=Path)
    parser.add_argument("png", type=Path)
    args = parser.parse_args()
    if not args.step.is_file():
        parser.error("Input STEP does not exist")
    args.png.parent.mkdir(parents=True, exist_ok=True)
    shape = cq.importers.importStep(str(args.step)).val()
    render([(shape, (0.7, 0.74, 0.8))], args.png)
