# Stops the demo box now and cancels the pending auto-stop.
# Run:  powershell -File deploy\demo-down.ps1
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-stack"
$Machine = "upskilling-p2-demo-session"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$arn = Invoke-Aws stepfunctions list-state-machines --query "stateMachines[?name=='$Machine'].stateMachineArn | [0]" --output text
if ($arn -and $arn -ne "None") {
  $running = Invoke-Aws stepfunctions list-executions --state-machine-arn $arn --status-filter RUNNING --query "executions[].executionArn" --output text
  foreach ($e in ($running -split "\s+" | Where-Object { $_ })) {
    Invoke-Aws stepfunctions stop-execution --execution-arn $e | Out-Null
    Write-Output "Cancelled pending auto-stop $e"
  }
}
$q = "Reservations[].Instances[?State.Name!='terminated'].InstanceId | [0] | [0]"
$id = Invoke-Aws ec2 describe-instances --filters "Name=tag:Name,Values=$Name" --query $q --output text
if (-not $id -or $id -eq "None") { throw "No box named $Name." }
$state = Invoke-Aws ec2 describe-instances --instance-ids $id --query "Reservations[0].Instances[0].State.Name" --output text
if ($state -eq "stopped") { Write-Output "$id is already stopped."; return }
# The stop goes through the state machine too: a run with a 1 second hold ends in its StopBox step
$inFile = Join-Path $env:TEMP "demo-stop-input.json"
[IO.File]::WriteAllText($inFile, (@{ instanceId = $id; seconds = 1 } | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding $false))
Invoke-Aws stepfunctions start-execution --state-machine-arn $arn --name ("stop-" + (Get-Date -Format "yyyyMMdd-HHmmss")) --input "file://$inFile" | Out-Null
Remove-Item $inFile
Write-Output "Stopping through the state machine..."
Invoke-Aws ec2 wait instance-stopped --instance-ids $id
Write-Output "Stopped $id. Compute billing has stopped (the 30 GB disk is a few cents a day)."
