$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$source = Join-Path $repoRoot 'docs\CLE_Dgate全量四臂三张上限实验结果_20261019.docx'
$qa = Join-Path $repoRoot 'translation_work\diagnostics\20261019\cle_memory_q\full_gate_cap3_v4\report_render'
New-Item -ItemType Directory -Path $qa -Force | Out-Null
$pdf = Join-Path $qa 'report.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$document = $null
try {
    $document = $word.Documents.Open($source, $false, $true)
    $document.Repaginate()
    $document.ExportAsFixedFormat($pdf, 17)
    Write-Output "Rendered pages: $($document.ComputeStatistics(2))"
} finally {
    if ($null -ne $document) { $document.Close(0) }
    $word.Quit()
}
& 'C:\Users\fujunye\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe' -scale-to 1600 -png $pdf (Join-Path $qa 'page')
if ($LASTEXITCODE -ne 0) { throw 'Page rendering failed' }
Write-Output $qa
