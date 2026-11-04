// Reuse the strict preceding gate. Context translation is naming only, not an assertion waiver.
import {gate as existingGate, ids, assertions} from './wp7a6-contract.mjs';
export {ids, assertions};
export const contexts=['chrome-1440','chrome-390','msedge-1440','msedge-390'].map(v=>'wp7a7-'+v);
export function gate(input) {
  const blockers=[...(input.blockers||[])];
  if(input.ads_clarification?.approved!==true) blockers.push('L-17 explicit scope approval missing');
  const result=existingGate({...input, blockers, entries:(input.entries||[]).map(e=>({...e,
    wp7a6_target:e.wp7a7_target===true,
    attempts:(e.attempts||[]).map(a=>({...a,context:a.context.replace(/^wp7a7-/, 'wp7a6-')}))}))});
  return {...result,package:'WP7A-7',ads_scope_approved:input.ads_clarification?.approved===true,
    live_provider_expiry:'UNVERIFIED',application_certification:'INCOMPLETE'};
}
