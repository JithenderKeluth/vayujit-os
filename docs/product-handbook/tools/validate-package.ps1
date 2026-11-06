[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$file=Join-Path $repo 'docs\product-handbook\VAYUJIT_OS_Complete_Product_Handbook_Reference_Draft_0_9_1.docx'
$zip=[IO.Compression.ZipFile]::OpenRead($file)
$xmlErrors=0;$docs=@{};$images=0
try {
    foreach($entry in $zip.Entries){
        if($entry.FullName -like 'word/media/*'){$images++}
        if($entry.FullName -match '\.(xml|rels)$'){
            $stream=$entry.Open()
            try{
                $settings=New-Object Xml.XmlReaderSettings
                $settings.DtdProcessing=[Xml.DtdProcessing]::Prohibit
                $settings.XmlResolver=$null
                $reader=[Xml.XmlReader]::Create($stream,$settings)
                $doc=New-Object Xml.XmlDocument
                $doc.XmlResolver=$null
                $doc.Load($reader)
                $docs[$entry.FullName]=$doc
                $reader.Dispose()
            }catch{$xmlErrors++}finally{$stream.Dispose()}
        }
    }
    $main=$docs['word/document.xml']
    $ns=New-Object Xml.XmlNamespaceManager($main.NameTable)
    $ns.AddNamespace('w','http://schemas.openxmlformats.org/wordprocessingml/2006/main')
    $ns.AddNamespace('wp','http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing')
    $missingAlt=@($main.SelectNodes('//wp:docPr[not(@descr) or @descr=""]',$ns)).Count
    $tables=@($main.SelectNodes('//w:tbl',$ns)).Count
    $headers=@($main.SelectNodes('//w:tbl/w:tr[1]/w:trPr/w:tblHeader',$ns)).Count
    $toc=@($main.SelectNodes('//w:instrText',$ns)|Where-Object{$_.InnerText -match 'TOC'}).Count
    $headings=@($main.SelectNodes('//w:pPr/w:pStyle[@w:val="Heading1"]',$ns)).Count
    $placeholders=(@($main.SelectNodes('//w:t',$ns)|Where-Object{$_.InnerText -match 'Update this contents field in Word before relying on page references'}).Count -gt 0)
    $macros=@($zip.Entries|Where-Object{$_.FullName -match 'vbaProject|embeddings/'}).Count
    $relDoc=$docs['word/_rels/document.xml.rels']
    $remote=@($relDoc.DocumentElement.ChildNodes|Where-Object{$_.TargetMode -eq 'External' -and $_.Target -match '^(https?|file|\\\\):?'}).Count
    [pscustomobject]@{xml_parse_errors=$xmlErrors;embedded_images=$images;images_missing_alt=$missingAlt;tables=$tables;tables_with_repeating_header=$headers;toc_fields=$toc;toc_has_unupdated_placeholder=$placeholders;toc_cached_values_verified=$false;chapter_headings=$headings;macro_or_ole_entries=$macros;remote_external_relationships=$remote;layout_verified=$false}|ConvertTo-Json -Compress
    if($xmlErrors -or $missingAlt -or $tables -ne $headers -or $macros -or $remote){exit 1}
}finally{$zip.Dispose()}
