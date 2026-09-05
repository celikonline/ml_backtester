param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $Python -c "import sys; assert (3,11) <= sys.version_info[:2] <= (3,12), 'Python 3.11 veya 3.12 kullanin.'"
if ($LASTEXITCODE -ne 0) { throw 'Uyumlu Python yolunu -Python parametresiyle belirtin.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Sanal ortam olusturulamadi.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python bagimliliklari kurulamadi.' }
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Node bagimliliklari kurulamadi.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'React derlemesi basarisiz.' }
} finally { Pop-Location }
Write-Host 'Kurulum tamamlandi. .\start.ps1 ile baslatin.' -ForegroundColor Green
