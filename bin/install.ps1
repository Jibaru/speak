param([switch]$Background)
$ErrorActionPreference = 'Stop'

$PluginRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$SpeakHome = if ($env:SPEAK_HOME) { $env:SPEAK_HOME } else { Join-Path $env:USERPROFILE '.cache\speak' }
$UvVersion = '0.12.22'
$Uv = Join-Path $SpeakHome 'bin\uv.exe'
$Venv = Join-Path $SpeakHome 'venv'
$Stamp = Join-Path $Venv '.speak-stamp'
$Lock = Join-Path $SpeakHome 'install.lock'
$Log = Join-Path $SpeakHome 'install.log'

New-Item -ItemType Directory -Force -Path $SpeakHome | Out-Null
if ((Test-Path $Lock) -and ((Get-Item $Lock).LastWriteTime -lt (Get-Date).AddMinutes(-20))) {
  Remove-Item -Force -Recurse $Lock
}
try { New-Item -ItemType Directory -Path $Lock -ErrorAction Stop | Out-Null } catch {
  Write-Error 'speak: installation already in progress'
  exit 1
}

if ($Background) {
  Add-Type -AssemblyName System.Speech
  (New-Object System.Speech.Synthesis.SpeechSynthesizer).SpeakAsync('Installing the speak voice engine. Voice will be ready in a minute.') | Out-Null
  Start-Transcript -Append -Path $Log | Out-Null
}

try {
  if (-not (Test-Path $Uv)) {
    $Arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
    $Archive = Join-Path $SpeakHome 'uv.zip'
    Invoke-WebRequest -UseBasicParsing "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-$Arch-pc-windows-msvc.zip" -OutFile $Archive
    Expand-Archive -Force $Archive (Join-Path $SpeakHome 'bin')
    Remove-Item $Archive
  }

  $env:UV_PROJECT_ENVIRONMENT = $Venv
  $env:UV_PYTHON_INSTALL_DIR = Join-Path $SpeakHome 'python'
  $env:UV_CACHE_DIR = Join-Path $SpeakHome 'uv-cache'
  $env:UV_HTTP_TIMEOUT = '300'
  $SyncArgs = @('sync', '--project', $PluginRoot, '--frozen', '--no-dev', '--no-editable', '--managed-python', '--python', '3.12', '--reinstall-package', 'speak', '--quiet')
  & $Uv @SyncArgs
  if ($LASTEXITCODE -ne 0) { & $Uv @SyncArgs }
  if ($LASTEXITCODE -ne 0) { throw 'speak: dependency installation failed' }

  $LockSize = (Get-Item (Join-Path $PluginRoot 'uv.lock')).Length
  [IO.File]::WriteAllText($Stamp, "$PluginRoot|$LockSize")

  if ($Background) {
    $env:SPEAK_PLUGIN_ROOT = $PluginRoot
    & (Join-Path $Venv 'Scripts\python.exe') -m speak setup
  }
} finally {
  Remove-Item -Force -Recurse $Lock -ErrorAction SilentlyContinue
  if ($Background) { Stop-Transcript | Out-Null }
}
