# This scripts checks whether Hyper-V feature is:
# a) available
# b) installed

$ErrorActionPreference = "Stop"

$HyperVFeature = Get-WmiObject -query "select * from Win32_OptionalFeature where name = 'Microsoft-Hyper-V'"

if ($HyperVFeature) {
    "Hyper-V available"
    AI_SetMsiProperty HYPER_V_AVAILABLE "True"

    if ($HyperVFeature.InstallState -eq 1) {
        AI_SetMsiProperty HYPER_V_INSTALLED "True"
        "Hyper-V installed"
    }
}
