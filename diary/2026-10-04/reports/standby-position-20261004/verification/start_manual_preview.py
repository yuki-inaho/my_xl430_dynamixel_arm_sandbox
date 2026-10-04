"""Manual-only standby preview. Never configures a READ/hardware bridge."""
import argparse
import shutil
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation-root",type=Path,required=True)
    parser.add_argument("--port",type=int,default=18084)
    args=parser.parse_args()
    root=args.simulation_root.resolve()
    sys.path.insert(0,str(root/"simulation/current_arm_viewer"))
    import server
    donor=server.MODEL_DIR
    output=root/"outputs/standby-position-20261004"
    output.mkdir(exist_ok=True)
    for name in ("scene.xml","model-provenance.json"):
        shutil.copyfile(donor/name,output/name)
    if not (output/"meshes").exists():
        (output/"meshes").symlink_to(donor/"meshes",target_is_directory=True)
    server.MODEL_DIR=output
    server.OBSERVATION_DIR=output/"direction-observations"
    original=server.Viewer
    class StandbyPreview(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.update({"angles":[0,-30,-30,-30],"theta":90,
                         "gripper":False,"camera":False,"source":"manual",
                         "distance":0.55,"azimuth":0,"elevation":-8})
    server.Viewer=StandbyPreview
    sys.argv=["standby-preview","--port",str(args.port)]
    server.main()
if __name__=="__main__":
    main()
