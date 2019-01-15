"Ensure hyperg is started"

New-Variable -Name workDir -Value C:\BuildResources\hyperg

$HyperdriveProcess = Get-Process hyperg -ErrorAction SilentlyContinue

if ($HyperdriveProcess) {
  Stop-Process -Id $HyperdriveProcess.Id
}

"Starting..."

$env:Path += ";$workDir"
$env:SEE_MASK_NOZONECHECKS = 1

$HyperdriveProcess = Start-Process $workDir\hyperg.exe -WorkingDirectory $workDir -PassThru

$HyperdriveProcess

$HyperdriveProcess.Id | Out-File .test-daemon-hyperg.pid
