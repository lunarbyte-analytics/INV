# Jednorazowo po sklonowaniu repozytorium: wymuszenie hookow z katalogu .githooks
Set-Location $PSScriptRoot
git config core.hooksPath .githooks
Write-Host "OK: core.hooksPath = .githooks (commit wymaga niepustego Message)"
