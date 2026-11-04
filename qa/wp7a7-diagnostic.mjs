// Small allowlisted classifications only; raw child output is never persisted.
export function browserDiagnostic(output) {
  const classification = ['ReferenceError','TypeError','SyntaxError','RangeError','ENOENT','EACCES','EPERM','ERR_MODULE_NOT_FOUND'].find(v=>output.includes(v)) || 'UNCLASSIFIED_BROWSER_CHILD';
  const source = /(?:qa[\\/])([a-z0-9-]+\.mjs):(\d+):(\d+)/i.exec(output);
  const known = ['Cannot access','is not defined','is not a function','not iterable','Unexpected token','no such file or directory','Maximum call stack'].find(v=>output.includes(v)) || null;
  return {classification, diagnostic:known, source:source?{file:'qa/'+source[1],line:Number(source[2]),column:Number(source[3])}:null,raw_output_persisted:false};
}
