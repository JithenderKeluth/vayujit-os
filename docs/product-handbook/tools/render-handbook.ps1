[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
throw 'NATIVE_WORD_AUTOMATION_DISABLED_AFTER_PRESERVATION_CHECK_FAILURE. Use a separately approved isolated renderer; do not attach to a user Office session.'
# Optional native Word fallback. It never attaches to an existing user document.
# Stop if COM returns a nonempty application instance. No security/policy setting
# or application/database service is modified. Outputs are documentation only.
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$folder=Join-Path $repo 'docs\product-handbook'
$inputPath=Join-Path $folder 'VAYUJIT_OS_Complete_Product_Handbook_Edition_0_9.docx'
$render=Join-Path $folder 'quality\render'
[void][IO.Directory]::CreateDirectory($render)
$pdf=Join-Path $render 'VAYUJIT_OS_Complete_Product_Handbook_Edition_0_9.pdf'
$receipt=[ordered]@{engine='Microsoft Word native fallback';status='NOT_EXECUTED';stage='initialize';existing_user_documents_touched=$false;opened=$false;toc_updated=$false;page_count=$null;word_version=$null;pdf_exported=$false;application_operations=0;database_operations=0;cleanup_failures=@()}
$word=$null;$doc=$null;$owned=$false
function Save-Checkpoint {
    $receipt|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $folder 'quality\word-render.json') -Encoding UTF8
    Write-Output ('Handbook render stage: '+$receipt.stage)
}
try {
    Save-Checkpoint
    $word=New-Object -ComObject Word.Application
    if($word.Documents.Count -ne 0 -or $word.ProtectedViewWindows.Count -ne 0){throw 'WORD_INSTANCE_NOT_EMPTY_STOPPED'}
    $owned=$true
    $word.Visible=$false
    $receipt.word_version=[string]$word.Version
    $receipt.stage='open_document'
    Save-Checkpoint
    $documents=$word.Documents
    $openArguments=[object[]]@($inputPath,$false,$false,$false)
    $doc=$documents.GetType().InvokeMember('Open',[Reflection.BindingFlags]::InvokeMethod,$null,$documents,$openArguments)
    $receipt.opened=$true
    $receipt.stage='update_fields'
    Save-Checkpoint
    $doc.Repaginate()
    [void]$doc.Fields.Update()
    foreach($toc in $doc.TablesOfContents){$toc.Update()}
    $doc.Repaginate()
    foreach($toc in $doc.TablesOfContents){$toc.UpdatePageNumbers()}
    $receipt.toc_updated=($doc.TablesOfContents.Count -eq 1)
    $receipt.stage='save_and_count'
    Save-Checkpoint
    $doc.Save()
    $receipt.page_count=[int]$doc.ComputeStatistics(2)
    $receipt.stage='export_pdf'
    Save-Checkpoint
    $doc.ExportAsFixedFormat($pdf,17)
    $receipt.pdf_exported=(Test-Path -LiteralPath $pdf -PathType Leaf) -and (Get-Item -LiteralPath $pdf).Length -gt 0
    $receipt.status=if($receipt.opened -and $receipt.toc_updated -and $receipt.pdf_exported){'OPEN_TOC_AND_PDF_PASS_VISUAL_REVIEW_PENDING'}else{'INCOMPLETE'}
} catch {
    $receipt.status='BLOCKED'
    $receipt.failure_type=$_.Exception.GetType().Name
    $receipt.failure_id=[string]$_.FullyQualifiedErrorId
    $inner=$_.Exception;for($level=0;$level -lt 5 -and $null -ne $inner.InnerException;$level++){$inner=$inner.InnerException}
    $receipt.native_hresult=[int]$inner.HResult
    $receipt.safe_reason=if($inner.Message -match '(?i)corrupt|unreadable|format'){'DOCUMENT_FORMAT_OR_READABILITY_ERROR'}elseif($inner.Message -match '(?i)permission|access|locked|in use'){'DOCUMENT_ACCESS_OR_LOCK_ERROR'}elseif($inner.Message -match '(?i)RPC|server|busy|rejected'){'OFFICE_AUTOMATION_SERVER_ERROR'}elseif($inner.Message -match '(?i)type|argument|mismatch'){'OFFICE_ARGUMENT_CONTRACT_ERROR'}else{'UNCLASSIFIED_OFFICE_OPEN_ERROR'}
    $receipt.raw_error_persisted=$false
    if($_.Exception.Message -eq 'WORD_INSTANCE_NOT_EMPTY_STOPPED'){$receipt.safe_code='WORD_INSTANCE_NOT_EMPTY_STOPPED'}else{$receipt.safe_code='WORD_NATIVE_RENDER_UNAVAILABLE'}
} finally {
    if($null -ne $doc){try{$save=0;$doc.Close([ref]$save)}catch{$receipt.cleanup_failures+= 'OWN_DOCUMENT_CLOSE_FAILED'};try{[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)}catch{$receipt.cleanup_failures+='DOCUMENT_REFERENCE_RELEASE_FAILED'}}
    if($owned -and $null -ne $word){try{$save=0;$word.Quit([ref]$save)}catch{$receipt.cleanup_failures+='OWN_EMPTY_WORD_QUIT_FAILED'}}
    if($null -ne $word){try{[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)}catch{$receipt.cleanup_failures+='WORD_REFERENCE_RELEASE_FAILED'}}
    $receipt|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $folder 'quality\word-render.json') -Encoding UTF8
}
$receipt|ConvertTo-Json -Depth 5
if($receipt.status -eq 'BLOCKED'){exit 1}
