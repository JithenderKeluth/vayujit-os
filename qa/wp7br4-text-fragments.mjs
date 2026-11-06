// Measure actual label/caption text, not the oversized box containing its input.
// Keep the original DOM target and every text fragment; do not suppress axe nodes.
import {resolveContrast} from './wp7br1-contrast.mjs';
export async function textFragments(run,selector,state){
 const p=run.page,rows=[];const count=await p.locator(selector).count();
 for(let targetIndex=0;targetIndex<count;targetIndex++){
  const target=p.locator(selector).nth(targetIndex);if(!await target.isVisible())continue;
  const fragments=await target.evaluate(el=>{const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);const out=[];let n,index=0;while((n=walker.nextNode())){if(n.parentElement.closest('input,textarea,select,button,pre,code'))continue;const text=n.textContent;for(const match of text.matchAll(/\S+/g))out.push({node_index:index,start:match.index,end:match.index+match[0].length,text:match[0]});index++;}return out;});
  for(let part=0;part<fragments.length;part++){
   const fragment=fragments[part];
   const measured=await target.evaluate((el,f)=>{
    const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node,index=0;while((node=walker.nextNode())){if(node.parentElement.closest('input,textarea,select,button,pre,code'))continue;if(index++===f.node_index)break;}
    if(!node||node.textContent.slice(f.start,f.end)!==f.text)return null;
    const range=document.createRange();range.setStart(node,f.start);range.setEnd(node,f.end);node.parentElement.scrollIntoView({block:'start',inline:'nearest'});
    for(let attempt=0;attempt<3;attempt++){
     const r=range.getBoundingClientRect();if(r.top<20||r.bottom>innerHeight-20)window.scrollBy(0,r.top-40);
     if(r.left<8||r.right>innerWidth-8){let scroller=node.parentElement;while(scroller&&!(scroller.scrollWidth>scroller.clientWidth+1&&/auto|scroll/.test(getComputedStyle(scroller).overflowX)))scroller=scroller.parentElement;if(scroller)scroller.scrollLeft+=r.left-16;else window.scrollBy(r.left-16,0);}
    }
    const e=node.parentElement,cs=getComputedStyle(e),r=range.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2),ancestors=[];
    for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);ancestors.push({backgroundColor:s.backgroundColor,backgroundImage:s.backgroundImage,opacity:s.opacity});}
    return{color:cs.color,fontSize:parseFloat(cs.fontSize),fontWeight:parseInt(cs.fontWeight),textShadow:cs.textShadow,disabled:false,visible:r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,obscured:!!hit&&!el.contains(hit),ancestors,rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},text:f.text};
   },fragment);
   if(!measured){rows.push({selector,target_index:targetIndex,part,status:'NOT VERIFIED',reason:'Text identity changed while reading; not measured'});continue;}
   const row={selector,target_index:targetIndex,part,context:run.label,state,timestamp:new Date().toISOString(),rendered:measured,...resolveContrast(measured),scope:'Actual original-target text word; input/select values excluded and separately tested'};
   row.screenshot=run.directory+'/'+state+'-'+targetIndex+'-'+part+'.png';await p.screenshot({path:row.screenshot});rows.push(row);
  }
  if(!fragments.length)rows.push({selector,target_index:targetIndex,status:'NOT VERIFIED',reason:'No direct label/caption text fragment found'});
 }
 return rows;
}
