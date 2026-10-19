"""From a locally owned/licensed recording only; no YouTube downloading."""
import argparse, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description='Capture frame at 10:00 from local authorized video')
p.add_argument('input',help='Existing, rights-cleared local video file (mp4 etc.)')
p.add_argument('output',help='Output still-image path, e.g. frame.jpg')
a=p.parse_args();f=Path(a.input)
if not f.is_file():p.error('Local input video does not exist')
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','00:10:00','-i',str(f),'-frames:v','1','-q:v','3',a.output],check=True)
print('Saved',a.output)
