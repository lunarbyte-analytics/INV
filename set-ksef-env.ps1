<#
.SYNOPSIS
    Ustawia zmienne srodowiskowe KSeF dla aplikacji INV (biezaca sesja PowerShell).

.DESCRIPTION
    Wymagane: KSEF_TOKEN, KSEF_NIP. Opcjonalnie: KSEF_TEST_BASE_URL.

    Uruchom przed startem aplikacji w tym samym oknie terminala:
      .\set-ksef-env.ps1

    Z parametrami (token trafia do historii polecen):
      .\set-ksef-env.ps1 -Nip "1234567890" -Token "..."

    Trwale (-Persistent) zapis w profilu uzytkownika Windows.

.NOTES
    Nie commituj tokenow. Plik .env.ksef (KEY=value) - dodaj do .gitignore.

    ExecutionPolicy:
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

[CmdletBinding()]
param(
    [string] $Token,
    [string] $Nip,
    [string] $BaseUrl = "",
    [switch] $Persistent
)

$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot ".env.ksef"
if (Test-Path -LiteralPath $envFile) {
    $kv = @{}
    Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { return }
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim()
        $kv[$k] = $v
    }
    if ($Token -eq "" -and $kv.ContainsKey("KSEF_TOKEN")) { $Token = $kv["KSEF_TOKEN"] }
    if ($Nip -eq "" -and $kv.ContainsKey("KSEF_NIP")) { $Nip = $kv["KSEF_NIP"] }
    if ($BaseUrl -eq "" -and $kv.ContainsKey("KSEF_TEST_BASE_URL")) { $BaseUrl = $kv["KSEF_TEST_BASE_URL"] }
}

if ($Nip -eq "") {
    $Nip = Read-Host "KSEF_NIP (10 cyfr NIP kontekstu)"
}
$Nip = ($Nip -replace "\D", "")
if ($Nip.Length -ne 10) {
    Write-Error "KSEF_NIP musi miec dokladnie 10 cyfr."
}

if ($Token -eq "") {
    $sec = Read-Host "KSEF_TOKEN (wklej token - znaki beda ukryte)" -AsSecureString
    $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try {
        $Token = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

$Token = $Token.Trim()
if ($Token -eq "") {
    Write-Error "KSEF_TOKEN nie moze byc pusty."
}

$env:KSEF_TOKEN = $Token
$env:KSEF_NIP = $Nip

if ($BaseUrl -ne "") {
    $env:KSEF_TEST_BASE_URL = $BaseUrl.Trim().TrimEnd("/")
} else {
    Remove-Item Env:\KSEF_TEST_BASE_URL -ErrorAction SilentlyContinue
}

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
}

if ($Persistent) {
    Set-UserEnv "KSEF_TOKEN" $Token
    Set-UserEnv "KSEF_NIP" $Nip
    if ($BaseUrl -ne "") {
        Set-UserEnv "KSEF_TEST_BASE_URL" $env:KSEF_TEST_BASE_URL
    } else {
        [Environment]::SetEnvironmentVariable("KSEF_TEST_BASE_URL", $null, "User")
    }
    Write-Host "Zapisano trwale w profilu uzytkownika (User). Nowy terminal = widoczne zmienne."
}

Write-Host ""
Write-Host "Ustawiono (ta sesja PowerShell):"
Write-Host "  KSEF_NIP               = $env:KSEF_NIP"
$len = $env:KSEF_TOKEN.Length
Write-Host "  KSEF_TOKEN             = **** (dlugosc: $len znakow)"
if ($env:KSEF_TEST_BASE_URL) {
    Write-Host "  KSEF_TEST_BASE_URL     = $($env:KSEF_TEST_BASE_URL)"
} else {
    Write-Host "  KSEF_TEST_BASE_URL     = (brak - domyslny adres testowy w aplikacji)"
}
Write-Host ""
Write-Host "Uruchom aplikacje z tego samego okna, np.: py -3 main.py"
Write-Host ""
