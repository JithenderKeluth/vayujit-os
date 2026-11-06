// Documentation-only discovery. Never imports application modules or opens a DB.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import ts from 'typescript';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const webRequire = createRequire(path.resolve('apps/web/package.json'));
const { parseTemplate } = await import(pathToFileURL(webRequire.resolve('@angular/compiler')).href);

const base = 'docs/product-handbook';
const ui = 'apps/web/src/app';
const clean = s => String(s ?? '').replace(/\s+/g, ' ').trim();
const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const md = s => clean(s).replaceAll('|', '\\|').replaceAll('\n', ' ');
const files = [];
async function walk(d) {
  for (const e of await fs.readdir(d, { withFileTypes: true })) {
    const p = path.posix.join(d, e.name);
    if (e.isDirectory()) await walk(p);
    else if (e.isFile() && p.endsWith('.ts') && !p.endsWith('.spec.ts')) files.push(p);
  }
}
await walk(ui);
const components = new Map();
const classFiles = new Map();
for (const file of files) {
  const source = await fs.readFile(file, 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  let meta;
  function visit(n) {
    if (ts.isCallExpression(n) && n.expression.getText(ast) === 'Component' && ts.isObjectLiteralExpression(n.arguments[0])) meta = n.arguments[0];
    if (ts.isClassDeclaration(n) && n.name) classFiles.set(n.name.text, file);
    ts.forEachChild(n, visit);
  }
  visit(ast);
  if (!meta) continue;
  const props = new Map(meta.properties.filter(ts.isPropertyAssignment).map(p => [p.name.getText(ast).replaceAll("'", ''), p.initializer]));
  let template = props.get('template')?.text ?? '';
  let templateFile = file;
  let templateLineOffset = props.get('template') ? ast.getLineAndCharacterOfPosition(props.get('template').getStart(ast)).line : 0;
  if (props.get('templateUrl')?.text) {
    templateFile = path.posix.normalize(path.posix.join(path.posix.dirname(file), props.get('templateUrl').text));
    template = await fs.readFile(templateFile, 'utf8');
    templateLineOffset = 0;
  }
  const parsed = parseTemplate(template, templateFile, { preserveWhitespaces: false });
  const fields = [], actions = [], headings = [], details = [], tables = [], dialogs = [], labels = new Map();
  const clientValidators = new Map();
  function validatorsWalk(n) {
    if (ts.isPropertyAssignment(n)) {
      const value = n.initializer.getText(ast);
      if (value.includes('Validators.') && !value.includes('readonly form')) {
        const key = n.name.getText(ast).replace(/^['"]|['"]$/g,'');
        if (/^[a-zA-Z_][a-zA-Z_0-9]*$/.test(key) && value.length < 900) clientValidators.set(key, clean(value));
      }
    }
    ts.forEachChild(n, validatorsWalk);
  }
  validatorsWalk(ast);
  const attr = (n, k) => n.attributes?.find(a => a.name === k)?.value;
  const binding = (n, k) => n.inputs?.find(a => a.name === k)?.value?.source;
  function text(n) {
    if (n.value !== undefined) return typeof n.value === 'string' ? n.value : (n.value?.source ?? '');
    return (n.children ?? []).filter(c => !['input','select','textarea'].includes(c.name)).map(text).join(' ');
  }
  function children(n) {
    return [...(n.children ?? []), ...(n.branches ?? []), ...(n.empty?.children ?? [])];
  }
  function labelWalk(n) {
    if (n.name === 'label' && attr(n, 'for')) labels.set(attr(n, 'for'), clean(text(n)));
    children(n).forEach(labelWalk);
  }
  (parsed.nodes ?? []).forEach(labelWalk);
  function scan(n, parentLabel = '', form = '') {
    const label = n.name === 'label' ? clean(text(n)) : parentLabel;
    const currentForm = n.name === 'form' ? (n.outputs?.find(x => x.name === 'ngSubmit')?.handler?.source ?? attr(n,'aria-label') ?? 'Form') : form;
    const line = n.sourceSpan?.start?.line !== undefined ? n.sourceSpan.start.line + 1 + templateLineOffset : null;
    if (['input','select','textarea'].includes(n.name)) {
      const id = attr(n,'id') ?? '';
      const visible = labels.get(id) || label;
      const aria = attr(n,'aria-label') || binding(n,'aria-label');
      const raw = Object.fromEntries((n.attributes ?? []).map(a => [a.name,a.value]));
      const bindings = Object.fromEntries((n.inputs ?? []).map(a => [a.name,clean(a.value?.source)]));
      const options = [];
      function optionWalk(x) { if(x.name === 'option') options.push({label:clean(text(x)),value:attr(x,'value') ?? binding(x,'value') ?? null});children(x).forEach(optionWalk); }
      if(n.name === 'select') children(n).forEach(optionWalk);
      const validation=clientValidators.get(attr(n,'formControlName'))??null;
      fields.push({id:'',component:file,template_file:templateFile,template_line:line,label:visible || aria || null,label_basis:visible?'VISIBLE_LABEL_SOURCE':aria?'ACCESSIBLE_NAME_SOURCE':'UNVERIFIED_LABEL',element:n.name,type:attr(n,'type') || (binding(n,'type')?'DYNAMIC_TYPE':n.name==='input'?'text':n.name),name:attr(n,'name')||attr(n,'formControlName')||id||null,model:binding(n,'ngModel')||null,form:currentForm,attributes:raw,bindings,options,client_validation:validation,required:raw.required!==undefined?'REQUIRED_IN_TEMPLATE':bindings.required?'CONDITIONAL_REQUIRED':validation?.includes('Validators.required')?'REQUIRED_OR_CONDITIONAL_IN_CLIENT':'NOT_STATED_IN_TEMPLATE',verification:'DOCUMENTED BUT NOT CURRENTLY VERIFIED',api_validation:'NOT_FULLY_REVIEWED'});
    }
    if (n.name==='button' || n.name==='a' && (attr(n,'routerLink')||n.inputs?.some(x=>x.name==='routerLink')||n.outputs?.some(x=>x.name==='click'))) actions.push({text:clean(text(n)),element:n.name,type:attr(n,'type')??null,handler:n.outputs?.map(x=>({event:x.name,source:clean(x.handler?.source)}))??[],route:attr(n,'routerLink')||binding(n,'routerLink')||null,disabled:binding(n,'disabled')||null,line});
    if (/^h[1-6]$/.test(n.name??'')) headings.push({level:n.name,text:clean(text(n))});
    if (n.name==='app-page-header') headings.push({level:'h1',text:attr(n,'title')||binding(n,'title')||''});
    if (n.name==='summary') details.push(clean(text(n)));
    if (n.name==='table') tables.push({caption:clean((n.children??[]).filter(x=>x.name==='caption').map(text).join(' ')),headers:[]});
    if (attr(n,'role')==='dialog' || n.name==='dialog') dialogs.push({name:attr(n,'aria-label')||attr(n,'aria-labelledby')||null,line});
    children(n).forEach(c=>scan(c,label,currentForm));
  }
  (parsed.nodes??[]).forEach(n=>scan(n));
  const slug=path.basename(file,'.component.ts').replace(/[^a-z0-9]+/gi,'-');
  fields.forEach((f,i)=>f.id=slug+'-F'+String(i+1).padStart(3,'0'));
  components.set(file,{file,selector:props.get('selector')?.text??null,source_sha256:sha(source),template_sha256:sha(template),template_file:templateFile,headings,fields,actions,details,dialogs,tables,parse_errors:(parsed.errors??[]).map(x=>clean(x.msg))});
}
const routeFile=ui+'/app.routes.ts';
const routeText=await fs.readFile(routeFile,'utf8');
const ast=ts.createSourceFile(routeFile,routeText,ts.ScriptTarget.Latest,true);
const aliases=new Map();
for(const m of routeText.matchAll(/const\s+(\w+)\s*=\s*\(\)\s*=>\s*import\('([^']+)'\)/g))aliases.set(m[1],path.posix.normalize(path.posix.join(ui,m[2]+'.ts')));
const routes=[];
function routeWalk(n){
 if(ts.isObjectLiteralExpression(n)){
  const p=new Map(n.properties.filter(ts.isPropertyAssignment).map(x=>[x.name.getText(ast),x.initializer]));const r=p.get('path');
  if(r&&ts.isStringLiteral(r)){
   const body=n.getText(ast),imp=body.match(/import\('([^']+)'\)/)?.[1];
   const component=imp?path.posix.normalize(path.posix.join(ui,imp+'.ts')):classFiles.get(p.get('component')?.getText(ast))||aliases.get(p.get('loadComponent')?.getText(ast))||null;
   routes.push({route:'/'+r.text,kind:p.has('redirectTo')?'REDIRECT':'PAGE',redirect:p.get('redirectTo')?.text??null,component,protected:body.includes('authGuard'),chapter:null,verification:'DOCUMENTED BUT NOT CURRENTLY VERIFIED'});
  }
 }ts.forEachChild(n,routeWalk);
}
routeWalk(ast);
const navigationSource=await fs.readFile(ui+'/shared/seller-navigation.component.ts','utf8');
const nav=[];
const navAst=ts.createSourceFile('seller-navigation.component.ts',navigationSource,ts.ScriptTarget.Latest,true);
function navWalk(n){
 if(ts.isPropertyDeclaration(n)&&['navigationGroups','advancedNavigationGroups'].includes(n.name.getText(navAst))&&n.initializer&&ts.isArrayLiteralExpression(n.initializer)){
  const advanced=n.name.getText(navAst)==='advancedNavigationGroups';
  for(const group of n.initializer.elements){if(!ts.isObjectLiteralExpression(group))continue;const p=new Map(group.properties.filter(ts.isPropertyAssignment).map(x=>[x.name.getText(navAst),x.initializer]));const label=p.get('label')?.text;const items=p.get('items');if(!items||!ts.isArrayLiteralExpression(items))continue;for(const item of items.elements){if(!ts.isArrayLiteralExpression(item))continue;const name=item.elements[0]?.text,route=item.elements[1]?.text;if(name&&route)nav.push({label:name,route,group:label,advanced,location:(advanced?'Advanced → ':'')+label+' → '+name});}}
 }ts.forEachChild(n,navWalk);
}
navWalk(navAst);
if(!nav.length)throw Error('NAVIGATION_AST_EMPTY');
for(const r of routes){r.navigation=nav.filter(n=>n.route===r.route).map(n=>n.label);if(r.component&&!components.has(r.component))throw Error('MISSING_COMPONENT:'+r.component);}
const pageComponents=[...new Set(routes.filter(r=>r.kind==='PAGE').map(r=>r.component).filter(Boolean))];
const register=pageComponents.map((p,i)=>({...components.get(p),page_id:'P'+String(i+1).padStart(3,'0'),routes:routes.filter(r=>r.component===p).map(r=>r.route),navigation:nav.filter(n=>routes.some(r=>r.component===p&&r.route===n.route)),verification:'DOCUMENTED BUT NOT CURRENTLY VERIFIED'}));
for(const r of routes)r.chapter=register.find(c=>c.file===r.component)?.page_id??null;
let revision='UNKNOWN';try{revision=execFileSync('git',['-c','safe.directory='+process.cwd().replaceAll('\\','/'),'rev-parse','HEAD'],{encoding:'utf8'}).trim();}catch{}
const pkg=JSON.parse(await fs.readFile('package.json','utf8'));
const data={generated_at:new Date().toISOString(),edition:'0.9 evidence backed reference edition',product_version:pkg.version,revision,dirty_worktree:true,route_sha256:sha(routeText),lock_sha256:sha(await fs.readFile('package-lock.json')),fresh_authenticated_browser:false,method:'TypeScript route and component metadata AST plus Angular template AST. Static controls, conditional branches and options are not current rendered verification. No application modules, DB or provider imported.',routes,navigation:nav,pages:register,shared_components:[...components.values()].filter(c=>!pageComponents.includes(c.file)),counts:{routes:routes.length,page_routes:routes.filter(r=>r.kind==='PAGE').length,redirects:routes.filter(r=>r.kind==='REDIRECT').length,page_families:register.length,page_fields:register.reduce((n,p)=>n+p.fields.length,0),shared_fields:[...components.values()].filter(c=>!pageComponents.includes(c.file)).reduce((n,p)=>n+p.fields.length,0)}};
await fs.mkdir(base+'/source',{recursive:true});await fs.mkdir(base+'/inventory',{recursive:true});
await fs.writeFile(base+'/source/ui-inventory.json',JSON.stringify(data,null,2)+'\n');
const pages=routes.map(r=>{const p=register.find(p=>p.page_id===r.chapter);const title=p?.headings[0]?.text??(r.kind==='REDIRECT'?'Redirect':'UNKNOWN exact page title');return `| ${md(r.route)} | ${md(title)} | ${r.kind} | ${md(nav.filter(n=>n.route===r.route).map(n=>n.location).join('; ')||'Contextual link or direct route')} | ${r.chapter??'Redirect'} | ${md(r.component??r.redirect)} | ${r.verification} |`;});
const intro='# Current application inventory\n\n'+data.generated_at+'\n\n'+data.method+'\n\n'+JSON.stringify(data.counts)+'\n\nNo expired QA origin was reopened. No new QA database is authorized. Current-UI verification is not claimed. Dynamic record routes require legitimate persisted identifiers. Redirects are not separate screens.\n\n';
await fs.writeFile(base+'/source/application-inventory.md',intro+'Source titles containing interpolation are dynamic expressions, not fabricated current visible labels.\n\n| Exact route | Source page heading | Kind | Navigation location | Page family | Current source | Availability evidence |\n| --- | --- | --- | --- | --- | --- | --- |\n'+pages.join('\n')+'\n');
await fs.writeFile(base+'/inventory/page-register.md',intro+'Every page route is mapped to a dedicated route note within its shared page-family chapter. A common component is not proof that all route branches behave alike.\n\n| Route | Source page heading | Kind | Navigation | Chapter | Source | Verification |\n| --- | --- | --- | --- | --- | --- | --- |\n'+pages.join('\n')+'\n');
const fields=[...register.flatMap(p=>p.fields.map(f=>({...f,page_id:p.page_id}))),...data.shared_components.flatMap(c=>c.fields.map(f=>({...f,page_id:'SHARED'})))];
await fs.writeFile(base+'/inventory/field-register.md','# Field register\n\nStatic declarations, including conditional controls, not a rendered-control census. Every row is a source reference, not a completed field tutorial. Exact runtime-requiredness, dynamic choices and API limits must be confirmed where marked unknown. Detailed semantic overrides are maintained in source/editorial.json; raw expressions are developer-only evidence, not instructions to enter code.\n\n| Stable field ID | Page | Label or accessible name | Type | Requiredness in template | Native constraints | Static dropdown options | Source | Verification |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'+fields.map(f=>`| ${f.id} | ${f.page_id} | ${md(f.label||'UNKNOWN exact label')} | ${f.type} | ${f.required} | ${md(JSON.stringify(Object.fromEntries(Object.entries(f.attributes).filter(([k])=>['required','min','max','step','minlength','maxlength','pattern','accept','multiple'].includes(k)))))} | ${md(f.options.map(o=>o.label).join('; ')||'None statically enumerated; dynamic values UNVERIFIED')} | ${f.template_file}:${f.template_line} | ${f.verification} |`).join('\n')+'\n');
await fs.writeFile(base+'/source/control-inventory.md','# Forms actions sections and conditional controls\n\nSource-only inventory. Labels containing interpolation vary at runtime. No action was executed. Full bindings and handlers are in ui-inventory.json for maintenance review.\n\n'+register.map(p=>`## ${p.page_id} ${p.file}\n\nRoutes: ${p.routes.join(', ')}\n\nHeadings: ${p.headings.map(h=>md(h.text)).join('; ')}\n\nDisclosures: ${p.details.map(md).join('; ')||'None found'}\n\nDialogs: ${p.dialogs.length}; tables: ${p.tables.length}.\n\n| Exact source action text | Kind | Disabled condition present |\n| --- | --- | --- |\n${p.actions.map(a=>`| ${md(a.text||'Dynamic or icon-only name needs review')} | ${a.element} | ${a.disabled?'Yes; runtime evaluation unverified':'Not statically bound'} |`).join('\n')}\n`).join('\n'));
console.log(JSON.stringify(data.counts));
