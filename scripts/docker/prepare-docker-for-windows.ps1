# Block for declaring the script parameters.
Param(
    $createShareFolder = "",
    $appDataDir = "",
    $currentUserName = ""
)
if (Get-Command "AI_GetMsiProperty" -errorAction SilentlyContinue)
{
    $createShareFolder = (AI_GetMsiProperty TempFolder)
    $appDataDir = (AI_GetMsiProperty LocalAppDataFolder)
    $currentUserName = (AI_GetMsiProperty LogonUser)
}

$ErrorActionPreference = "Stop"

# Your code goes here.
$golemUserName = "golem-docker"
"golemUserName: " + $golemUserName

$currentGolemUser = Get-LocalUser | ?{$_.Name -eq $golemUserName}
"currentGolemUser: " + $currentGolemUser
if( ! $currentGolemUser )
{
    "Creating local user"
    $securePassword = ConvertTo-SecureString $golemUserName -AsPlainText -Force
    New-LocalUser -Name $golemUserName -Password $securePassword -Description "Account to use docker with golem." -AccountNeverExpires -PasswordNeverExpires
    "Local user created"
}
# TODO: set execution policy here?

"createShareFolder: " + $createShareFolder
"appDataDir: " + $appDataDir

$createShareScript = $createShareFolder + "create-share.ps1"
"createShareScript: " + $createShareScript

$golemDataDir = $appDataDir + "\golem\golem\default"
$mainnetDir = $golemDataDir + "\mainnet\ComputerRes"
"mainnetDir: " + $mainnetDir
$testnetDir = $golemDataDir + "\rinkeby\ComputerRes"
"testnetDir: " + $testnetDir

function EnsureShare {
    Param([string]$folder)
    "Ensure Shared folder"
    md $folder -Force
    "Folder created, create share"
    &"$createShareScript" "$golemUserName" "$folder"
    "Share created"
}

EnsureShare $mainnetDir
EnsureShare $testnetDir

"Add current user to the Hyper-V Administrators group"
# Create "Hyper-V Administrators" group

$HvAdminGroupSID = "S-1-5-32-578"
$HvAdminGroup =(gwmi Win32_Group | ?{$_.sid -eq $HvAdminGroupSID})
"Found group?"
"Admin group: " + $HvAdminGroup
if( $HvAdminGroup )
{
    "currentUserName:" + $currentUserName
    $fullUserName = "$env:computername\$currentUserName"
    $isMember = (Get-LocalGroupMember -sid $HvAdminGroup.sid  | ?{$_.name -eq $fullUserName})
    "Is the current user member?"
    "isMember: " + $isMember
    if ( ! $isMember )
    {
        "Add current user to Hyper-V Administrators group"
        Add-LocalGroupMember -sid $HvAdminGroup.sid -member $fullUserName

        $isMember = (Get-LocalGroupMember -sid $HvAdminGroup.sid  | ?{$_.name -eq $fullUserName})
        "Is the current user member?"
      "isMember: " + $isMember
        if ( ! $isMember )
        {
                "Installer failed to add current user to hyperv group"
                exit 1
        }
    }
}

"Check Golem SMB firewall rule"
$firewallRule = Get-NetFirewallRule | ?{$_.name -eq "GOLEM-SMB"}
"Current rule: " + $firewallRule
if( ! $firewallRule )
{
    New-NetFirewallRule -DisplayName "Golem SMB" -Name "GOLEM-SMB" `
     -Direction Inbound -LocalPort 445 -Protocol TCP `
     -RemoteAddress 172.16.0.0/12 -LocalAddress 172.16.0.0/12 `
     -Program System -Action Allow

    $firewallRule = Get-NetFirewallRule | ?{$_.name -eq "GOLEM-SMB"}
    "Created rule: " + $firewallRule
    if( ! $firewallRule )
    {
        "Failed to create firewall rule."
        exit 1
    }
}

exit 0
