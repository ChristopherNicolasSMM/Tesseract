/* Apropriações explícitas; cálculo e validação monetária pertencem ao servidor. */
(() => {
  'use strict';
  const lines=document.getElementById('accrual-lines'),add=document.getElementById('accrual-add');
  if(!lines||!add)return;
  add.onclick=()=>{
    if(lines.children.length>=120)return;
    const row=lines.firstElementChild.cloneNode(true);
    row.querySelectorAll('input,select').forEach(input=>{input.value='';});
    lines.append(row);
  };
  lines.addEventListener('click',event=>{
    if(event.target.closest('.accrual-remove')&&lines.children.length>1)event.target.closest('.accrual-line').remove();
  });
})();
