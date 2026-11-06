import {test} from 'node:test';
import assert from 'node:assert/strict';
import {wp7bPreviewPath,safeWp7bPreview} from '../wp7b-safety.mjs';
import {allowRequest} from '../safety.mjs';
test('WP7B admits only authenticated read-only recommendation preview in its own policy',()=>{
 const base='/api/v1/ads/recommendations/12345678-1234-1234-1234-123456789abc/';
 assert(wp7bPreviewPath(base+'preview','POST'));
 for(const suffix of ['confirm','dismiss','execute','publish'])assert(!wp7bPreviewPath(base+suffix,'POST'));
 assert(!wp7bPreviewPath(base+'preview','DELETE'));
 assert(!wp7bPreviewPath('/api/v1/ads/recommendations/not-id/preview','POST'));
 assert(safeWp7bPreview({}));for(const body of [null,[],{confirm:true},{token:'x'},{execute:false}])assert(!safeWp7bPreview(body));
 assert(allowRequest('http://127.0.0.1:5555'+base+'preview','POST','http://127.0.0.1:5555','WP7B'));
 assert(!allowRequest('https://example.com'+base+'preview','POST','http://127.0.0.1:5555','WP7B'));
 assert(!allowRequest('http://127.0.0.1:5555'+base+'preview','POST','http://127.0.0.1:5555','WP7A7'));
});
