$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) {
    throw "Virtual-environment Python not found: $python"
}

$inputDefinitions = @(
    @{ Preferred = "data\inputs\quality_correction.csv"; Legacy = "data\inputs\strategy1.csv" },
    @{ Preferred = "data\inputs\deep_value.csv"; Legacy = "data\inputs\strategy2.csv" },
    @{ Preferred = "data\inputs\recovery_30_50.csv"; Legacy = "data\inputs\strategy3.csv" },
    @{ Preferred = "data\inputs\technical_reversal.csv"; Legacy = "data\inputs\strategy4.csv" }
)
$inputs = foreach ($definition in $inputDefinitions) {
    if (Test-Path $definition.Preferred -PathType Leaf) {
        $definition.Preferred
    } elseif (Test-Path $definition.Legacy -PathType Leaf) {
        $definition.Legacy
    } else {
        throw "Screener export not found: $($definition.Preferred)"
    }
}
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
