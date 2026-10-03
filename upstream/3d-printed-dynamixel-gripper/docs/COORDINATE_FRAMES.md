# Calibration coordinate frames

The calibration pipeline names every transform as `destination_from_source`.
Column vectors are used throughout.

| Frame | Handedness | Axes |
| --- | --- | --- |
| CAD / MuJoCo world | right-handed | Z up; model geometry is converted from mm to m at simulation import |
| MuJoCo camera | right-handed | +X right, +Y up, camera looks along -Z |
| OpenCV camera | right-handed | +X right, +Y down, camera looks along +Z |

The fixed camera-frame conversion is
`R_mujoco_camera_from_opencv_camera = diag(1, -1, -1)`. Its determinant is
+1; it is a 180 degree rotation about X, not a reflection.

MuJoCo reports the camera's local-to-world rotation and world position. The
pipeline first constructs `T_world_from_mujoco_camera`, then computes:

```text
T_world_from_camera = T_world_from_mujoco_camera
                    * T_mujoco_camera_from_opencv_camera
T_camera_from_world = inverse(T_world_from_camera)
```

`T_camera_from_world` is the OpenCV extrinsic used for projection. It must not
be replaced by a bare transpose because translation must also be inverted.

For image width `w`, height `h`, and MuJoCo vertical field of view `fovy`, the
synthetic pinhole camera uses square pixels:

```text
fx = fy = (h / 2) / tan(fovy / 2)
cx = w / 2
cy = h / 2
```

Rendering/backend availability is tested separately from these deterministic
frame and projection equations.
