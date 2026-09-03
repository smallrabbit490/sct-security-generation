param(
    [switch]$PruneUnauthorized
)

$ErrorActionPreference = 'Stop'

# Safe local diagnostic: never print or persist the key material itself.
$repoRoot = Split-Path -Parent $PSScriptRoot
$keyFile = Join-Path $repoRoot 'local_secrets\chatanywhereapi使用\apikey.txt'
$outDir = Join-Path $repoRoot 'translation_work\chatanywhere_key_check'
$model = 'deepseek-v4-flash'
$endpoint = 'https://api.chatanywhere.tech/v1/chat/completions'

if (-not (Test-Path -LiteralPath $keyFile)) {
    throw "Missing local key file: $keyFile"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$keys = @(Get-Content -LiteralPath $keyFile | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$results = @()

for ($index = 0; $index -lt $keys.Count; $index++) {
    $key = $keys[$index]
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $httpStatus = $null
    $status = 'error'
    $errorType = $null
    $body = @{ model = $model; messages = @(@{ role = 'user'; content = 'Reply with OK.' }); max_tokens = 8; temperature = 0 } | ConvertTo-Json -Depth 5

    try {
        $response = Invoke-WebRequest -UseBasicParsing -SkipCertificateCheck `
            -Uri $endpoint -Method Post -Headers @{ Authorization = "Bearer $key" } `
            -ContentType 'application/json' -Body $body -TimeoutSec 45
        $httpStatus = [int]$response.StatusCode
        if ($httpStatus -ge 200 -and $httpStatus -lt 300) {
            $status = 'ok'
        } elseif ($httpStatus -in 401, 403) {
            $errorType = 'invalid_or_unauthorized'
        } elseif ($httpStatus -eq 429) {
            $errorType = 'rate_limited_or_quota'
        } elseif ($httpStatus -ge 500) {
            $errorType = 'provider_error'
        } else {
            $errorType = 'request_error'
        }
    } catch {
        if ($_.Exception.Response) {
            $httpStatus = [int]$_.Exception.Response.StatusCode
        }
        $message = $_.Exception.Message
        if ($httpStatus -in 401, 403) {
            $errorType = 'invalid_or_unauthorized'
        } elseif ($httpStatus -eq 429) {
            $errorType = 'rate_limited_or_quota'
        } elseif ($httpStatus -ge 500) {
            $errorType = 'provider_error'
        } elseif ($message -match 'timeout|timed out') {
            $errorType = 'timeout'
        } else {
            $errorType = 'request_error'
        }
    }

    $watch.Stop()
    $results += [ordered]@{
        key_index = $index + 1
        status = $status
        http_status = $httpStatus
        error_type = $errorType
        latency_ms = $watch.ElapsedMilliseconds
        model = $model
    }
}

if ($PruneUnauthorized) {
    $successfulIndexes = @(
        for ($index = 0; $index -lt $results.Count; $index++) {
            if ($results[$index].status -eq 'ok') {
                $index
            }
        }
    )
    $unauthorizedCount = @($results | Where-Object { $_.http_status -in 401, 403 }).Count
    $unexpectedCount = $results.Count - $successfulIndexes.Count - $unauthorizedCount
    if ($successfulIndexes.Count -ne 1) {
        throw "Refusing to prune: expected exactly one working key, found $($successfulIndexes.Count)."
    }
    if ($unexpectedCount -ne 0) {
        throw "Refusing to prune: $unexpectedCount key(s) had a status other than success or unauthorized."
    }

    $keyDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $keyFile))
    $resolvedKeyFile = [IO.Path]::GetFullPath($keyFile)
    $tempFile = [IO.Path]::GetFullPath((Join-Path $keyDirectory 'apikey.prune.tmp'))
    if ([IO.Path]::GetDirectoryName($resolvedKeyFile) -ne $keyDirectory -or
        [IO.Path]::GetDirectoryName($tempFile) -ne $keyDirectory) {
        throw 'Refusing to prune outside the configured local key directory.'
    }

    [IO.File]::WriteAllText($tempFile, $keys[$successfulIndexes[0]] + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($tempFile, $resolvedKeyFile, $true)
    Write-Host "Pruned $unauthorizedCount unauthorized key(s); retained 1 working key."
}

[ordered]@{
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    endpoint = $endpoint
    request_policy = 'one minimal request per non-empty key; key material is never written'
    key_count = $keys.Count
    results = $results
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outDir 'chatanywhere_key_check.json') -Encoding UTF8

$results | Format-Table -AutoSize
