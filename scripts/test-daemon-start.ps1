"Ensure hyperg is started"

$HyperdriveProcess = Get-Process hyperg -ErrorAction SilentlyContinue

if ($HyperdriveProcess) {
  Stop-Process -Id $HyperdriveProcess
}

"Starting..."
$HyperdriveProcess = Start-Process C:\BuildResources\hyperg\hyperg.exe -WorkingDirectory C:\Users\buildbot-worker -PassThru

$HyperdriveProcess

$HyperdriveProcess.Id | Out-File .test-daemon-hyperg.pid
