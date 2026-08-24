$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

$env:USE_TF = "0"
$env:TF_CPP_MIN_LOG_LEVEL = "2"

$DotEnvPath = Join-Path (Get-Location) ".env"
if (Test-Path $DotEnvPath) {
    Get-Content $DotEnvPath | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#") -or -not $Line.Contains("=")) {
            return
        }
        $Parts = $Line.Split("=", 2)
        $Key = $Parts[0].Trim()
        $Value = $Parts[1].Trim().Trim('"').Trim("'")
        if ($Key) {
            [Environment]::SetEnvironmentVariable($Key, $Value, "Process")
        }
    }
}

$CacheRoot = Join-Path (Get-Location) ".cache"
if (-not $env:XDG_CACHE_HOME) { $env:XDG_CACHE_HOME = $CacheRoot }
if (-not $env:HF_HOME) { $env:HF_HOME = Join-Path $CacheRoot "huggingface" }
if (-not $env:TRANSFORMERS_CACHE) { $env:TRANSFORMERS_CACHE = Join-Path $env:HF_HOME "hub" }
if (-not $env:SENTENCE_TRANSFORMERS_HOME) { $env:SENTENCE_TRANSFORMERS_HOME = Join-Path $CacheRoot "sentence-transformers" }
if (-not $env:TORCH_HOME) { $env:TORCH_HOME = Join-Path $CacheRoot "torch" }
@($env:XDG_CACHE_HOME, $env:HF_HOME, $env:TRANSFORMERS_CACHE, $env:SENTENCE_TRANSFORMERS_HOME, $env:TORCH_HOME) |
    ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

$PythonExe = "D:\anaconda3\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python).Source
}

Write-Host "Using Python:"
& $PythonExe -c "import sys; print(sys.executable)"

Write-Host "Checking required packages:"
& $PythonExe -c "import importlib.util as u; mods=['streamlit','faiss','sentence_transformers','transformers','torch','openai']; [print(f'{m}: {bool(u.find_spec(m))}') for m in mods]"

Write-Host "Runtime switches:"
& $PythonExe -c "import os; keys=['HF_HUB_OFFLINE','GRAPH_PICKLE_PATH','HF_HOME','SENTENCE_TRANSFORMERS_HOME','TORCH_HOME']; [print(k + '=' + str(os.environ.get(k))) for k in keys]"

Write-Host "Starting Streamlit UI at http://localhost:8501"
& $PythonExe -m streamlit run ui/app.py --server.headless true --server.port 8501
