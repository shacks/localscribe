# Creates a Desktop shortcut that launches LocalScribe windowless via pythonw.
$ErrorActionPreference = "Stop"
$repo = (Get-Location).Path
$pythonw = Join-Path $repo ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "Run setup.ps1 first (.venv missing)" }

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut((Join-Path $desktop "LocalScribe.lnk"))
$sc.TargetPath = $pythonw
$sc.Arguments = "-m src.main"
$sc.WorkingDirectory = $repo
$sc.IconLocation = "$env:SystemRoot\System32\SoundRecorder.exe,0"
$sc.Description = "LocalScribe - local consultation recorder"
$sc.Save()
Write-Host "Desktop shortcut created: LocalScribe"
