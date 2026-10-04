# R3/C7 park-pose lessons (2026-10-04)

Inputs: unchanged R3 donor, four axes Z/−X/+X/+X; forward is world+Y and up is+Z. Coordinate goals refer to elbow→wrist and wrist→ID5 mount/horn direction. This axis is distinct from C7 finger-tip direction and D405 optical axis.

With neutral CAD yawq1=0, preserve the calibrated current shoulderq2. The world forearm pitch is −q2+q3, so horizontal forward gives q3=q2. The wrist→ID5 direction has pitch −q2+q3+q4, so q4=−30°. Independent MuJoCo endpoint checks must give (0,1,0) and (0,√3/2,−1/2); do not treat the joint expressions alone as a test.

Test shoulder examples −20/0/+20° all satisfy those directions. They are CAD examples, not the current user's shoulder angle. CAD theta90° is an illustrative C7 midpoint; physical ID5 neutral needs its own calibrated theta/count.

The latest saved complete raw READ was 2026-10-04 00:21:38 JST: counts1..5=2054,3354,1154,2058,2059, all torqueOFF, portclosed. The user later reported a stable existing pose and a front cushion around5mm. That supports selecting POWER_OFF_SUPPORTED_CURRENT as a named baseline. It does not justify replaying old counts or declaring new CAD zero counts.

R3 self-copy Boolean controls failed for some imported shapes. Keep self-collision/path UNKNOWN until a reliable whole-configuration collision checker exists. MuJoCo's existing viewer has gravity0, contacts disabled, and placeholder inertias. Orientation/render tests do not establish stability.

A naive folded CAD example q3≈−97.78°, with other joints0, puts some long camera/gripper geometry below the table. Reject it as a reconstruction of the current stable arm. The real mounting state, wrist angle and shoulder orientation must be captured.

Related control review found Secondary-ID aliasing and missing motion/hold torque invariants. Position definition must not reuse an unsafe motion command just because an endpoint looks plausible.

2026-10-04 physical staged run: bare R3 arm reached an approximate forward/downward
standby under camera review. IDs2/3/4 held, IDs1/5 stayed read-only. The first
second-stage goal timed out with 36count load sag and stopped without releasing torque.
A separate once-per-joint correction of at most30count reached the original tolerance;
neither the tolerance nor the ID3-only guard was broadened. Returning in reviewed stages
then releasing at the original user-confirmed stable posture showed no large fall:
10sec/200 independent samples, maximum span1count. Cushion load path and actual
supply OUTPUT OFF remained unconfirmed at that cutoff. These counts are case evidence,
not default settings for another arm. Exact CAD world angles remain estimates.

At13:06 the user reported supply power OFF. Three images captured after that report
showed the original folded posture still held. Supply voltage was not measured and no
motor communication occurred after OFF. Physical work was paused at the user's request;
remaining geometric calibration and support/load-path checks were kept outstanding.
