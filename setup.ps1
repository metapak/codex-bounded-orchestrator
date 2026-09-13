[CmdletBinding()]
param(
    [string]$Target,
    [ValidateSet("astra", "sol")]
    [string]$Profile,
    [ValidateSet("balanced", "quality", "economy", "custom")]
    [string]$Preset,
    [string[]]$RoleModel = @(),
    [string[]]$RoleEffort = @(),
    [ValidateSet("none", "anthropic", "deepseek")]
    [string]$ExternalProvider,
    [string]$ExternalModel,
    [ValidateSet("none", "minimal", "low", "medium", "high", "xhigh", "max")]
    [string]$ExternalEffort,
    [switch]$Force,
    [switch]$ForceConfig,
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================"
Write-Host " Codex Bounded Orchestrator 0.5.0"
Write-Host " Guided setup / Windows"
Write-Host "============================================================"
Write-Host " Native roles: OpenAI GPT models only"
Write-Host " External APIs: optional, proposal-only, default is none"

if ([string]::IsNullOrWhiteSpace($Target)) {
    if ($NonInteractive) { throw "-Target is required with -NonInteractive." }
    Write-Host "`n[ TARGET / HEDEF ]"
    $Target = Read-Host "Paste the target repository folder path"
}
$Target = $Target.Trim().Trim('"').Trim("'")

if (-not $NonInteractive -and -not $Uninstall -and -not $DryRun) {
    Write-Host "`n[ ACTION / ISLEM ]"
    Write-Host "  1) Safe install/update  - back up only when replacement is chosen"
    Write-Host "  2) Dry run only        - preview; write nothing"
    Write-Host "  3) Uninstall           - remove unchanged managed files"
    $Action = Read-Host "Select [1]"
    if ([string]::IsNullOrWhiteSpace($Action)) { $Action = "1" }
    switch ($Action) {
        "2" { $DryRun = $true }
        "3" { $Uninstall = $true }
        "1" { }
        default { throw "Invalid action: $Action" }
    }
}

if (-not $NonInteractive -and -not $Uninstall -and -not $DryRun) {
    Write-Host "`n[ CONFLICTS / CAKISMALAR ]"
    Write-Host "Default keeps files that differ. Choose yes only to back up and replace them."
    $Choice = Read-Host "Replace conflicting managed role/skill/tool files? [y/N]"
    if ($Choice -match '^(y|yes)$') { $Force = $true }
    $Choice = Read-Host "Replace an existing .codex\config.toml after backup? [y/N]"
    if ($Choice -match '^(y|yes)$') { $ForceConfig = $true }
}

$Invoke = @{ Target = $Target }
if ($Profile) { $Invoke.Profile = $Profile }
if ($Preset) { $Invoke.Preset = $Preset }
if ($RoleModel.Count -gt 0) { $Invoke.RoleModel = $RoleModel }
if ($RoleEffort.Count -gt 0) { $Invoke.RoleEffort = $RoleEffort }
if ($ExternalProvider) { $Invoke.ExternalProvider = $ExternalProvider }
if (-not [string]::IsNullOrWhiteSpace($ExternalModel)) { $Invoke.ExternalModel = $ExternalModel }
if (-not [string]::IsNullOrWhiteSpace($ExternalEffort)) { $Invoke.ExternalEffort = $ExternalEffort }
if (-not $NonInteractive -and -not $Uninstall) { $Invoke.Interactive = $true }
if ($Force) { $Invoke.Force = $true }
if ($ForceConfig) { $Invoke.ForceConfig = $true }
if ($DryRun) { $Invoke.DryRun = $true }
if ($Uninstall) { $Invoke.Uninstall = $true }

& "$ScriptDir\scripts\install.ps1" @Invoke
$Code = $LASTEXITCODE
if ($null -eq $Code) { $Code = 0 }
if (-not $NonInteractive) { Write-Host "`nInstaller exited with status $Code." }
exit $Code
