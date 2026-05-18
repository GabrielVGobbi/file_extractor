"""
Limpar cache e reiniciar o serviço.

Uso:
  .\scripts\clean_and_restart.ps1
"""

Write-Host "🧹 Limpando cache de disco..." -ForegroundColor Yellow
$cacheDir = ".cache/extractions"
if (Test-Path $cacheDir) {
    Remove-Item -Path $cacheDir -Recurse -Force
    Write-Host "✅ Cache de disco removido" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Cache de disco já estava vazio" -ForegroundColor Cyan
}

# Verificar se Redis está rodando e limpar (apenas se ENABLE_CELERY=true)
$enableCelery = $env:ENABLE_CELERY
if ($enableCelery -eq "true") {
    Write-Host "🔄 Limpando Redis (ENABLE_CELERY=true)..." -ForegroundColor Yellow
    try {
        redis-cli FLUSHDB | Out-Null
        Write-Host "✅ Redis limpo" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Redis não encontrado ou não está rodando. Pulando..." -ForegroundColor Yellow
    }
}

Write-Host "🚀 Reiniciando API..." -ForegroundColor Yellow
Write-Host "Abra um novo terminal e execute:" -ForegroundColor Cyan
Write-Host "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
