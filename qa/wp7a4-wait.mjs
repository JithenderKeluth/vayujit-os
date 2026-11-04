// Keep a waiter rejection observed if an earlier UI action fails. Awaiting the
// returned ORIGINAL promise still rejects, so no acceptance error is suppressed.
export function responseWait(page,predicate,options){
 const pending=page.waitForResponse(predicate,options);
 void pending.catch(()=>{});
 return pending;
}
