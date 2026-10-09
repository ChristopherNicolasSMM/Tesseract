const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../../static/js/reports_history.js');
test('undo/redo returns independent snapshots and branches discard redo',()=>{
 const history=create();const state={layout:{body:[{text:'A'}]},schema:'{'};
 history.reset(state);state.layout.body[0].text='B';history.record(state);
 assert.equal(history.undo().layout.body[0].text,'A');const next=history.redo();next.layout.body[0].text='outside';
 assert.equal(history.undo().layout.body[0].text,'A');assert.equal(history.redo().layout.body[0].text,'B');
 history.undo();history.record({layout:{body:[{text:'C'}]},schema:'{}'});assert.equal(history.canRedo(),false);
 assert.equal(history.undo().layout.body[0].text,'A');
});
test('reset after save clears both directions; duplicate records are ignored',()=>{
 const history=create();history.reset({value:1});history.record({value:1});assert.equal(history.canUndo(),false);
 history.record({value:2});history.undo();history.reset({value:1});assert.equal(history.canUndo(),false);assert.equal(history.canRedo(),false);
});
test('count and UTF-8 byte limits drop oldest snapshots',()=>{
 const history=create({limit:3});history.reset({value:0});for(let value=1;value<5;value++)history.record({value});
 assert.equal(history.undo().value,3);assert.equal(history.undo().value,2);assert.equal(history.undo(),undefined);
 const bounded=create({maxBytes:20});bounded.reset('áááá');bounded.record('éééé');assert.equal(bounded.canUndo(),true);
 bounded.record('íííí');assert.equal(bounded.undo(),'éééé');assert.equal(bounded.undo(),undefined);
});
