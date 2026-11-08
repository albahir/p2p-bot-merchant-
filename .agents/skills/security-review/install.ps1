# Installs the security-audit skill into ~/.claude/skills/
# Usage: ./install.ps1            copy (default)
#        ./install.ps1 -Link      symlink, so git pull updates the skill

param([switch]$Link)

$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot 'security-audit'
$skillsDir = Join-Path $HOME '.claude/skills'
$target = Join-Path $skillsDir 'security-audit'

if (-not (Test-Path $source)) {
    throw "security-audit/ not found next to this script. Run it from the repo root."
}

if (-not (Test-Path $skillsDir)) {
    New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
}

if (Test-Path $target) {
    Write-Host "Removing existing $target"
    Remove-Item -Recurse -Force $target
}

if ($Link) {
    # Symlink needs Developer Mode or an elevated shell on Windows.
    New-Item -ItemType SymbolicLink -Path $target -Target $source | Out-Null
    Write-Host "Linked $target -> $source"
} else {
    Copy-Item -Recurse $source $target
    Write-Host "Copied skill to $target"
}

Write-Host ""
Write-Host "Installed. Restart Claude Code, then run: /security-audit"
