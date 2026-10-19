"""Gather Saiki streams listed by Nijisanji Wiki and (optionally) YouTube Data API.

Collect Wiki-curated videos from all channel types, including other Nijisanji
livers, official, external and collab channels. Unapproved external channels are
NOT monitored via YouTube search: Wiki-listed entries become manual candidates.
Videos with no live-streaming metadata stay date-only rather than inventing times.

YOUTUBE_API_KEY is optional: without it the Wiki gives day+URL, not stream clock times.
This script runs on a server / GitHub Actions, not in a public browser.
"""
from __future__ import annotations

import colorsys
import io
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs, quote, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "streams.json"
JS = ROOT / "data" / "streams.js"
CACHE = ROOT / "data" / "thumbnail_cache.json"
CFG = json.loads((ROOT / 'channels.json').read_text(encoding='utf-8'))
WIKI_URL = "https://wikiwiki.jp/nijisanji/佐伯イッテツ/動画一覧/2026"
YEAR = 2026
API_KEY = os.environ.get('YOUTUBE_API_KEY','').strip()
USER_AGENT = 'SaikiCalendarPersonalArchive/0.4 (low frequency; personal fan calendar)'
VIDEO_ID = re.compile(r'^[\w-]{11}$')


def fetch_bytes(url: str, timeout: int = 20) -> bytes:
    # urllib.request.Request encodes the request line as ASCII.
    # Percent-encode non-ASCII path characters (such as Japanese Wiki names).
    parsed = urlsplit(url)
    safe_path = quote(parsed.path, safe="/%:@+-._~")
    safe_query = quote(parsed.query, safe="=&;%:@+,/?-._~")
    ascii_url = urlunsplit((parsed.scheme, parsed.netloc, safe_path, safe_query, parsed.fragment))
    req = Request(ascii_url, headers={'User-Agent':USER_AGENT, 'Accept-Language':'ja'})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def get_api(resource: str, **params):
    if not API_KEY:
        raise RuntimeError('YOUTUBE_API_KEY not configured')
    address = 'https://www.googleapis.com/youtube/v3/' + resource + '?' + urlencode({**params,'key':API_KEY})
    return json.loads(fetch_bytes(address))


def id_from_url(url: str) -> str|None:
    try:
        u = urlsplit(url)
        if u.hostname in ('youtu.be', 'www.youtu.be'):
            vid = u.path.strip('/').split('/')[0]
        elif u.hostname in ('youtube.com','www.youtube.com','m.youtube.com'):
            vid = parse_qs(u.query).get('v',[''])[0]
            if not vid:
                m = re.match(r'^/(?:live|shorts|embed)/([^/]+)',u.path)
                vid = m.group(1) if m else ''
        else:
            return None
        return vid if VIDEO_ID.fullmatch(vid) else None
    except ValueError:
        return None


def category_from_marker(s: str) -> str|None:
    # Wiki's legend: red=self, orange=Oriens, navy=Nijisanji official,
    # gray=other member/group, silver=external, black=Nico live. Only consider
    # a color marker before the broadcast title link, never a random other link.
    color = re.search(r'(?:color\s*[:=(]\s*[\"\']?\s*|color\s*\(\s*)(#2a4b71|red|orange|gray|grey|silver|black)\b',s,re.I)
    if not color:
        if 'data-saiki-channel="self"' in s: return 'self'
        if 'data-saiki-channel="official"' in s: return 'official'
        return None
    name=color.group(1).lower()
    if name=='red':return 'self'
    if name in ('orange','#2a4b71'):return 'official'
    if name in ('gray','grey'):return 'other'
    if name=='silver':return 'external'
    return 'nico'  # only separately handled when a YouTube URL is present


def parse_wiki(raw: bytes) -> dict:
    """Parse the curated 2026 archive list in either Wiki markup or rendered HTML.

    Non-self streams from other channels are candidates, not auto-registered.
    Nico/ABEMA/other non-YouTube items are skipped by this YouTube feed;
    their links can still be entered manually in the app.
    """
    page=raw.decode('utf-8', errors='replace')
    found={}
    # WIKIWIKI source-like notation. The main page contains some inline source
    # after includes; the dedicated /2026 page has entries on individual lines.
    rx=re.compile(r'^\s*-{1,2}\s*(\d{2})/(\d{2})\s+(?:🔒\s*)?&color\((Red|Orange|#2A4B71|Gray|Grey|Silver|Black)\)\{■\};\s*\[\[([^\]\n]+?)>(https?://[^\]\s]+)\]\]',re.I|re.M)
    for m in rx.finditer(page):
        month, day, marker, title, url=m.groups()
        try:d=datetime(YEAR,int(month),int(day))
        except ValueError:continue
        v=id_from_url(url)
        if not v:continue
        kind=category_from_marker('color('+marker+')')
        found[v]=make_item(v,title,d.strftime('%Y-%m-%d'),kind)
    if found:return found
    soup=BeautifulSoup(page,'html.parser')
    for li in soup.find_all('li'):
        text=li.get_text(' ',strip=True)
        date=re.match(r'^[-•\s]*(\d{2})/(\d{2})\b',text)
        if not date:continue
        month,day=map(int,date.groups())
        try:d=datetime(YEAR,month,day)
        except ValueError:continue
        for anchor in li.find_all('a',href=True):
            v=id_from_url(anchor.get('href',''))
            if not v:continue
            # Require the square color marker before the actual broadcast link.
            # Use the HTML portion *before* that anchor, including its parent.
            pre=''.join(str(n) for n in li.contents).split(str(anchor),1)[0]
            kind=category_from_marker(pre)
            if not kind:continue
            title=anchor.get_text(' ',strip=True)[:300]
            found[v]=make_item(v,title,d.strftime('%Y-%m-%d'),kind)
            break
    return found


