$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) {
    throw "Virtual-environment Python not found: $python"
}

$inputs = @(
    "data\inputs\strategy1.csv",
    "data\inputs\strategy2.csv",
    "data\inputs\strategy3.csv",
    "data\inputs\strategy4.csv"
)
$today = (Get-Date).Date
foreach ($inputFile in $inputs) {
    if (-not (Test-Path $inputFile -PathType Leaf)) {
        throw "Screener export not found: $inputFile"
    }
    $file = Get-Item $inputFile
    if ($file.Length -eq 0) {
        throw "Screener export is empty: $inputFile"
    }
    if ($file.LastWriteTime.Date -ne $today) {
        throw "Screener export is not dated today; refresh it before screening: $inputFile"
    }
}

& $python app.py `
    --strategy-1 $inputs[0] `
    --strategy-2 $inputs[1] `
    --strategy-3 $inputs[2] `
    --strategy-4 $inputs[3] `
    --output screening_results.xlsx `
    --strategy-results-dir strategy_results

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
