[CmdletBinding()]
param([ValidatePattern('^VAYUJIT_OS_Complete_Product_Handbook(?:_Edition_0_9|_Reference_Draft(?:_0_9_1)?)?\.docx$')][string]$OutputName='VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Native OOXML fallback: writes only this documentation package. No Office,
# application, database, provider, process-control or network operation here.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$handbook = Join-Path $repo 'docs\product-handbook'
$book = Get-Content -LiteralPath (Join-Path $handbook 'source\book.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$output = Join-Path $handbook $OutputName
$body = New-Object Text.StringBuilder
$relationships = New-Object 'Collections.Generic.List[string]'
$media = New-Object 'Collections.Generic.List[object]'
$imageNumber = 0
$relationNumber = 10
$headingNumber = 0
$chapterNumber = 0
function Escape-Xml([string]$value) { return [Security.SecurityElement]::Escape($value) }
function Text-Run([string]$value, [string]$properties = '') {
    return '<w:r><w:rPr>' + $properties + '</w:rPr><w:t xml:space="preserve">' + (Escape-Xml $value) + '</w:t></w:r>'
}
function Paragraph([string]$value, [string]$style='Normal', [bool]$keep=$false) {
    $next = if ($keep) {'<w:keepNext/>'} else {''}
    return '<w:p><w:pPr><w:pStyle w:val="'+$style+'"/>'+$next+'</w:pPr>'+(Text-Run $value)+'</w:p>'
}
function Add-Entry([IO.Compression.ZipArchive]$archive,[string]$name,[string]$content) {
    $entry=$archive.CreateEntry($name,[IO.Compression.CompressionLevel]::Optimal)
    $writer=New-Object IO.StreamWriter($entry.Open(),(New-Object Text.UTF8Encoding($false)))
    try {$writer.Write($content)} finally {$writer.Dispose()}
}
[void]$body.Append((Paragraph $book.title 'Title'))
[void]$body.Append((Paragraph 'Beginner user manual and reference' 'Subtitle'))
[void]$body.Append((Paragraph ('Edition '+$book.edition+'  '+$book.editionName)))
[void]$body.Append((Paragraph ('Updated '+$book.date+'  Product package '+$book.product)))
[void]$body.Append((Paragraph 'For the VAYUJIT owner and a first time Indian e commerce seller'))
[void]$body.Append((Paragraph 'Learn the supported local workflows, understand evidence and unknowns, and stop at the correct human approval boundary. No live transaction, guaranteed product outcome or production readiness is implied.'))
[void]$body.Append((Paragraph 'Historical synthetic screenshots are labelled. Current UI verification gaps are explicit.'))
[void]$body.Append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
[void]$body.Append((Paragraph 'Contents' 'TOCHeading'))
[void]$body.Append('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \o "1-2" \h \z \u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Update this contents field in Word before relying on page references.</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
foreach($block in $book.blocks) {
    switch ($block.kind) {
        'heading' {
            $headingNumber++
            $display = [string]$block.text
            if ($block.level -eq 1) {$chapterNumber++;$display=[string]$chapterNumber+' '+$display}
            [void]$body.Append('<w:p><w:pPr><w:pStyle w:val="Heading'+$block.level+'"/></w:pPr><w:bookmarkStart w:id="'+$headingNumber+'" w:name="hb_'+$headingNumber+'"/>'+(Text-Run $display)+'<w:bookmarkEnd w:id="'+$headingNumber+'"/></w:p>')
        }
        'paragraph' { [void]$body.Append((Paragraph ([string]$block.text))) }
        'hyperlink' {
            $relationNumber++;$id='rId'+$relationNumber
            $relationships.Add('<Relationship Id="'+$id+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="'+(Escape-Xml ([string]$block.target))+'" TargetMode="External"/>')
            [void]$body.Append('<w:p><w:hyperlink r:id="'+$id+'">'+(Text-Run ([string]$block.text) '<w:rStyle w:val="Hyperlink"/>')+'</w:hyperlink></w:p>')
        }
        'table' {
            $columns=$block.headers.Count
            $widths=@();for($c=0;$c -lt $columns;$c++){$percent=if($block.widths){$block.widths[$c]}else{100.0/$columns};$widths+= [int][Math]::Round(9360*$percent/100)}
            $borders='<w:tblBorders>';foreach($edge in @('top','left','bottom','right','insideH','insideV')){$borders+='<w:'+$edge+' w:val="single" w:sz="4" w:color="D9D9D9"/>'};$borders+='</w:tblBorders>'
            [void]$body.Append('<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblLayout w:type="fixed"/>'+$borders+'<w:tblCellMar><w:top w:w="85" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="85" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>')
            foreach($w in $widths){[void]$body.Append('<w:gridCol w:w="'+$w+'"/>')};[void]$body.Append('</w:tblGrid>')
            $allRows=New-Object 'Collections.Generic.List[object]';$allRows.Add($block.headers);foreach($row in $block.rows){$allRows.Add($row)}
            for($r=0;$r -lt $allRows.Count;$r++){
                $header=if($r -eq 0){'<w:tblHeader/>'}else{''}
                [void]$body.Append('<w:tr><w:trPr><w:cantSplit/>'+$header+'</w:trPr>')
                for($c=0;$c -lt $columns;$c++){
                    $fill=if($r -eq 0){'173A49'}elseif($r%2 -eq 0){'F0F5F7'}else{'FFFFFF'}
                    $prop=if($r -eq 0){'<w:b/><w:color w:val="FFFFFF"/>'}else{'<w:color w:val="000000"/>'}
                    $align=if($columns -ge 3 -and $c -eq 0){'left'}else{'left'}
                    [void]$body.Append('<w:tc><w:tcPr><w:tcW w:w="'+$widths[$c]+'" w:type="dxa"/><w:shd w:fill="'+$fill+'"/><w:vAlign w:val="center"/></w:tcPr><w:p><w:pPr><w:pStyle w:val="TableText"/><w:jc w:val="'+$align+'"/></w:pPr>'+(Text-Run ([string]$allRows[$r][$c]) ($prop+'<w:sz w:val="21"/>'))+'</w:p></w:tc>')
                }
                [void]$body.Append('</w:tr>')
            }
            [void]$body.Append('</w:tbl>');[void]$body.Append((Paragraph '' 'TableAfter'))
        }
        'image' {
            $imageNumber++;$relationNumber++;$id='rId'+$relationNumber;$name='screenshot-'+$imageNumber+'.png'
            $imagePath=[IO.Path]::GetFullPath((Join-Path $repo ([string]$block.path)))
            if(-not $imagePath.StartsWith($handbook+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'HANDBOOK_IMAGE_SCOPE_INVALID'}
            if(-not (Test-Path -LiteralPath $imagePath -PathType Leaf)){throw 'HANDBOOK_IMAGE_MISSING'}
            $maxWidth=5943600.0;$maxHeight=5577840.0
            $scale=[Math]::Min($maxWidth/[double]$block.width,$maxHeight/[double]$block.height)
            if([double]$block.width -lt 700){$scale=[Math]::Min($scale,2743200.0/[double]$block.width)}
            $cx=[long]([double]$block.width*$scale);$cy=[long]([double]$block.height*$scale)
            $relationships.Add('<Relationship Id="'+$id+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/'+$name+'"/>')
            $media.Add([pscustomobject]@{path=$imagePath;name=$name})
            [void]$body.Append('<w:p><w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="'+$cx+'" cy="'+$cy+'"/><wp:docPr id="'+$imageNumber+'" name="Figure '+$block.figure+'" descr="'+(Escape-Xml ([string]$block.alt))+'"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="'+$name+'"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="'+$id+'"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="'+$cx+'" cy="'+$cy+'"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
            [void]$body.Append((Paragraph ([string]$block.caption) 'Caption'))
        }
        'diagram' {
            [void]$body.Append((Paragraph 'The connected seller journey' 'Heading2'))
            $stepIndex=0;foreach($s in $block.steps){$stepIndex++;[void]$body.Append((Paragraph ([string]$stepIndex+'  '+[string]$s) 'DiagramStep'));if($stepIndex -lt $block.steps.Count){[void]$body.Append((Paragraph ([string][char]0x2193) 'DiagramStep'))}}
            [void]$body.Append((Paragraph 'Read from top to bottom. A blocked or unsupported stage stops at its evidence or authorization boundary. This is an explanatory journey diagram, not an application screenshot.'))
        }
        default {throw 'UNSUPPORTED_HANDBOOK_BLOCK'}
    }
}
$section='<w:sectPr><w:headerReference w:type="default" r:id="rId2"/><w:footerReference w:type="default" r:id="rId3"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1440" w:bottom="1080" w:left="1440" w:header="500" w:footer="500"/><w:titlePg/></w:sectPr>'
$document='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>'+$body.ToString()+$section+'</w:body></w:document>'
$styles='<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="000000"/><w:lang w:val="en-IN"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="264" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>'
$styles+='<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
foreach($s in @(@('Title',34,0),@('Subtitle',20,0),@('TOCHeading',20,0),@('Heading1',21,0),@('Heading2',16,1),@('Heading3',12,2))){$id=[string]$s[0];$size=[int]$s[1]*2;$outline=if($id.StartsWith('Heading')){'<w:outlineLvl w:val="'+$s[2]+'"/>'}else{''};$break=if($id -eq 'Heading1'){'<w:pageBreakBefore/>'}else{''};$styles+='<w:style w:type="paragraph" w:styleId="'+$id+'"><w:name w:val="'+$id+'"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="100"/>'+$outline+$break+'</w:pPr><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="'+$size+'"/></w:rPr></w:style>'}
$styles+='<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="40" w:after="160"/></w:pPr><w:rPr><w:i/><w:sz w:val="20"/><w:color w:val="000000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="40" w:line="250" w:lineRule="auto"/></w:pPr></w:style><w:style w:type="paragraph" w:styleId="TableAfter"><w:name w:val="Table After"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="70"/></w:pPr><w:rPr><w:sz w:val="8"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="DiagramStep"><w:name w:val="Diagram Step"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:ind w:left="360"/><w:spacing w:after="100"/></w:pPr><w:rPr><w:b/></w:rPr></w:style><w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:rPr><w:color w:val="07596A"/><w:u w:val="single"/></w:rPr></w:style></w:styles>'
$header='<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="right"/></w:pPr>'+(Text-Run ('VAYUJIT OS  Product Handbook  Edition '+$book.edition) '<w:sz w:val="18"/><w:color w:val="000000"/>')+'</w:p></w:hdr>'
$footer='<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'+(Text-Run 'Page ' '<w:sz w:val="18"/>')+'<w:fldSimple w:instr="PAGE"><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>'
$rels='<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/><Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>' + ($relationships -join '')+'</Relationships>'
$types='<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'
$rootRels='<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'
$core='<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>VAYUJIT OS Complete Product Handbook</dc:title><dc:creator>VAYUJIT documentation</dc:creator><dc:description>Evidence backed beginner reference edition with explicit verification gaps</dc:description></cp:coreProperties>'
$stream=[IO.File]::Open($output,[IO.FileMode]::Create,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$zip=New-Object IO.Compression.ZipArchive($stream,[IO.Compression.ZipArchiveMode]::Create,$false)
try {
    Add-Entry $zip '[Content_Types].xml' $types
    Add-Entry $zip '_rels/.rels' $rootRels
    Add-Entry $zip 'word/document.xml' $document
    Add-Entry $zip 'word/styles.xml' $styles
    Add-Entry $zip 'word/_rels/document.xml.rels' $rels
    Add-Entry $zip 'word/header1.xml' $header
    Add-Entry $zip 'word/footer1.xml' $footer
    Add-Entry $zip 'word/settings.xml' '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:updateFields w:val="true"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>'
    Add-Entry $zip 'docProps/core.xml' $core
    foreach($m in $media){[void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$m.path,('word/media/'+$m.name),[IO.Compression.CompressionLevel]::Optimal)}
} finally {$zip.Dispose();$stream.Dispose()}
$receipt=[ordered]@{status='GENERATED_NOT_RENDERED';builder='Windows native OOXML fallback';chapters=$chapterNumber;images=$imageNumber;heading_count=$headingNumber;bytes=(Get-Item -LiteralPath $output).Length;output=('docs/product-handbook/'+$OutputName);application_operations=0;database_operations=0}
$receipt|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $handbook 'quality\generation.json') -Encoding UTF8
$receipt|ConvertTo-Json -Depth 5
