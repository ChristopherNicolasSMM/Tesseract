/* Operações da árvore declarativa, sem DOM ou acesso aos dados do relatório. */
(() => {
  'use strict';
  function flatten(nodes, parent=null, depth=0, result=[]) {
    nodes.forEach((node,index)=>{result.push({node,parent,siblings:nodes,index,depth});if(node.type==='section')flatten(node.children||[],node,depth+1,result);});return result;
  }
  const locate=(nodes,id)=>flatten(nodes).find(entry=>entry.node.id===id);
  function validate(nodes) {
    const entries=flatten(nodes);
    if(entries.length>200||entries.some(entry=>entry.depth>8||(entry.node.type==='section'&&entry.depth>=8))||new Set(entries.map(entry=>entry.node.id)).size!==entries.length)throw Error('Invalid layout limits');
  }
  function duplicate(nodes,id,newId=()=> 'node_'+crypto.randomUUID()) {
    const entry=locate(nodes,id);if(!entry)return;
    const copy=JSON.parse(JSON.stringify(entry.node));flatten([copy]).forEach(item=>item.node.id=newId());
    entry.siblings.splice(entry.index+1,0,copy);
    try{validate(nodes);}catch(error){entry.siblings.splice(entry.index+1,1);throw error;}return copy;
  }
  function move(nodes,id,delta) {
    const entry=locate(nodes,id);if(!entry)return false;const next=entry.index+delta;
    if(next<0||next>=entry.siblings.length)return false;
    [entry.siblings[entry.index],entry.siblings[next]]=[entry.siblings[next],entry.siblings[entry.index]];return true;
  }
  function reparent(nodes,id,parentId) {
    const entry=locate(nodes,id), parent=parentId?locate(nodes,parentId)?.node:null;
    if(!entry||(parentId&&(!parent||parent.type!=='section'))||flatten([entry.node]).some(item=>item.node.id===parentId))throw Error('Invalid destination');
    if((entry.parent?.id||'')===(parentId||''))return false;
    const destination=parent?(parent.children||=[]):nodes;
    entry.siblings.splice(entry.index,1);destination.push(entry.node);
    try{validate(nodes);}catch(error){destination.pop();entry.siblings.splice(entry.index,0,entry.node);throw error;}return true;
  }
  function remove(nodes,id) {const entry=locate(nodes,id);if(entry)entry.siblings.splice(entry.index,1);}
  const api={flatten,locate,validate,duplicate,move,reparent,remove};
  if(typeof module!=='undefined')module.exports=api;else window.TesseractReportsLayout=api;
})();
