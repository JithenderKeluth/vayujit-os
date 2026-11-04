import test from 'node:test';
import assert from 'node:assert/strict';
import {browserDiagnostic} from '../wp7a7-diagnostic.mjs';
test('browser startup diagnostic retains only allowlisted type and source location',()=>{
 const result=browserDiagnostic('ReferenceError: password=secret-value token=secret-token is not defined\n at file:///workspace/qa/wp7a4-browser.mjs:49:100');
 assert.equal(result.classification,'ReferenceError'); assert.equal(result.diagnostic,'is not defined');
 assert.deepEqual(result.source,{file:'qa/wp7a4-browser.mjs',line:49,column:100});
 assert.equal(result.raw_output_persisted,false);
 assert.ok(!JSON.stringify(result).includes('secret'));
});
test('unknown browser failures cannot persist arbitrary native output',()=>{
 const result=browserDiagnostic('database-password=hidden postgresql://private/customer');
 assert.equal(result.classification,'UNCLASSIFIED_BROWSER_CHILD'); assert.equal(result.diagnostic,null);
 assert.equal(result.source,null); assert.ok(!JSON.stringify(result).includes('hidden'));
});
