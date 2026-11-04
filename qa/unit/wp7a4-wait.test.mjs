import test from 'node:test';
import assert from 'node:assert/strict';
import {responseWait} from '../wp7a4-wait.mjs';
test('an orphaned response waiter is observed but still rejects its actual awaited assertion',async()=>{
 const failure=new Error('TEST_RESPONSE_TIMEOUT');
 const result=responseWait({waitForResponse:()=>Promise.reject(failure)},()=>true,{});
 await new Promise(r=>setImmediate(r));
 await assert.rejects(result,/TEST_RESPONSE_TIMEOUT/);
});
