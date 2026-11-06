// Read-only preview ONLY. No confirmation, dismiss, worker, spend or execution authority.
export const wp7bPreviewPath=(p,m)=>m==='POST' && /^\/api\/v1\/ads\/recommendations\/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\/preview$/.test(p);
export const safeWp7bPreview=b=>b!==null && typeof b==='object' && !Array.isArray(b) && Object.keys(b).length===0;
