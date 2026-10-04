"""Synthetic end-to-end recovery: Gaussian E step and articulated block M step."""
import numpy as np
from scipy.spatial.transform import Rotation
from articulated_filterreg.geometry import State,KinematicChain
from articulated_filterreg.native import GaussianMoments,assemble_blocks

def test_synthetic_scale_pose_and_joint_recovery():
    rng=np.random.default_rng(1204)
    chain=KinematicChain(np.array([[0,0,.02],[-.0002,0,.0563],[-.0002,.0148,.1646],[-.0002,.1049,.1646]]),
                         np.array([[0,0,1],[-1,0,0],[1,0,0],[1,0,0]]))
    centers=np.array([[0,0,.01],[0,0,.05],[0,.005,.12],[0,.065,.165],[0,.15,.18]])
    ref=np.vstack([rng.normal(0,.019,(35,3))+c for c in centers])
    levels=np.repeat(np.arange(5,dtype=np.int32),35)
    truth=State(Rotation.from_rotvec([.25,-.45,.1]).as_matrix(),np.array([.13,-.08,.72]),np.log(1.85),np.deg2rad([8,-17,12,-28]))
    observed=chain.transform(ref,levels,truth)
    initial_delta=np.r_[[.018,-.012,.008],[.008,-.008,.002],-.025,[.035,-.025,.04,-.035]]
    state=truth.increment(initial_delta)
    # The synthetic body labels are known. They disambiguate inter-link overlap
    # but the point-to-point correspondences within each body are NOT supplied.
    for sigma in [.018,.008,.003,.001]:
        filters=[GaussianMoments(observed[levels==b],sigma,mode='direct') for b in range(5)]
        try:
            for _ in range(22):
                x=chain.transform(ref,levels,state);mu=np.empty_like(x);weights=np.ones(len(x))
                for b,f in enumerate(filters):
                    ix=levels==b;m=f.evaluate(x[ix]);mass=np.maximum(m[:,0],1e-300)
                    mu[ix]=m[:,1:4]/mass[:,None]
                    weights[ix]=(m[:,0]>1e-8).astype(float)
                H,g=assemble_blocks(x,mu,weights,levels,chain.space_maps(state))
                delta=np.linalg.solve(H+np.diag(np.maximum(np.diag(H),1e-10)*1e-7),g)
                state=state.increment(delta)
        finally:
            for f in filters:f.close()
    error=np.sqrt(np.mean(np.sum((chain.transform(ref,levels,state)-observed)**2,axis=1)))
    assert error<3e-5
    assert abs(state.scale-truth.scale)/truth.scale<.001
    np.testing.assert_allclose(state.joints,truth.joints,atol=.003)
