<#

.SYNOPSIS
This is a script for creating SMB shares to be used by docker-volume-netshare plugin.

.DESCRIPTION
Script assumes that both user <UserName> and directory <SharedDirPath> exist.
Script grants <UserName> full rights to all files and subfolders in <SharedDirPath> (however *NOT* to the <SharedDirPath> itself).
Name of the created share is MD5 digest of normalized <SharedDirPath>.
If a share with this name already exists script does not create a new one.

.EXAMPLE
./create-share.ps1 -UserName golem-docker -SharedDirPath C:\Users\golem-workdir

#>

param(
    [Parameter(Mandatory=$true)] [string] $UserName,
    [Parameter(Mandatory=$true)] [string] $SharedDirPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Assert that user exists
Get-LocalUser $UserName | Out-Null

# Assert that directory exists
if (!(Test-Path -Path $SharedDirPath -PathType Container)) {
    Write-Error -Message "$SharedDirPath is not a directory."
}

# Normalize path
$SharedDirPath = (Get-Item -Path $SharedDirPath).FullName.TrimEnd("\").ToLower()

"Setting directory ACL..."

$FileSystemRights = [System.Security.AccessControl.FileSystemRights]"FullControl"
$InheritanceFlags = [System.Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit"
$PropagationFlags = [System.Security.AccessControl.PropagationFlags]"InheritOnly"
$AccessControlType = [System.Security.AccessControl.AccessControlType]::Allow
$AccessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($UserName, $FileSystemRights, $InheritanceFlags, $PropagationFlags, $AccessControlType)

$Acl = Get-Acl $SharedDirPath
$Acl.AddAccessRule($AccessRule)
Set-Acl -Path $SharedDirPath -AclObject $Acl


$PathAsStream = [IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($SharedDirPath))
$SmbShareName = (Get-FileHash -InputStream $PathAsStream -Algorithm MD5).Hash

if (Get-SmbShare | Where-Object -Property Name -EQ $SmbShareName) {
    "Share already exists."
    exit
}

"Sharing directory..."

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
    New-SmbShare -Name $SmbShareName -Path "$SharedDirPath" -FullAccess "$env:COMPUTERNAME\$UserName" >"$StdoutPath" 2>"$StderrPath"
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
