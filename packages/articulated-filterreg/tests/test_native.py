import numpy as np
import pytest
from articulated_filterreg.native import GaussianMoments, assemble_blocks

def test_exact_gaussian_moments():
    y=np.array([[0.,0,0],[1.,0,0],[0,1.,0]])
    x=np.array([[.2,.3,0],[.6,0,0]])
    sigma=.7
    k=np.exp(-np.sum((x[:,None]-y[None])**2,axis=-1)/(2*sigma**2))
    expected=k@np.column_stack((np.ones(len(y)),y,np.sum(y*y,axis=1)))
    with GaussianMoments(y,sigma,mode='direct') as f:
        np.testing.assert_allclose(f.evaluate(x),expected,rtol=1e-13,atol=1e-14)

def test_lattice_constant_reproduction_and_locality():
    rng=np.random.default_rng(4)
    y=rng.normal(size=(250,3))*.03+np.array([.1,.2,.6])
    with GaussianMoments(y,.04) as f:
        m=f.evaluate(y)
    assert np.isfinite(m).all() and (m[:,0]>0).all()
    mu=m[:,1:4]/m[:,0,None]
    assert np.max(np.linalg.norm(mu-y,axis=1))<.13
    assert np.all(mu>=y.min(0)-1e-12) and np.all(mu<=y.max(0)+1e-12)

def test_native_invalid_inputs():
    for y,s in [(np.zeros((0,3)),1),(np.zeros((3,2)),1),(np.ones((3,3))*np.nan,1),(np.zeros((3,3)),0)]:
        with pytest.raises((ValueError,RuntimeError)):
            GaussianMoments(y,s)
    with GaussianMoments(np.zeros((3,3)),1) as f:
        with pytest.raises(ValueError):f.evaluate(np.zeros((2,2)))
    with pytest.raises(RuntimeError):f.evaluate(np.zeros((2,3)))

def test_link_block_reduction_matches_point_jacobian():
    rng=np.random.default_rng(1);n,b,d=71,4,11
    x=rng.normal(size=(n,3));mu=rng.normal(size=(n,3));w=rng.uniform(size=n)
    levels=rng.integers(0,b,size=n,dtype=np.int32);S=rng.normal(size=(b,7,d))
    H,g=assemble_blocks(x,mu,w,levels,S)
    expected_H=np.zeros((d,d));expected_g=np.zeros(d)
    for i,p in enumerate(x):
        px,py,pz=p
        A=np.array([[0,pz,-py,1,0,0,px],[-pz,0,px,0,1,0,py],[py,-px,0,0,0,1,pz]])
        J=A@S[levels[i]]
        expected_H+=w[i]*J.T@J; expected_g+=w[i]*J.T@(mu[i]-p)
    np.testing.assert_allclose(H,expected_H,rtol=1e-12,atol=1e-11)
    np.testing.assert_allclose(g,expected_g,rtol=1e-12,atol=1e-11)


def test_body_index_overflow_is_rejected_before_int32_conversion():
    """A large input must not wrap to a seemingly valid native body index."""
    points = np.ones((1, 3))
    maps = np.zeros((1, 7, 1))
    for dtype in (np.int64, np.uint64):
        bodies = np.array([2**32], dtype=dtype)
        with pytest.raises(ValueError):
            assemble_blocks(points, points, np.ones(1), bodies, maps)
