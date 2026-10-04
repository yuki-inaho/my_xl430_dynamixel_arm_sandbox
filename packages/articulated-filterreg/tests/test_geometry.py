import numpy as np
from scipy.spatial.transform import Rotation
from articulated_filterreg.geometry import State,KinematicChain,projection

def chain():
    return KinematicChain(np.array([[0,0,.02],[-.0002,0,.0563],[-.0002,.0148,.1646],[-.0002,.1049,.1646]]),
                          np.array([[0,0,1],[-1,0,0],[1,0,0],[1,0,0]]))

def test_neutral_fk_is_identity():
    c=chain();np.testing.assert_allclose(c.fk(np.zeros(4)),np.broadcast_to(np.eye(4),(5,4,4)),atol=1e-14)

def test_similarity_and_articulated_jacobian_finite_difference():
    c=chain();rng=np.random.default_rng(8)
    p=rng.normal(size=(15,3))*.1;lv=np.arange(15,dtype=np.int32)%5
    s=State(Rotation.from_rotvec([.2,-.6,.1]).as_matrix(),np.array([.1,.2,.8]),np.log(1.7),np.array([.1,-.4,-.3,.2]))
    x=c.transform(p,lv,s);S=c.space_maps(s)
    J=np.zeros((len(x),3,11))
    for i,(px,py,pz) in enumerate(x):
        A=np.array([[0,pz,-py,1,0,0,px],[-pz,0,px,0,1,0,py],[py,-px,0,0,0,1,pz]])
        J[i]=A@S[lv[i]]
    for k in range(11):
        d=np.eye(11)[k]*1e-7
        fd=(c.transform(p,lv,s.increment(d))-c.transform(p,lv,s.increment(-d)))/(2e-7)
        np.testing.assert_allclose(fd,J[:,:,k],atol=3e-8,rtol=1e-6)

def test_projection_inverse():
    K=np.array([[683.473,0,325.5],[0,684.831,183],[0,0,1.]])
    pixels=np.array([[0.,0],[651,366],[260,94]])
    z=np.array([.8,1,.52]);p=np.column_stack(((pixels[:,0]-K[0,2])*z/K[0,0],(pixels[:,1]-K[1,2])*z/K[1,1],z))
    np.testing.assert_allclose(projection(p,K),pixels,atol=1e-10)

def test_invalid_state_and_fractional_body_rejected():
    import pytest
    with pytest.raises(ValueError):State(np.eye(3)*2,np.zeros(3),0,np.zeros(4))
    with pytest.raises(ValueError):State(np.eye(3),np.zeros(3),1000,np.zeros(4))
    c=chain();s=State(np.eye(3),np.zeros(3),0,np.zeros(4))
    with pytest.raises(ValueError):c.transform(np.zeros((1,3)),np.array([.5]),s)
    with pytest.raises(ValueError):projection(np.full((2,3),np.nan),np.eye(3))

def test_state_vector_roundtrip():
    s=State(Rotation.from_rotvec([.2,-.1,.4]).as_matrix(),np.array([.2,.1,.8]),.5,np.array([.1,.2,.3,.4]))
    ss=State.from_vector(s.vector())
    np.testing.assert_allclose(ss.rotation,s.rotation,atol=1e-15)
    np.testing.assert_allclose(ss.vector(),s.vector(),atol=1e-15)
