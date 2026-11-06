[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$file=Join-Path $root 'VAYUJIT_OS_Product_Handbook_Compact.docx'
$zip=[IO.Compression.ZipFile]::OpenRead($file)
$errors=0;$docs=@{}
try{
 foreach($entry in $zip.Entries){
  if($entry.FullName -match '\.(xml|rels)$'){
   $stream=$entry.Open()
   try{
    $settings=New-Object Xml.XmlReaderSettings;$settings.DtdProcessing=[Xml.DtdProcessing]::Prohibit;$settings.XmlResolver=$null
    $reader=[Xml.XmlReader]::Create($stream,$settings);$doc=New-Object Xml.XmlDocument;$doc.XmlResolver=$null;$doc.Load($reader);$docs[$entry.FullName]=$doc;$reader.Dispose()
   }catch{$errors++}finally{$stream.Dispose()}
  }
 }
 $d=$docs['word/document.xml'];$n=New-Object Xml.XmlNamespaceManager($d.NameTable)
 $n.AddNamespace('w','http://schemas.openxmlformats.org/wordprocessingml/2006/main');$n.AddNamespace('wp','http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing');$n.AddNamespace('a','http://schemas.openxmlformats.org/drawingml/2006/main')
 $sections=@($d.SelectNodes('//w:sectPr',$n));$shots=@($d.SelectNodes('//wp:docPr',$n));$links=@($d.SelectNodes('//w:hyperlink[@w:anchor]',$n));$anchors=@($d.SelectNodes('//w:bookmarkStart',$n) | ForEach-Object {$_.GetAttribute('name',$n.LookupNamespace('w'))})
 $missingLinks=@($links | Where-Object {$_.GetAttribute('anchor',$n.LookupNamespace('w')) -notin $anchors}).Count
 $missingAlt=@($shots | Where-Object {-not $_.GetAttribute('descr')}).Count
 $externals=@($docs['word/_rels/document.xml.rels'].DocumentElement.ChildNodes | Where-Object {$_.GetAttribute('TargetMode') -eq 'External'}).Count
 $badMedia=0;$source=Get-Content (Join-Path $root 'compact/source.json') -Raw -Encoding UTF8|ConvertFrom-Json
 $expected=@($source.pages | Where-Object kind -eq 'screenshot')
 for($i=0;$i -lt $expected.Count;$i++){
  $entry=$zip.GetEntry('word/media/screen-'+($i+1)+'.png');if(-not $entry){$badMedia++;continue}
  $stream=$entry.Open();$hash=[Security.Cryptography.SHA256]::Create()
  try{$digest=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant();if($digest -ne $expected[$i].sha256){$badMedia++}}finally{$hash.Dispose();$stream.Dispose()}
 }
 $landscape=@($d.SelectNodes('//w:sectPr/w:pgSz[@w:orient="landscape"]',$n)).Count
 $passes=$errors -eq 0 -and $sections.Count -eq 67 -and $landscape -eq 19 -and $shots.Count -eq 19 -and $missingAlt -eq 0 -and $missingLinks -eq 0 -and $externals -eq 0 -and $badMedia -eq 0
 $result=[ordered]@{status=$(if($passes){'STRUCTURAL_PASS_RENDER_PENDING'}else{'FAIL'});xml_errors=$errors;designed_page_sections=$sections.Count;landscape_screenshot_sections=$landscape;embedded_images=$shots.Count;images_missing_alt=$missingAlt;image_hash_mismatches=$badMedia;internal_navigation_links=$links.Count;broken_links=$missingLinks;external_relationships=$externals;actual_page_count=$null;word_open_verified=$false;visual_layout_verified=$false}
 $result|ConvertTo-Json|Set-Content (Join-Path $root 'compact/validation.json') -Encoding UTF8
 $result|ConvertTo-Json
 if(-not $passes){exit 1}
}finally{$zip.Dispose()}
