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
      // YouTube's seek operation and pause normally reveal the bottom progress bar.
      // Hide only player controls/gradients, not the video frame or subtitles.
      // This is limited to the temporary capture tab (closed after each frame).
      const player=document.getElementById('movie_player')||video.closest('.html5-video-player');
      if(!player)return {ok:false,reason:'player_not_found'};
      if(!document.getElementById('saiki-capture-hide-controls')){
        const style=document.createElement('style');
        style.id='saiki-capture-hide-controls';
        style.textContent=[
          '#movie_player .ytp-chrome-bottom',
          '#movie_player .ytp-chrome-top',
          '#movie_player .ytp-gradient-bottom',
          '#movie_player .ytp-gradient-top',
          '#movie_player .ytp-progress-bar-container',
          '#movie_player .ytp-progress-bar',
          '#movie_player .ytp-bezel',
          '#movie_player .ytp-pause-overlay',
          '#movie_player .ytp-tooltip',
          '#movie_player .ytp-cards-teaser',
          '#movie_player .ytp-cards-button',
          '#movie_player .ytp-ce-element'
        ].join(',')+'{display:none!important;visibility:hidden!important;opacity:0!important;transition:none!important;animation:none!important}';
        (document.head||document.documentElement).appendChild(style);
      }
      // Move the hover target away from the player without moving the real cursor.
      // An invisible, pointer-active overlay stays in the temporary YouTube tab
      // through captureVisibleTab; it does not paint over or crop the video.
      let hoverShield=document.getElementById('saiki-capture-hover-shield');
      if(!hoverShield){
        hoverShield=document.createElement('div');
        hoverShield.id='saiki-capture-hover-shield';
        hoverShield.setAttribute('aria-hidden','true');
        hoverShield.style.cssText='position:fixed!important;inset:0!important;z-index:2147483647!important;background:transparent!important;pointer-events:auto!important;cursor:default!important;';
        document.documentElement.appendChild(hoverShield);
      }
      // YouTube may keep its controls visible based on a JavaScript hover flag.
      // Notify the player of a pointer exit and enable its own autohide state.
      player.dispatchEvent(new MouseEvent('mouseout',{bubbles:true,relatedTarget:hoverShield}));
      player.dispatchEvent(new MouseEvent('mouseleave',{bubbles:false,relatedTarget:hoverShield}));
      player.classList.add('ytp-autohide');
      // The cursor may still physically be over the video. Keep the shield
      // present and wait for YouTube's control hide animation to finish.
      await pause(3000);
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
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

/* Opt-in metadata reading. Returns only public video fields (no login state). */
async function metadataForVideo(siteTab,videoId){
  let tab;
  try{
    tab=await chrome.tabs.create({
      windowId:siteTab.windowId,active:true,
      url:'https://www.youtube.com/watch?v='+encodeURIComponent(videoId)
    });
    if(!await waitForNavigation(tab.id))throw Error('youtube_navigation_failed');
    await sleep(800);
    const [injected]=await chrome.scripting.executeScript({
      target:{tabId:tab.id},world:'MAIN',args:[videoId],
      func:async(expectedId)=>{
        const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
        const validTime=value=>value&&Number.isFinite(Date.parse(value))?value:null;
        function extract(){
          const player=document.getElementById('movie_player');
          const playerHost=document.querySelector('ytd-player');
          const responses=[];
          try{if(typeof player?.getPlayerResponse==='function')responses.push(player.getPlayerResponse())}catch{}
          try{if(typeof playerHost?.getPlayerResponse==='function')responses.push(playerHost.getPlayerResponse())}catch{}
          try{if(playerHost?.player_?.getPlayerResponse)responses.push(playerHost.player_.getPlayerResponse())}catch{}
          if(window.ytInitialPlayerResponse)responses.push(window.ytInitialPlayerResponse);
          for(const response of responses){
            const detail=response?.videoDetails;
            if(!detail||detail.videoId!==expectedId)continue;
            const live=response?.microformat?.playerMicroformatRenderer?.liveBroadcastDetails;
            const length=Number(detail.lengthSeconds);
            const elem=document.querySelector('video.html5-main-video');
            const fallback=Number(elem?.duration);
            const seconds=Number.isFinite(length)&&length>0?length:Number.isFinite(fallback)&&fallback>0?fallback:0;
            const renderer=response?.microformat?.playerMicroformatRenderer;
            return {
              videoId:expectedId,
              title:String(detail.title||'').slice(0,220),
              channel:String(detail.author||renderer?.ownerChannelName||'').slice(0,100),
              durationSeconds:Math.round(seconds),
              start:validTime(live?.startTimestamp),
              end:validTime(live?.endTimestamp),
              broadcast:!!(live?.startTimestamp||detail.isLiveContent),
              source:'youtube-player'
            };
          }
          const video=document.querySelector('video.html5-main-video');
          const seconds=Number(video?.duration);
          if(video&&Number.isFinite(seconds)&&seconds>0){
            const title=(document.title||'').replace(/\s*-\s*YouTube\s*$/,'');
            return {videoId:expectedId,title:title.slice(0,220),channel:'',
              durationSeconds:Math.round(seconds),start:null,end:null,broadcast:false,
              source:'video-element'};
          }
          return null;
        }
        for(let i=0;i<35;i++){
          const result=extract();
          if(result?.durationSeconds>0)return result;
          if(i===34&&result)return result;
          await wait(350);
        }
        return {videoId:expectedId,title:'',channel:'',durationSeconds:0,start:null,end:null,
          broadcast:false,source:'not_available'};
      }
    });
    const info=injected?.result;
    if(!info||info.videoId!==videoId)throw Error('metadata_video_mismatch');
    return info;
  }finally{
    if(tab?.id)try{await chrome.tabs.remove(tab.id)}catch{}
  }
}

chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message?.type==='METADATA'){
    const siteTab=sender.tab;
    const videoId=message.videoId;
    const requestId=message.requestId;
    if(!siteTab||!sender.url?.startsWith(SITE)||!VIDEO_ID.test(videoId||'')
      ||typeof requestId!=='string'||requestId.length>90){
      sendResponse({ok:false,message:'動画URLまたは呼び出し元が不正です'});return false;
    }
    if(busy){sendResponse({ok:false,message:'スクショ回収中です。完了後に試してください'});return false}
    busy=true;
    sendResponse({ok:true});
    metadataForVideo(siteTab,videoId)
      .then(info=>send(siteTab.id,'METADATA_RESULT',{requestId,videoId,ok:true,info}))
      .catch(error=>send(siteTab.id,'METADATA_RESULT',{requestId,videoId,ok:false,
        message:String(error?.message||'metadata_error').slice(0,120)}))
      .finally(()=>{busy=false});
    return false;
  }
  if(message?.type!=='BATCH')return false;
  const siteTab=sender.tab;
  if(!siteTab||!sender.url?.startsWith(SITE)){
    sendResponse({ok:false,message:'佐伯配信手帳からのみ操作できます'});return false;
  }
  const items=message.items;
  if(busy){sendResponse({ok:false,message:'既に処理中です'});return false}
  if(!Array.isArray(items)||items.length<1||items.length>10||!items.every(item=>VIDEO_ID.test(item.videoId||''))){
    sendResponse({ok:false,message:'対象は1〜10件の公開動画に限定しています'});return false;
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
