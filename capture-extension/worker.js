/* Opt-in Chrome MV3 capture. Never reads/export cookies or account tokens. */
'use strict';
const CHANNEL='saiki-pc-capture-v1';
const SITE='https://anna0618xx.github.io/saiki-stream-calendar/';
const VIDEO_ID=/^[A-Za-z0-9_-]{11}$/;
let busy=false;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const send=async(tabId,type,payload={})=>{
  try{await chrome.tabs.sendMessage(tabId,{channel:CHANNEL,type,payload})}
  catch(err){console.warn('Saiki capture: calendar tab unavailable',type)}
};
async function waitForNavigation(tabId){
  for(let i=0;i<45;i++){
    let tab;
    try{tab=await chrome.tabs.get(tabId)}catch{return false}
    if(tab.status==='complete'&&tab.url?.startsWith('https://www.youtube.com/watch?'))return true;
    await sleep(400);
  }
  return false;
}
async function seekVideo(tabId){
  const [result]=await chrome.scripting.executeScript({
    target:{tabId},
    args:[600],
    func:async(seconds)=>{
      const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
      let video;
      for(let i=0;i<50;i++){
        video=document.querySelector('video.html5-main-video')||document.querySelector('video');
        if(video&&video.readyState>=1&&video.videoWidth>0)break;
        await pause(400);
      }
      if(!video||video.readyState<1)return {ok:false,reason:'video_not_ready'};
      video.muted=true;
      const duration=video.duration;
      const target=Number.isFinite(duration)?Math.min(seconds,Math.max(0,duration-8)):seconds;
      try{video.currentTime=target}catch{return {ok:false,reason:'seek_denied'}}
      for(let i=0;i<50;i++){
        if(video.readyState>=2&&video.videoWidth>0&&Math.abs(video.currentTime-target)<5)break;
        await pause(400);
      }
      if(!(video.readyState>=2&&Math.abs(video.currentTime-target)<5))return {ok:false,reason:'frame_not_ready'};
      video.pause();
      await pause(650);
      const bounds=video.getBoundingClientRect();
      let left=bounds.left,top=bounds.top,width=bounds.width,height=bounds.height;
      if(width<240||height<140)return {ok:false,reason:'video_not_visible'};
      // Exclude letterboxing produced by a contain-fitted player.
      const frameRatio=video.videoWidth/video.videoHeight,boxRatio=width/height;
      if(Number.isFinite(frameRatio)&&frameRatio>0){
        if(boxRatio>frameRatio){const actual=height*frameRatio;left+=(width-actual)/2;width=actual}
        else{const actual=width/frameRatio;top+=(height-actual)/2;height=actual}
      }
      if(left<0||top<0||left+width>innerWidth+2||top+height>innerHeight+2){
        return {ok:false,reason:'video_outside_viewport'};
      }
      return {ok:true,rect:{left,top,width,height},viewport:{width:innerWidth,height:innerHeight}};
    }
  });
  return result?.result||{ok:false,reason:'video_script_failed'};
}
async function captureOne(siteTab,videoId){
  let tab;
  try{
    tab=await chrome.tabs.create({
      windowId:siteTab.windowId,active:true,
      url:'https://www.youtube.com/watch?v='+encodeURIComponent(videoId)+'&t=600s'
    });
    if(!await waitForNavigation(tab.id))throw Error('youtube_navigation_failed');
    await sleep(900);
    const frame=await seekVideo(tab.id);
    if(!frame.ok)throw Error(frame.reason||'unknown_frame_error');
    const [active]=await chrome.tabs.query({windowId:tab.windowId,active:true});
    if(active?.id!==tab.id)throw Error('capture_tab_not_active');
    const current=await chrome.tabs.get(tab.id);
    if(!current.url?.startsWith('https://www.youtube.com/watch?')||!new URL(current.url).searchParams.get('v')?.includes(videoId))throw Error('unexpected_capture_url');
    const screenshot=await chrome.tabs.captureVisibleTab(tab.windowId,{format:'jpeg',quality:85});
    if(!screenshot?.startsWith('data:image/jpeg;base64,'))throw Error('empty_capture');
    await send(siteTab.id,'IMAGE',{videoId,image:screenshot,rect:frame.rect,viewport:frame.viewport});
  }finally{
    if(tab?.id)try{await chrome.tabs.remove(tab.id)}catch{}
  }
}
chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message?.type!=='BATCH')return false;
  const siteTab=sender.tab;
  if(!siteTab||!sender.url?.startsWith(SITE)){
    sendResponse({ok:false,message:'佐伯配信手帳からのみ操作できます'});return false;
  }
  const items=message.items;
  if(busy){sendResponse({ok:false,message:'既に処理中です'});return false}
  if(!Array.isArray(items)||items.length<1||items.length>5||!items.every(item=>VIDEO_ID.test(item.videoId||''))){
    sendResponse({ok:false,message:'対象は1〜5件の公開動画に限定しています'});return false;
  }
  busy=true;
  sendResponse({ok:true});
  (async()=>{
    let captured=0,failed=0;
    try{
      for(let i=0;i<items.length;i++){
        const {videoId}=items[i];
        await send(siteTab.id,'PROGRESS',{index:i+1,total:items.length,videoId,status:'running'});
        try{
          await captureOne(siteTab,videoId);
          captured++;
          await send(siteTab.id,'PROGRESS',{index:i+1,total:items.length,videoId,status:'captured'});
        }catch(error){
          failed++;
          await send(siteTab.id,'PROGRESS',{index:i+1,total:items.length,videoId,status:'error',
            reason:String(error?.message||'capture_failed').slice(0,90)});
        }
        await sleep(1000);
      }
    }finally{
      busy=false;
      await send(siteTab.id,'FINISHED',{captured,failed,total:items.length});
    }
  })().catch(err=>{busy=false;console.warn('Saiki capture batch stopped',err?.message)});
  return false;
});
