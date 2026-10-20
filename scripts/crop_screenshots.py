"""Screenshot crop proposals. Does NOT upload any personal screenshots."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

RATIO=4/5
EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp'}

def find_faces(image):
    detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    if detector.empty(): return []
    rgb=np.asarray(image.convert('RGB'))
    h,w=rgb.shape[:2]
    scale=min(1.,900/max(w,h))
    if scale<1: rgb=cv2.resize(rgb,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
    gray=cv2.equalizeHist(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY))
    minimum=max(22,int(min(gray.shape[:2])*.065))
    detected=detector.detectMultiScale(gray,scaleFactor=1.08,minNeighbors=4,minSize=(minimum,minimum))
    faces=[]
    for x,y,fw,fh in detected:
        xx,yy,ww,hh=[round(v/scale) for v in (x,y,fw,fh)]
        if ww>0 and hh>0:faces.append((xx,yy,ww,hh))
    return sorted(faces,key=lambda r:r[2]*r[3],reverse=True)

def box_for_face(size,face,ratio=RATIO):
    w,h=size;x,y,fw,fh=face
    ch=min(h,max(fh*4.3,h*.47));cw=ch*ratio
    if cw>w:cw=w;ch=cw/ratio
    cw=int(min(w,round(cw)));ch=int(min(h,round(ch)))
    left=max(0,min(w-cw,round(x+fw*.5-cw*.5)))
    top=max(0,min(h-ch,round(y+fh*.5-ch*.29)))
    return (int(left),int(top),int(left+cw),int(top+ch))

def fallback_boxes(size,ratio=RATIO):
    w,h=size;ch=int(round(min(h,w/ratio)));cw=int(round(ch*ratio))
    y=max(0,(h-ch)//2)
    return {name:(round((w-cw)*anchor),y,round((w-cw)*anchor)+cw,y+ch)
            for name,anchor in [('left',0),('center',.5),('right',1)]}

def propose_boxes(image):
    faces=find_faces(image)
    if faces and (len(faces)==1 or faces[1][2]*faces[1][3] < faces[0][2]*faces[0][3]*.55):
        return [('face',box_for_face(image.size,faces[0]))]
    return list(fallback_boxes(image.size).items())

def crop_one(image,output_dir,basename,max_size=(400,500)):
    image=ImageOps.exif_transpose(image).convert('RGB')
    output_dir.mkdir(parents=True,exist_ok=True)
    items=[]
    for variant,box in propose_boxes(image):
        cropped=image.crop(box);cropped.thumbnail(max_size,Image.Resampling.LANCZOS)
        target=output_dir/(basename+'-'+variant+'.webp')
        cropped.save(target,'WEBP',quality=84,method=5)
        items.append({'variant':variant,'file':str(target),'box':list(box),'sourceSize':list(image.size),
                      'cropSize':list(cropped.size),'requiresReview':True})
    return items

def process_folder(source,output):
    if not source.exists():raise FileNotFoundError(source)
    paths=[source] if source.is_file() else sorted(p for p in source.rglob('*') if p.suffix.lower() in EXTENSIONS)
    items=[]
    for path in paths:
        if path.suffix.lower() not in EXTENSIONS:continue
        try:
            with Image.open(path) as im:
                relative=path.relative_to(source if source.is_dir() else source.parent)
                key=hashlib.sha256(str(relative).encode()).hexdigest()[:8]
                crops=crop_one(im,output,path.stem[:60]+'-'+key)
                items.append({'source':str(path),'candidates':crops})
        except (UnidentifiedImageError,OSError,ValueError) as err:
            print('Skipped invalid image:',path.name,type(err).__name__,file=sys.stderr)
    return items

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Local-only private screenshot crop suggestions')
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('private-crop-preview'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    results=process_folder(args.input,args.output)
    (args.output/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved private crop previews:',len(results))
