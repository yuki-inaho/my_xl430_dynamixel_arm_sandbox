"""Check one requested pose against the current CAD; never a path certificate.

Example: python source/check_pose.py 0 0 -30 -30 0 25
Known excessive negative elbow+wrist folds are stopped before CAD calculation.
Passing that screening rule alone NEVER constitutes acceptance.
"""
import argparse,json,math,sys
from motion import Checker
RANGES=((-180,180),(-40,40),(-60,60),(-60,60),(-90,90),(0,50))

def admission_error(q):
    if len(q)!=6 or any(not math.isfinite(x) for x in q):return 'six finite joint angles are required'
    if any(not a<=x<=b for x,(a,b) in zip(q,RANGES)):return 'outside characterised angular ranges'
    if q[2]+q[3]<-90:return 'conservative fold screening: q3+q4 must be >= -90 degrees'
    return None

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('q',type=float,nargs=6);args=parser.parse_args()
    result={'q_deg':args.q,'continuous_motion_proven':False,'manufacturing_approved':False}
    error=admission_error(args.q)
    if error:
        result.update(passed=False,blocked_reason=error);print(json.dumps(result,indent=2));return 2
    try:
        bad=Checker().pose(args.q);result.update(passed=not bad,collisions=bad,scope='single_pose_BREP_self_collision_only_no_cables_new_fasteners_or_environment')
    except Exception as exc:result.update(passed=False,error=str(exc))
    print(json.dumps(result,indent=2));return 0 if result['passed'] else 2
if __name__=='__main__':sys.exit(main())
