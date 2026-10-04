Kinematic Onshape export. See the top-level README.md and VALIDATION_GUIDE.md in the full bundle.
Use robot.urdf with assets/. robot.onshape-raw.urdf is the preserved raw exporter result.
Run pg3_states.py to obtain nonlinear closed-loop joint states; run validate_robot.py with numpy/trimesh.
Mass, inertia, hardware home and effort/velocity are unmeasured. No dynamics/control acceptance.
