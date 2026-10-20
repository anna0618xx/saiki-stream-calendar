"""Review-only crops from finished PUBLIC self-channel YouTube broadcasts.
Private browser screenshots, member-only videos and Google Drive are never read.
If capture is unavailable, record a 7-day cooldown, do not fail Pages deployment.
"""
from __future__ import annotations
import argparse,json,re,subprocess,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from PIL import Image
from crop_screenshots import crop_one

ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/'data/streams.json'
OUT_DIR=ROOT/'images/auto_crops'
MANIFEST=ROOT/'data/auto_crops.json'
ATTEMPTS=ROOT/'data/auto_crop_attempts.json'
VIDEO_ID=re.compile(r'^[A-Za-z0-9_-]{11}$')

def load_json(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError,OSError):return default

def eligible(record):
    return record.get('channelType')=='self' and record.get('candidate') is False and record.get('status')=='ended' and record.get('available') is not False and bool(record.get('start')) and bool(record.get('end')) and bool(VIDEO_ID.fullmatch(str(record.get('videoId',''))))

def choose(records,processed,attempts,now,max_age_days=40,limit=1):
    found=[]
    for rec in sorted(records,key=lambda x:x.get('end') or '',reverse=True):
        if not eligible(rec) or rec['videoId'] in processed:continue
        try:end=datetime.fromisoformat(rec['end'].replace('Z','+00:00'))
        except (ValueError,TypeError):continue
        if end>now or end<now-timedelta(days=max_age_days):continue
        try:last=datetime.fromisoformat(attempts.get(rec['videoId'],{}).get('at',''))
        except ValueError:last=None
        if last and now-last<timedelta(days=7):continue
        found.append(rec)
        if len(found)>=limit:break
    return found

def capture(video_id,target,seconds=600):
    if not VIDEO_ID.fullmatch(video_id):raise ValueError('Invalid public video ID')
    src='https://www.youtube.com/watch?v='+video_id
    # Never print extracted signed streaming URLs.
    pull=subprocess.run([
      'yt-dlp','--no-playlist','--no-warnings','--no-progress','--no-cache-dir',
      '--format','best[height<=720][ext=mp4]/best[height<=720]/best','--get-url',src
    ],capture_output=True,text=True,timeout=45,check=False)
    if pull.returncode or not pull.stdout.strip():raise RuntimeError('Public stream URL not accessible')
    playback=pull.stdout.strip().splitlines()[0]
    if not playback.startswith('https://'):raise RuntimeError('Unsupported public playback URL')
    result=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin',
           '-ss',str(seconds),'-i',playback,'-frames:v','1','-y',str(target)],
           capture_output=True,timeout=90,check=False)
    if result.returncode or not target.is_file() or target.stat().st_size<500:
        raise RuntimeError('Could not extract public frame')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--limit',type=int,default=1)
    p.add_argument('--age-days',type=int,default=40)
    p.add_argument('--seconds',type=int,default=600)
    args=p.parse_args()
    if not 1<=args.limit<=3 or not 10<=args.seconds<=3600:raise SystemExit('Invalid capture limits')
    now=datetime.now(timezone.utc)
    feed=load_json(FEED,{}).get('streams',[])
    manifest=load_json(MANIFEST,{'generatedAt':None,'items':{}})
    if not isinstance(manifest.get('items'),dict):manifest['items']={}
    attempts=load_json(ATTEMPTS,{})
    if not isinstance(attempts,dict):attempts={}
    todo=choose(feed,set(manifest['items']),attempts,now,max_age_days=args.age_days,limit=args.limit)
    print('Eligible PUBLIC videos to try:',len(todo))
    changed=False
    for rec in todo:
        video=rec['videoId']
        try:
            with tempfile.TemporaryDirectory() as tmp:
                raw=Path(tmp)/'public_frame.jpg'
                capture(video,raw,seconds=args.seconds)
                with Image.open(raw) as image:proposals=crop_one(image,OUT_DIR,video)
            options=[{'variant':x['variant'],'image':Path(x['file']).relative_to(ROOT).as_posix(),
                       'requiresReview':True} for x in proposals]
            manifest['items'][video]={'videoId':video,'date':rec.get('day',''),
                'source':'public-youtube-frame','capturedSeconds':args.seconds,
                'candidates':options,'createdAt':now.isoformat()}
            changed=True
            print('Prepared review-only public crop candidates:',video,len(options))
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as exc:
            attempts[video]={'at':now.isoformat(),'result':'unavailable'}
            changed=True
            print('Public capture unavailable:',video,type(exc).__name__)
    if not changed:
        print('No new public frame crops. Manifest unchanged.')
        return
    manifest['generatedAt']=now.isoformat()
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ATTEMPTS.write_text(json.dumps(attempts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
