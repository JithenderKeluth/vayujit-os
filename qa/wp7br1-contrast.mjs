// Supplemental measured WCAG contrast, NOT a replacement for axe or speech tests.
import path from 'node:path';
export function parseColor(value){
 if(!/^rgba?\(/.test(value||'') || value.includes('%'))return null;
 const n=value.match(/\d*\.?\d+/g)?.map(Number);
 if(!n || ![3,4].includes(n.length) || n.slice(0,3).some(x=>x>255))return null;
 if(n.length===3)n.push(1);return n[3]>=0&&n[3]<=1?n:null;
}
export function composite(f,b){return f.slice(0,3).map((v,i)=>v*f[3]+b[i]*(1-f[3])).concat(1);}
export function contrastRatio(a,b){const lum=c=>c.slice(0,3).map(v=>{const s=v/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);const x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
export function resolveContrast(m){
 if(m.disabled)return{status:'NOT APPLICABLE',criterion:'1.4.3',reason:'Native inactive control; exemption is not applied to surrounding instructions.'};
 if(!m.visible || m.obscured || m.ancestors.some(x=>Number(x.opacity)!==1) || m.textShadow!=='none')return{status:'NOT VERIFIED',reason:'Visibility, overlay, opacity or text-shadow requires additional rendered review.'};
 const layers=[];
 for(const a of m.ancestors){if(a.backgroundImage!=='none')return{status:'NOT VERIFIED',reason:'Background image/gradient cannot be reduced to one verified solid color.'};const c=parseColor(a.backgroundColor);if(!c)return{status:'NOT VERIFIED',reason:'Unsupported color space'};layers.push(c);if(c[3]===1)break;}
 if(!layers.length || layers.at(-1)[3]!==1)return{status:'NOT VERIFIED',reason:'No verified opaque backdrop; canvas color is not invented.'};
 let bg=layers.pop();while(layers.length)bg=composite(layers.pop(),bg);
 const fg=parseColor(m.color);if(!fg)return{status:'NOT VERIFIED',reason:'Unsupported foreground color'};
 const effective=composite(fg,bg),ratio=contrastRatio(effective,bg),large=m.fontSize>=24 || m.fontSize>=18.666666667 && m.fontWeight>=700;
 return{status:ratio>=(large?3:4.5)?'PASS':'FAIL',criterion:'1.4.3',ratio,required:large?3:4.5,foreground:fg,effective_foreground:effective,background:bg,method:'Computed rendered sRGB; alpha composited through verified solid ancestor backgrounds; WCAG relative luminance'};
}
// Observe finite CSS transitions finishing; never disable/cancel an animation.
export async function waitForTransitions(element){
 return element.evaluate(async el=>{
  const animations=el.getAnimations();
  if(animations.some(a=>a.effect?.getComputedTiming().iterations===Infinity))return false;
  let timer;
  try{return await Promise.race([Promise.all(animations.map(a=>a.finished.then(()=>true,()=>false))).then(values=>values.every(Boolean)),new Promise(resolve=>{timer=setTimeout(()=>resolve(false),1000);})]);}
  finally{clearTimeout(timer);}
 });
}
export async function measureTargets(run,selectors,state){
 const rows=[];
 for(const selector of selectors){const targets=run.page.locator(selector);const count=await targets.count();
  if(!count){rows.push({state,selector,status:'NOT VERIFIED',reason:'Required target not present in this rendered state'});continue;}
  for(let i=0;i<Math.min(count,8);i++){
   const element=targets.nth(i);if(!await element.isVisible())continue;
   await element.scrollIntoViewIfNeeded();
   if(!await waitForTransitions(element)){rows.push({state,selector,index:i,status:'NOT VERIFIED',reason:'Rendered transition did not settle within the bounded observation; no animation was disabled'});continue;}
   const m=await element.evaluate(el=>{const cs=getComputedStyle(el),r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2),ancestors=[];for(let a=el;a;a=a.parentElement){const s=getComputedStyle(a);ancestors.push({backgroundColor:s.backgroundColor,backgroundImage:s.backgroundImage,opacity:s.opacity});}return{color:cs.color,fontSize:parseFloat(cs.fontSize),fontWeight:parseInt(cs.fontWeight),textShadow:cs.textShadow,disabled:el.matches(':disabled'),visible:r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,obscured:!!hit&&!el.contains(hit),focused:el===document.activeElement,outline:{color:cs.outlineColor,width:cs.outlineWidth,style:cs.outlineStyle},border:{color:cs.borderTopColor,width:cs.borderTopWidth},ancestors};});
   const screenshot=path.join(run.directory,`contrast-${state}-${rows.length}.png`);await element.screenshot({path:screenshot});
   const focus=m.focused && m.outline.style!=='none' && parseFloat(m.outline.width)>0?{...resolveContrast({...m,color:m.outline.color,fontSize:24,fontWeight:700,textShadow:'none',ancestors:m.ancestors.slice(1)}),criterion:'1.4.11',scope:'Measured authored outline versus verified adjacent parent backdrop; not full focus conformance'}:{status:'NOT VERIFIED',reason:'Focus outline not active at this sampled element'};
   rows.push({state,route:new URL(run.page.url()).pathname,selector,index:i,...resolveContrast(m),focus_indicator:focus,rendered:m,screenshot});
  }
  if(count>8)rows.push({state,selector,status:'NOT VERIFIED',reason:`Bounded sample: ${count-8} additional matching targets not measured`});
 }
 return rows;
}
