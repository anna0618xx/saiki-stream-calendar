/* Saiki capture bridge. Only the deployed calendar origin can submit video IDs. */
(() => {
  'use strict';
  const CHANNEL='saiki-pc-capture-v1';
  const ORIGIN='https://anna0618xx.github.io';
  if(location.origin!==ORIGIN||!location.pathname.startsWith('/saiki-stream-calendar/'))return;
  const emit=(type,payload={})=>window.postMessage({channel:CHANNEL,direction:'extension',type,...payload},ORIGIN);
  window.addEventListener('message',event=>{
    if(event.source!==window||event.origin!==ORIGIN)return;
    const msg=event.data;
    if(!msg||msg.channel!==CHANNEL||msg.direction!=='site'||msg.type!=='START')return;
    const list=Array.isArray(msg.items)?msg.items:[];
    if(list.length<1||list.length>5||!list.every(x=>x&&/^[A-Za-z0-9_-]{11}$/.test(x.videoId||''))){
      emit('ERROR',{message:'対象の動画IDを確認してください'});return;
    }
    chrome.runtime.sendMessage({type:'BATCH',items:list.map(x=>({videoId:x.videoId}))},reply=>{
      const error=chrome.runtime.lastError?.message;
      if(error||!reply?.ok)emit('ERROR',{message:error||reply?.message||'拡張機能を起動できません'});
      else emit('STARTED',{count:list.length});
    });
  });
  chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
    if(!message||message.channel!==CHANNEL)return false;
    if(!['PROGRESS','IMAGE','FINISHED'].includes(message.type))return false;
    emit(message.type,{...message.payload});
    sendResponse({ok:true});
    return false;
  });
  emit('READY');
})();
