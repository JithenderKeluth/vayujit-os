[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
# Native OOXML packaging only. No Word automation or application operations.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$root=Join-Path $repo 'docs\product-handbook'
$book=Get-Content -LiteralPath (Join-Path $root 'compact\source.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$output=Join-Path $root 'VAYUJIT_OS_Product_Handbook_Compact.docx'
$body=New-Object Text.StringBuilder
$rels=New-Object 'Collections.Generic.List[string]'
$images=New-Object 'Collections.Generic.List[object]'
function X([string]$s){return [Security.SecurityElement]::Escape($s)}
function Run([string]$s,[string]$pr=''){return '<w:r><w:rPr>'+$pr+'</w:rPr><w:t xml:space="preserve">'+(X $s)+'</w:t></w:r>'}
function P([string]$s,[string]$style='Normal'){return '<w:p><w:pPr><w:pStyle w:val="'+$style+'"/></w:pPr>'+(Run $s)+'</w:p>'}
function Sect([bool]$landscape){
 $size=if($landscape){'<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'}else{'<w:pgSz w:w="12240" w:h="15840"/>'}
 return '<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:type w:val="nextPage"/>'+$size+'<w:pgMar w:top="1008" w:right="1008" w:bottom="1008" w:left="1008" w:header="360" w:footer="360"/></w:sectPr>'
}
$imageNo=0
for($index=0;$index -lt $book.pages.Count;$index++){
 $page=$book.pages[$index]
 switch($page.kind){
  'cover'{
   [void]$body.Append((P $book.title 'Title'))
   [void]$body.Append((P $book.subtitle 'Subtitle'))
   [void]$body.Append((P ('Updated '+$book.date) 'Small'))
   [void]$body.Append((P 'For the owner of a single seller business in India' 'Heading2'))
   [void]$body.Append((P 'Use this guide to choose a task, find the right workspace, enter genuine information and understand the next step. Start with research if you have no product, or with Products and Catalog if you already know what you sell.'))
   [void]$body.Append((P 'The guide covers product research, suppliers, economics, Catalog, inventory, marketplace preparation, finance, content, marketing and daily operations. Each task explains where to go, what to check and how to continue.'))
   [void]$body.Append((P 'Screenshots show genuine historical synthetic examples. Names, quantities and amounts in them are not real business records and must not be copied. Current labels or layout may differ. Larger screenshot pages follow the relevant tasks.'))
   [void]$body.Append((P 'The application does not guarantee sales, supplier trust or profitability. Local readiness and approval do not establish live marketplace access or authorize publication, contact, payment or advertising spend. Keep unknown facts unknown.'))
   [void]$body.Append((P 'Use the detailed handbook when you need the full page and field reference. This edition concentrates on the main seller journeys rather than an exhaustive technical inventory.'))
  }
  'contents'{
   [void]$body.Append((P $page.title 'Heading1'))
   [void]$body.Append((P 'Choose a numbered task below. Links open its section; the numbers identify tasks, not page numbers.' 'Small'))
   foreach($entry in $page.entries){[void]$body.Append('<w:p><w:pPr><w:pStyle w:val="Contents"/></w:pPr><w:hyperlink w:anchor="'+$entry.anchor+'">'+(Run ($entry.number.ToString()+'  '+$entry.title) '<w:color w:val="075462"/><w:u w:val="single"/>')+'</w:hyperlink></w:p>')}
  }
  'task'{
   [void]$body.Append('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:bookmarkStart w:id="'+$page.number+'" w:name="'+$page.anchor+'"/>'+(Run ($page.number.ToString()+'  '+$page.title))+'<w:bookmarkEnd w:id="'+$page.number+'"/></w:p>')
   [void]$body.Append((P ('Where to go: '+$page.where) 'Location'))
   [void]$body.Append((P $page.intro))
   for($n=0;$n -lt $page.steps.Count;$n++){[void]$body.Append((P (($n+1).ToString()+'. '+$page.steps[$n]) 'Step'))}
   [void]$body.Append((P ('Before you proceed: '+$page.check)))
   [void]$body.Append((P ('Next: '+$page.next) 'Next'))
  }
  'screenshot'{
   $imageNo++;$id='rId'+(10+$imageNo);$name='screen-'+$imageNo+'.png'
   [void]$body.Append((P ('Screen guide for task '+$page.number+' '+$page.title) 'ScreenTitle'))
   $imagePath=[IO.Path]::GetFullPath((Join-Path $repo $page.path))
   if(-not $imagePath.StartsWith((Join-Path $root 'screenshots')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'SCREENSHOT_SCOPE_INVALID'}
   # Uniform scaling only. Full screenshot bytes and aspect ratio are preserved.
   $scale=[Math]::Min(8778240.0/[double]$page.width,5097780.0/[double]$page.height)
   $cx=[long]([double]$page.width*$scale);$cy=[long]([double]$page.height*$scale)
   $rels.Add('<Relationship Id="'+$id+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/'+$name+'"/>')
   $images.Add([pscustomobject]@{path=$imagePath;name=$name})
   [void]$body.Append('<w:p><w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="'+$cx+'" cy="'+$cy+'"/><wp:docPr id="'+$imageNo+'" name="Screenshot '+$imageNo+'" descr="'+(X $page.alt)+'"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="'+$name+'"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="'+$id+'"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="'+$cx+'" cy="'+$cy+'"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
   [void]$body.Append((P $page.caption 'Caption'))
  }
  default{throw 'UNSUPPORTED_COMPACT_PAGE'}
 }
 $section=Sect ($page.kind -eq 'screenshot')
 if($index -eq $book.pages.Count-1){[void]$body.Append($section)}else{[void]$body.Append('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>'+$section+'</w:pPr><w:r><w:rPr><w:sz w:val="2"/></w:rPr><w:t></w:t></w:r></w:p>')}
}
$ns=' xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
$document='<?xml version="1.0" encoding="UTF-8"?><w:document'+$ns+' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>'+$body.ToString()+'</w:body></w:document>'
$styles='<?xml version="1.0" encoding="UTF-8"?><w:styles'+$ns+'><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="000000"/><w:lang w:val="en-IN"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="140" w:line="264" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
foreach($entry in @(@('Title',30,240),@('Subtitle',19,240),@('Heading1',21,220),@('Heading2',14,180),@('ScreenTitle',16,100))){$id=$entry[0];$outline=if($id -eq 'Heading1'){'<w:outlineLvl w:val="0"/>'}elseif($id -eq 'Heading2'){'<w:outlineLvl w:val="1"/>'}else{''};$styles+='<w:style w:type="paragraph" w:styleId="'+$id+'"><w:name w:val="'+$id+'"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="0" w:after="'+$entry[2]+'"/>'+$outline+'</w:pPr><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="'+($entry[1]*2)+'"/></w:rPr></w:style>'}
foreach($id in @('Location','Next','Step','Contents','Caption','Small')){
 $size=if($id -in @('Caption','Small')){20}else{22}
 $spacing=if($id -eq 'Contents'){120}elseif($id -eq 'Caption'){60}else{140}
 $pr=if($id -in @('Location','Next')){'<w:b/>'}elseif($id -eq 'Caption'){'<w:i/>'}else{''}
 $styles+='<w:style w:type="paragraph" w:styleId="'+$id+'"><w:name w:val="'+$id+'"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="'+$spacing+'" w:line="264" w:lineRule="auto"/>'+$(if($id -eq 'Step'){'<w:ind w:left="260" w:hanging="260"/>'}else{''})+'</w:pPr><w:rPr><w:sz w:val="'+$size+'"/><w:color w:val="000000"/>'+$pr+'</w:rPr></w:style>'
}
$styles+='</w:styles>'
$relationship='<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'+($rels -join '')+'</Relationships>'
$types='<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'
function AddEntry([IO.Compression.ZipArchive]$zip,[string]$name,[string]$content){$entry=$zip.CreateEntry($name,[IO.Compression.CompressionLevel]::Optimal);$writer=New-Object IO.StreamWriter($entry.Open(),(New-Object Text.UTF8Encoding($false)));try{$writer.Write($content)}finally{$writer.Dispose()}}
$stream=[IO.File]::Open($output,[IO.FileMode]::Create,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$zip=New-Object IO.Compression.ZipArchive($stream,[IO.Compression.ZipArchiveMode]::Create,$false)
try{
 AddEntry $zip '[Content_Types].xml' $types
 AddEntry $zip '_rels/.rels' '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'
 AddEntry $zip 'word/document.xml' $document
 AddEntry $zip 'word/styles.xml' $styles
 AddEntry $zip 'word/_rels/document.xml.rels' $relationship
 AddEntry $zip 'word/settings.xml' ('<w:settings'+$ns+'><w:updateFields w:val="true"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
 AddEntry $zip 'word/footer1.xml' ('<w:ftr'+$ns+'><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'+(Run 'VAYUJIT OS  |  ' '<w:sz w:val="18"/>')+'<w:fldSimple w:instr="PAGE"><w:r><w:t></w:t></w:r></w:fldSimple></w:p></w:ftr>')
 AddEntry $zip 'docProps/core.xml' '<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>VAYUJIT OS Product Handbook</dc:title><dc:subject>Practical seller guide</dc:subject><dc:creator>VAYUJIT documentation</dc:creator></cp:coreProperties>'
 foreach($image in $images){[void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$image.path,('word/media/'+$image.name),[IO.Compression.CompressionLevel]::Optimal)}
}finally{$zip.Dispose();$stream.Dispose()}
[ordered]@{status='GENERATED_NOT_RENDERED';output='docs/product-handbook/VAYUJIT_OS_Product_Handbook_Compact.docx';designed_pages=$book.designed_page_count;actual_pages=$null;sections=$book.sections;screenshots=$imageNo;application_operations=0;database_operations=0;word_automation=$false}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'compact\generation.json') -Encoding UTF8
Get-Content -LiteralPath (Join-Path $root 'compact\generation.json') -Raw -Encoding UTF8