def make_item(v,title,day,kind):
    channel_type=kind or 'other'
    label={'self':'佐伯イッテツ','official':'公式チャンネル',
           'other':'他ライバー・ユニット','external':'外部チャンネル',
           'nico':'外部チャンネル'}.get(channel_type,'他チャンネル')
    return dict(videoId=v,title=title,channel=label,
      channelType=channel_type,day=day,start=None,end=None,scheduledStart=None,actualStart=None,
      status='archive-unverified',url='https://www.youtube.com/watch?v='+v,
      thumbnail='https://i.ytimg.com/vi/'+v+'/mqdefault.jpg',candidate=channel_type!='self',
      source='nijisanji-wiki-2026',suggestedTag='',greenScore=None)

def green_screen_score(blob: bytes) -> tuple[float,int]:
    """High-saturation green occupying large parts of thumbnail, not tiny text accents."""
    with Image.open(io.BytesIO(blob)) as im:
        im=im.convert('RGB').resize((144,81))
        img=list(im.getdata())
    mask=[]
    for r,g,b in img:
        h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
        mask.append(0.215<=h<=0.47 and s>=0.34 and v>=0.29 and g>r*1.12 and g>b*1.10)
    frac=sum(mask)/len(mask)
    tiles=0
    for ty in range(0,81,9):
        for tx in range(0,144,12):
            n=sum(mask[y*144+x] for y in range(ty,ty+9) for x in range(tx,tx+12))
            if n>=48: tiles+=1
    return round(frac,3),tiles


def cached_green(video_id: str, cache: dict) -> tuple[float|None,bool]:
    if video_id in cache:
        v=cache[video_id]
        return v.get('ratio'),bool(v.get('isGreen'))
    url=f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg'
    try:
        ratio,tiles=green_screen_score(fetch_bytes(url,timeout=15))
    except (HTTPError,URLError,OSError,TimeoutError) as e:
        print('Thumbnail unavailable:',video_id,str(e)[:60]);return None,False
    # Conservative: a coherent green background must occupy enough space.
    # 144 tiles total. A game UI with a tiny green logo should be excluded.
    is_green=ratio>=0.32 and tiles>=33
    cache[video_id]=dict(ratio=ratio,tiles=tiles,isGreen=is_green)
    return ratio,is_green


def update_api(items: dict):
    if not API_KEY:
        print('No YouTube API key: dates from Wiki only; weekly clock data will remain unknown.')
        return
    channel_ids=[c for c in CFG.get('channels',[]) if re.fullmatch(r'UC[\w-]{22}',c.get('id',''))]
    # Discover latest broadcasts on specifically approved channels only.
    for cfg in channel_ids:
        try:
            channels=get_api('channels',part='contentDetails',id=cfg['id']).get('items',[])
            if not channels: continue
            playlist=channels[0]['contentDetails']['relatedPlaylists']['uploads']
            token=None
            pages=int(CFG.get('pages_per_channel',2))
            for _ in range(max(1,min(pages,10))):
                params={'part':'contentDetails','playlistId':playlist,'maxResults':50}
                if token:params['pageToken']=token
                result=get_api('playlistItems',**params)
                for obj in result.get('items',[]):
                    v=obj.get('contentDetails',{}).get('videoId','')
                    if VIDEO_ID.fullmatch(v) and v not in items:
                        items[v]=make_item(v,'',None,cfg['type'])
                token=result.get('nextPageToken')
                if not token:break
        except Exception as e:
            print('Channel discovery failed:',cfg['name'],repr(e))
    all_ids=list(items)
    for start in range(0,len(all_ids),50):
        try:
            details=get_api('videos',part='snippet,liveStreamingDetails,status',id=','.join(all_ids[start:start+50])).get('items',[])
        except Exception as e:
            print('API batch failed:',repr(e));continue
        for v in details:
            rec=items.get(v['id']);sn=v.get('snippet',{});live=v.get('liveStreamingDetails',{})
            if not rec:continue
            if v.get('status',{}).get('privacyStatus')!='public':
                # Removed/non-public videos should not be inserted newly.
                rec['available']=False;continue
            if not live:
                # Wiki-curated appearances can be prerecorded videos; keep them
                # as date-only candidates instead of fabricating live times.
                if rec.get('source')=='nijisanji-wiki-2026' and rec.get('day'):
                    rec.update(title=sn.get('title') or rec['title'],
                               channel=sn.get('channelTitle') or rec['channel'],
                               status='video-date-only',available=True)
                else:rec['available']=False
                continue
            title=sn.get('title','');desc=sn.get('description','')
            # An explicitly requested link becomes a self-stream only when
            # the verified YouTube channel ID matches our approved creator.
            if rec.get('source')=='manual-video-request':
                approved_self={cfg['id'] for cfg in channel_ids if cfg.get('type')=='self'}
                if sn.get('channelId') in approved_self:
                    rec['channelType']='self'
                    rec['candidate']=False
            if rec['channelType']=='official' and rec.get('source')!='nijisanji-wiki-2026':
                if not any(k.casefold() in (title+'\n'+desc).casefold() for k in CFG.get('candidate_keywords',[])):
                    rec['available']=False;continue
            actual=live.get('actualStartTime');scheduled=live.get('scheduledStartTime')
            began=actual or scheduled
            if began:
                day_jst=(datetime.fromisoformat(began.replace('Z','+00:00'))+timedelta(hours=9)).strftime('%Y-%m-%d')
                if day_jst < '2026-01-01':rec['available']=False;continue
                rec['day']=day_jst
            elif not rec.get('day'):
                rec['available']=False;continue
            rec.update(title=title or rec['title'],channel=sn.get('channelTitle',rec['channel']),
                       start=began,end=live.get('actualEndTime'),actualStart=actual,
                       scheduledStart=scheduled,status='ended' if live.get('actualEndTime') else ('live' if actual else 'scheduled'),
                       available=True)


