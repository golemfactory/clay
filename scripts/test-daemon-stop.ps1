
$filePath = ".test-daemon-hyperg.pid"
$HyperdriveProcess = Get-Content $filePath -Raw

# Get-Process

Stop-Process -Id $HyperdriveProcess

