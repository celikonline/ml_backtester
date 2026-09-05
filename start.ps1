$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Once setup.ps1 ile kurulumu tamamlayin. README.md dosyasina bakin.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend\dist\index.html'))) {
    Push-Location (Join-Path $PSScriptRoot 'frontend')
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'React derlemesi basarisiz.' }
    } finally { Pop-Location }
}
Write-Host 'Regime Lab: http://127.0.0.1:8000' -ForegroundColor Green
Write-Host 'Durdurmak icin Ctrl+C kullanin.'
& $pythonExe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
