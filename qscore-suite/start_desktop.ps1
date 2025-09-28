Set-ExecutionPolicy -Scope Process Bypass
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
.\.venv\Scripts\Activate.ps1
python .\desktop\app_launcher.py
