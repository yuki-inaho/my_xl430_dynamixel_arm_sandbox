"""Read STEP assembly occurrences without merging repeated names."""

from dataclasses import dataclass

import cadquery as cq
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.Quantity import Quantity_ColorRGBA
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib


@dataclass
class Occurrence:
    index: int
    path: str
    name: str
    shape: cq.Shape
    loc: cq.Location
    label: object
    color: object = None

    @property
    def world(self):
        return self.shape.moved(self.loc)


def bounds(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, b, False, False)
    return list(b.Get())


def read_step(path):
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    r.SetColorMode(True)
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"Cannot read {path}")
    doc = TDocStd_Document(TCollection_ExtendedString("XCAF"))
    if not r.Transfer(doc):
        raise ValueError("STEP transfer failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label):
        a = TDataStd_Name()
        return (
            a.Get().ToExtString()
            if label.FindAttribute(TDataStd_Name.GetID_s(), a)
            else "unnamed"
        )

    rows = []

    def walk(label, loc, path):
        nm = name(label)
        if st.IsReference_s(label):
            loc = loc * cq.Location(st.GetLocation_s(label))
            ref = TDF_Label()
            st.GetReferredShape_s(label, ref)
        else:
            ref = label
        path = path + "/" + nm
        if st.IsAssembly_s(ref):
            seq = TDF_LabelSequence()
            st.GetComponents_s(ref, seq)
            for j in range(1, seq.Length() + 1):
                walk(seq.Value(j), loc, path)
        else:
            shape = cq.Shape.cast(st.GetShape_s(ref))
            color = None
            for lab in [label, ref]:
                c = Quantity_ColorRGBA()
                if ct.GetColor_s(
                    lab, XCAFDoc_ColorType.XCAFDoc_ColorSurf, c
                ) or ct.GetColor_s(lab, XCAFDoc_ColorType.XCAFDoc_ColorGen, c):
                    color = cq.Color(
                        c.GetRGB().Red(),
                        c.GetRGB().Green(),
                        c.GetRGB().Blue(),
                        c.Alpha(),
                    )
                    break
            rows.append(Occurrence(len(rows), path, nm, shape, loc, ref, color))

    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    for j in range(1, roots.Length() + 1):
        walk(roots.Value(j), cq.Location(), "")
    return doc, st, rows
