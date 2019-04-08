<#

.SYNOPSIS
This is a script for running an arbitrary powershell script with administrator privileges.

.EXAMPLE
.\run-as-admin.ps1 -ScriptPath "C:\Users\golem\my-script.ps1" -ScriptParams "-Param1 `"this is example`""

#>

param(
    [Parameter(Mandatory=$true)] [string] $ScriptPath,
    [Parameter(Mandatory=$false)] [string] $ScriptParams = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Convert path to absolute
$ScriptPath = Convert-Path -Path $ScriptPath

# Creating temporary files for capturing stout & stderr
$StdoutPath = (New-TemporaryFile).FullName
$StderrPath = (New-TemporaryFile).FullName
$TmpScriptPath = "$env:TEMP/tmp-script.ps1"

# Generate code for a script that will capture the original script's stdout & stderr
# This is done because powershell cannot redirect output of a process started with 'RunAs' verb
@"
`$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

try {
    &"$ScriptPath" $ScriptParams >"$StdoutPath" 2>"$StderrPath"
} catch {
    `$_ | Out-File -FilePath "$StderrPath" -Encoding "UTF8"
    throw
}
"@ | Out-File -Encoding "UTF8" -FilePath $TmpScriptPath

$Process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -NoLogo -ExecutionPolicy RemoteSigned `"$TmpScriptPath`"" `
    -Wait -PassThru -Verb RunAs -WindowStyle Hidden

Get-Content -Encoding "UTF8" -Path $StdoutPath | Write-Output
Get-Content -Encoding "UTF8" -Path $StderrPath | Write-Error

exit $Process.ExitCode
