/* Histórico local limitado; snapshots independentes, sem armazenamento persistente. */
(() => {
  'use strict';
  function create({limit=30,maxBytes=8*1024*1024}={}) {
    let entries=[],index=-1;
    const bytes=value=>new TextEncoder().encode(value).length;
    const encode=value=>{const text=JSON.stringify(value);return {text,bytes:bytes(text)};};
    function reset(value) {entries=[encode(value)];index=0;}
    function record(value) {
      const serialized=encode(value);if(entries[index]?.text===serialized.text)return;
      entries=entries.slice(0,index+1);entries.push(serialized);index=entries.length-1;
      while(entries.length>1&&(entries.length>limit||entries.reduce((sum,item)=>sum+item.bytes,0)>maxBytes)){entries.shift();index--;}
    }
    function move(delta) {const target=index+delta;if(target<0||target>=entries.length)return;index=target;return JSON.parse(entries[index].text);}
    return {reset,record,undo:()=>move(-1),redo:()=>move(1),canUndo:()=>index>0,canRedo:()=>index>=0&&index<entries.length-1};
  }
  const api={create};if(typeof module!=='undefined')module.exports=api;else window.TesseractReportsHistory=api;
})();
