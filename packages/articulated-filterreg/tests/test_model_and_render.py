from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation
from articulated_filterreg.geometry import CadModel
from articulated_filterreg.render import rasterize
ROOT=Path(__file__).resolve().parents[1]

def test_derived_urdf_matches_reference_space_fk():
    m=CadModel.load(ROOT/'model/bare_arm.npz')
    xml=ET.parse(ROOT/'model/bare_arm_r3.urdf').getroot()
    joints=xml.findall('joint');assert len(joints)==4
    assert len(xml.findall('link'))==5
    q=np.array([.2,-.31,.44,-.51]);actual=m.chain.fk(q)
    T=np.eye(4);origin=np.zeros(3)
    for i,j in enumerate(joints):
        xyz=np.fromstring(j.find('origin').attrib['xyz'],sep=' ')
        axis=np.fromstring(j.find('axis').attrib['xyz'],sep=' ')
        origin+=xyz
        local=np.eye(4);local[:3,3]=xyz
        rot=np.eye(4);rot[:3,:3]=Rotation.from_rotvec(axis*q[i]).as_matrix()
        T=T@local@rot
        reference_frame=np.eye(4);reference_frame[:3,3]=-origin
        np.testing.assert_allclose(T@reference_frame,actual[i+1],atol=1e-12)
    for level in range(5):
        faces=m.faces[m.face_level==level]
        assert np.all(m.vertex_level[faces]==level)
    assert set(m.units)=={'M01','M02','M03','M04','M05','P01_base','P02_yaw_carrier','P03_shoulder_XL430','P04_extension_XL430','P05_wrist_XL430'}

def test_zbuffer_front_triangle_occludes_back():
    K=np.array([[10.,0,10],[0,10,10],[0,0,1.]])
    tri=np.array([[-.5,-.5,1],[.5,-.5,1],[0,.5,1]])
    vertices=np.vstack((tri*2,tri));faces=np.array([[0,1,2],[3,4,5]],np.int32)
    d,i=rasterize(vertices,faces,K,21,21)
    assert i[9,10]==1 and abs(d[9,10]-1)<1e-12
    assert i[0,0]==-1 and np.isinf(d[0,0])
    d2,i2=rasterize(vertices,faces[::-1].copy(),K,21,21)
    assert i2[9,10]==0
    np.testing.assert_array_equal(d,d2)
