<#
.SYNOPSIS
    Builds a standalone Windows executable for Cipherpad using PyInstaller.

.DESCRIPTION
    Wraps `uv run pyinstaller packaging\cipherpad.spec` so the whole team has a
    single, repeatable command to produce a distributable build. Requires
    `uv` (https://docs.astral.sh/uv/) to be installed and available on PATH;
    dependencies (including PyInstaller, a dev dependency) are resolved
    automatically by uv.

.PARAMETER Clean
    Remove any previous build\ and dist\ output before building.

.EXAMPLE
    .\scripts\build_exe.ps1

.EXAMPLE
    .\scripts\build_exe.ps1 -Clean
#>
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if ($Clean) {
        Write-Host "Removing previous build\ and dist\ output..."
        Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
    }

    Write-Host "Building cipherpad.exe with PyInstaller..."
    uv run pyinstaller packaging\cipherpad.spec --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "Build complete: $repoRoot\dist\cipherpad\cipherpad.exe"
    Write-Host "Distribute by zipping the entire 'dist\cipherpad' folder."
}
finally {
    Pop-Location
}
