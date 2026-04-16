param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [Parameter(Mandatory = $true)]
    [string]$CertificateThumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

# FIX: [5] Windows signing helper for release binaries.
if (-not (Test-Path $ExecutablePath)) {
    Write-Error "Executable not found: $ExecutablePath"
    exit 1
}

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    Write-Error "signtool.exe not found. Install Windows SDK signing tools."
    exit 1
}

& $signtool.Path sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 "$ExecutablePath"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Signing failed for $ExecutablePath"
    exit $LASTEXITCODE
}

Write-Host "Signing completed: $ExecutablePath"