def main():
    old={}
    if OUT.exists():
        try:old={r['videoId']:r for r in json.loads(OUT.read_text(encoding='utf-8')).get('streams',[]) if r.get('videoId')}
        except (KeyError, ValueError):pass
    items={}
    if os.environ.get('FETCH_WIKI', '1') == '1':
        try:
            print('Fetching:',WIKI_URL)
            raw=fetch_bytes(WIKI_URL,timeout=25)
            items=parse_wiki(raw)
            print('Matched 2026 Wiki rows:',len(items))
            if not items:raise ValueError('Wiki parsed but no links')
        except Exception as e:
            print('Wiki unavailable; preserving cached feed:',repr(e))
    else:
        print('Skipping Wiki fetch on frequent refresh; using cached feed.')
    if not items:
        items={k:v for k,v in old.items()}
    # Supplement Wiki with explicitly requested video IDs. Keep them as
    # manual-review candidates unless they match an existing OSHI URL.
    manual_ids_path=ROOT / 'data' / 'manual_video_ids.json'
    if manual_ids_path.exists():
        try:
            manual_ids=json.loads(manual_ids_path.read_text(encoding='utf-8'))
            if not isinstance(manual_ids,list):
                raise ValueError('manual_video_ids must be an array')
            for vid in manual_ids:
                if isinstance(vid,str) and VIDEO_ID.fullmatch(vid) and vid not in items:
                    item=make_item(vid,'',None,'other')
                    item['source']='manual-video-request'
                    item['candidate']=True
                    items[vid]=item
        except (ValueError,OSError) as e:
            print('Could not read explicit video IDs:',repr(e))
    # Preserve previously discovered entries if Wiki temporarily loses entries.
    # They will still require manual approval if they are from other channels.
    for k,v in old.items():items.setdefault(k,v)
    update_api(items)
    # Use last known metadata if this run lacked API results.
    for k,rec in items.items():
        previous=old.get(k,{})
        if not rec.get('start') and previous.get('start'):
            for field in ('start','end','actualStart','scheduledStart','status','channel','title'):
                if previous.get(field):rec[field]=previous[field]
        if rec.get('source')=='nijisanji-wiki-2026':
            rec['candidate']=rec.get('channelType')!='self'
    try:cache=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    except (ValueError,OSError):cache={}
    for r in items.values():
        if r.get('available') is False:continue
        # Thumbnail classification is cached; only fetch unknown IDs.
        score,is_green=cached_green(r['videoId'],cache)
        r['greenScore']=score
        r['suggestedTag']='chat' if is_green else ''
    streams=sorted((v for v in items.values() if v.get('available') is not False and v.get('day','')>='2026-01-01'),key=lambda x:(x.get('day',''),x.get('videoId','')))
    if not streams:
        raise SystemExit('No streams found. Existing feed not overwritten.')
    old_raw = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    stamp = (old_raw.get('generatedAt') if old_raw.get('streams')==streams else None) or datetime.now(timezone.utc).isoformat()
    result={'generatedAt':stamp,'streams':streams,
            'notice':'Wiki dates may not be actual broadcast times; YouTube API enrichment optional.'}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # JS copy is also usable when index.html opened as local file:// URL.
    JS.write_text('window.SAIKI_ARCHIVE_FEED = '+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {len(streams)} records, {sum(bool(x.get("suggestedTag")) for x in streams)} green-screen guesses.')

if __name__=='__main__': main()
