param(
  [string]$Name = "AI_Modding_Suite",
  [string]$Entry = "app.py"
)

$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Hidden imports for dynamic plugin loading
$hidden = @(
  "plugins.preset_ksp"
) -join ","

pyinstaller --noconfirm --clean --windowed `
  --name $Name `
  --hidden-import $hidden `
  $Entry

Write-Host "Build complete. Check .\dist\$Name\$Name.exe"
