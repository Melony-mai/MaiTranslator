$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)

Write-Host "[0/4] Generating icons..."
& .venv\Scripts\python.exe tools\gen_icons.py
if ($LASTEXITCODE -ne 0) { throw "icon generation failed with exit code $LASTEXITCODE" }

Write-Host "[1/4] Cleaning previous build..."
if (Test-Path "build\pyinstaller") { Remove-Item -Recurse -Force "build\pyinstaller" }
if (Test-Path "dist\MaiTranslator") { Remove-Item -Recurse -Force "dist\MaiTranslator" }

Write-Host "[2/4] Running PyInstaller..."
& .venv\Scripts\pyinstaller.exe MaiTranslator.spec --distpath dist --workpath build\pyinstaller --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

Write-Host "[3/4] Copying runtime assets (llama.cpp binaries + model)..."
New-Item -ItemType Directory -Force -Path "dist\MaiTranslator\vendor\llamacpp","dist\MaiTranslator\models" | Out-Null
Copy-Item -Path "vendor\llamacpp\*" -Destination "dist\MaiTranslator\vendor\llamacpp" -Recurse -Force
$modelSrc = "models\HY-MT1.5-7B-Q4_K_M.gguf"
if (-not (Test-Path $modelSrc)) { throw "model not found: $modelSrc" }
Copy-Item -LiteralPath $modelSrc -Destination "dist\MaiTranslator\models\" -Force

Write-Host "[4/4] Creating portable zip..."
$zip = Join-Path (Resolve-Path "dist").Path "MaiTranslator-1.0.0-win64-portable.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
tar.exe -a -c -f $zip -C dist MaiTranslator
if ($LASTEXITCODE -ne 0) { throw "zip failed" }

Get-ChildItem "dist\MaiTranslator\MaiTranslator.exe", $zip | Select-Object FullName, @{N='MB';E={[math]::Round($_.Length/1MB)}}
Write-Host "BUILD OK"
