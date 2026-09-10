
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Target,

    [ValidateSet("astra", "sol")]
    [string]$Profile = "astra",

    [switch]$Force,
    [switch]$ForceConfig,
    [switch]$DryRun,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Arguments = @("$ScriptDir\install.py", $Target, "--profile", $Profile)
if ($Force) { $Arguments += "--force" }
if ($ForceConfig) { $Arguments += "--force-config" }
if ($DryRun) { $Arguments += "--dry-run" }
if ($Uninstall) { $Arguments += "--uninstall" }

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @Arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @Arguments
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    & python3 @Arguments
} else {
    Write-Error "Python 3.11 or newer was not found on PATH."
    exit 2
}
exit $LASTEXITCODE
