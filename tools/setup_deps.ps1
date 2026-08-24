$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)

$LLAMA_TAG = "b10603"
$LLAMA_BIN = "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-win-cuda-12.4-x64.zip"
$CUDART_BIN = "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/cudart-llama-bin-win-cuda-12.4-x64.zip"
$MODEL_URL = "https://huggingface.co/tencent/HY-MT1.5-7B-GGUF/resolve/main/HY-MT1.5-7B-Q4_K_M.gguf"

New-Item -ItemType Directory -Force -Path "downloads", "vendor\llamacpp", "models" | Out-Null

function Fetch($url, $out) {
    $name = Split-Path $out -Leaf
    Write-Host "Downloading $name ..."
    & curl.exe -sSL --retry 10 --retry-delay 3 -C - -o $out $url
    if ($LASTEXITCODE -ne 0) { throw "download failed: $url" }
}

if (-not (Test-Path "vendor\llamacpp\llama-server.exe")) {
    Fetch $LLAMA_BIN "downloads\llamacpp-cuda.zip"
    Fetch $CUDART_BIN "downloads\cudart.zip"
    Write-Host "Extracting llama.cpp binaries..."
    Expand-Archive -Path "downloads\llamacpp-cuda.zip" -DestinationPath "vendor\llamacpp" -Force
    Expand-Archive -Path "downloads\cudart.zip" -DestinationPath "vendor\llamacpp" -Force
} else {
    Write-Host "llama.cpp binaries already present, skipping."
}

$model = "models\HY-MT1.5-7B-Q4_K_M.gguf"
if (-not (Test-Path $model)) {
    Write-Host "Downloading translation model (~4.4 GB, resumable)..."
    Fetch $MODEL_URL $model
} else {
    Write-Host "Model already present, skipping."
}

Write-Host ""
Write-Host "Setup complete:"
Get-ChildItem "vendor\llamacpp\llama-server.exe", $model | Select-Object FullName, @{N='MB';E={[math]::Round($_.Length/1MB)}}
