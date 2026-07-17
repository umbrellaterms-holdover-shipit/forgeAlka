# Run this inside the root directory containing your pyproject.toml

Write-Host ">>> Installing package dependencies with STT and TTS extras..." -ForegroundColor Cyan
pip install -e .[stt,tts]

# Set up local directory for storing engine model assets
$ModelDir = Join-Path $PSScriptRoot "models"
if (!(Test-Path $ModelDir)) {
    New-Item -ItemType Directory -Path $ModelDir | Out-Null
}

Write-Host "`n>>> Downloading CPU-optimized audio assets to: $ModelDir" -ForegroundColor Cyan

# 1. Faster-Whisper - Pre-downloading direct files for total offline independence
# We use the raw CT2-quantized structure so Whisper doesn't try to look up Hugging Face at runtime.
$WhisperDir = Join-Path $ModelDir "whisper-tiny-en-ct2"
if (!(Test-Path $WhisperDir)) {
    New-Item -ItemType Directory -Path $WhisperDir | Out-Null
    Write-Host "[Whisper] Pre-fetching quantized CPU model files..." -ForegroundColor Yellow
    
    # Base URL for the optimized small footprint English model weights
    $BaseWhispUrl = "https://huggingface.co/Systran/faster-whisper-tiny.en/resolve/main"
    
    $Files = @("model.bin", "config.json", "vocabulary.txt", "tokenizer.json")
    foreach ($File in $Files) {
        Write-Host "  -> Fetching $File..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "$BaseWhispUrl/$File" -OutFile (Join-Path $WhisperDir $File)
    }
} else {
    Write-Host "[Whisper] Quantized model files already present." -ForegroundColor Green
}

# 2. Vosk - Small English Model
$VoskZip = Join-Path $ModelDir "vosk-model-small-en-us-0.15.zip"
$VoskUrl = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
if (!(Test-Path (Join-Path $ModelDir "vosk-model-small-en-us-0.15"))) {
    Write-Host "[Vosk] Downloading lightweight en-us model..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $VoskUrl -OutFile $VoskZip
    Write-Host "[Vosk] Extracting..." -ForegroundColor Yellow
    Expand-Archive -Path $VoskZip -DestinationPath $ModelDir
    Remove-Item $VoskZip
} else {
    Write-Host "[Vosk] Lightweight model already present." -ForegroundColor Green
}

# 3. Kokoro - 8-bit Quantized ONNX & Voices binary
$KokoroOnnx = Join-Path $ModelDir "kokoro-v1.0.int8.onnx"
$KokoroVoices = Join-Path $ModelDir "voices-v1.0.bin"

if (!(Test-Path $KokoroOnnx)) {
    Write-Host "[Kokoro] Downloading int8 quantized ONNX weights..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" -OutFile $KokoroOnnx
}
if (!(Test-Path $KokoroVoices)) {
    Write-Host "[Kokoro] Downloading voices configuration binary..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" -OutFile $KokoroVoices
}
if ((Test-Path $KokoroOnnx) -and (Test-Path $KokoroVoices)) {
    Write-Host "[Kokoro] Models checked and verified." -ForegroundColor Green
}

# 4. Piper TTS - Medium stability voice model and configuration schema
$PiperModel = Join-Path $ModelDir "en_US-lessac-medium.onnx"
$PiperConfig = Join-Path $ModelDir "en_US-lessac-medium.onnx.json"

if (!(Test-Path $PiperModel)) {
    Write-Host "[Piper] Downloading Lessac-medium voice model..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -OutFile $PiperModel
}
if (!(Test-Path $PiperConfig)) {
    Write-Host "[Piper] Downloading Lessac-medium configurations..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -OutFile $PiperConfig
}
if ((Test-Path $PiperModel) -and (Test-Path $PiperConfig)) {
    Write-Host "[Piper] Models checked and verified." -ForegroundColor Green
}

Write-Host "`n>>> Setup complete. Every required engine weight is fully localized inside .\models\" -ForegroundColor Green