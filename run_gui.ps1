$script = Join-Path $PSScriptRoot 'main.py'
# Prefer pythonw to avoid console window; fallback to python
if (Get-Command pythonw -ErrorAction SilentlyContinue) {
    Start-Process -FilePath pythonw -ArgumentList "`"$script`""
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Start-Process -FilePath python -ArgumentList "`"$script`""
} else {
    Write-Host "No se encontró pythonw ni python en PATH. Instale Python o ejecute main.py manualmente."
}
