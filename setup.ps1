
[CmdletBinding()]
param(
    [string]$Target,
    [ValidateSet("astra", "sol")]
    [string]$Profile = "astra",
    [switch]$Force,
    [switch]$ForceConfig,
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================"
Write-Host " Codex Bounded Orchestrator 0.2.0 - Windows installer"
Write-Host " Astra owns | Terra maps/verifies | Sol builds/diagnoses"
Write-Host "============================================================"

if ([string]::IsNullOrWhiteSpace($Target)) {
    if ($NonInteractive) {
        throw "-Target is required with -NonInteractive."
    }
    $Target = Read-Host "`nPaste the target repository folder path"
}
$Target = $Target.Trim().Trim('"').Trim("'")

if (-not $NonInteractive -and -not $Uninstall -and -not $DryRun) {
    Write-Host "`nAction:"
    Write-Host "  1) Safe install/update"
    Write-Host "  2) Dry run only"
    Write-Host "  3) Uninstall managed files"
    $Action = Read-Host "Select [1]"
    if ([string]::IsNullOrWhiteSpace($Action)) { $Action = "1" }
    switch ($Action) {
        "2" { $DryRun = $true }
        "3" { $Uninstall = $true }
        "1" { }
        default { throw "Invalid action: $Action" }
    }
}

if (-not $NonInteractive -and -not $Uninstall) {
    Write-Host "`nOwner profile:"
    Write-Host "  1) Astra medium (recommended)"
    Write-Host "  2) Sol high fallback"
    $Choice = Read-Host "Select [1]"
    if ($Choice -eq "2") { $Profile = "sol" } else { $Profile = "astra" }
}

if (-not $NonInteractive -and -not $Uninstall -and -not $DryRun) {
    $Choice = Read-Host "`nReplace conflicting managed role/skill/tool files after backup? [y/N]"
    if ($Choice -match '^(y|yes)$') { $Force = $true }

    $Choice = Read-Host "Replace an existing .codex\config.toml after backup? [y/N]"
    if ($Choice -match '^(y|yes)$') { $ForceConfig = $true }
}

$Invoke = @{
    Target = $Target
    Profile = $Profile
}
if ($Force) { $Invoke.Force = $true }
if ($ForceConfig) { $Invoke.ForceConfig = $true }
if ($DryRun) { $Invoke.DryRun = $true }
if ($Uninstall) { $Invoke.Uninstall = $true }

& "$ScriptDir\scripts\install.ps1" @Invoke
$Code = $LASTEXITCODE
if ($null -eq $Code) { $Code = 0 }

if (-not $NonInteractive) {
    Write-Host "`nInstaller exited with status $Code."
}
exit $Code
