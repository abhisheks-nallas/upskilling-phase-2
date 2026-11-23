# Starts the demo box, opens its firewall to your current IP, and arms an automatic stop after -Hours.
# Run:  powershell -File deploy\demo-up.ps1 -Hours 3
# Needs: deploy\stack-up.ps1 and deploy\orchestrator-setup.ps1 already run once.
param([int]$Hours = 3)
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-stack"
$Machine = "upskilling-p2-demo-session"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }
$began = Get-Date

$q = "Reservations[].Instances[?State.Name!='terminated'].InstanceId | [0] | [0]"
$id = Invoke-Aws ec2 describe-instances --filters "Name=tag:Name,Values=$Name" --query $q --output text
if (-not $id -or $id -eq "None") { throw "No box named $Name. Run deploy\stack-up.ps1 first." }

# Your IP changes (home, VPN, office), so point the firewall at where you are now. Only this box's own group is touched.
$myip = (Invoke-RestMethod https://checkip.amazonaws.com).Trim()
$sg = Invoke-Aws ec2 describe-security-groups --filters "Name=group-name,Values=$Name" --query "SecurityGroups[0].GroupId" --output text
$old = Invoke-Aws ec2 describe-security-groups --group-ids $sg --query "SecurityGroups[0].IpPermissions" --output json
if ($old -and $old.Trim() -ne "[]") {
  $f = Join-Path $env:TEMP "old-perms.json"
  [IO.File]::WriteAllText($f, $old, (New-Object Text.UTF8Encoding $false))
  Invoke-Aws ec2 revoke-security-group-ingress --group-id $sg --ip-permissions "file://$f" | Out-Null
  Remove-Item $f
}
$perms = 22, 8000, 31314 | ForEach-Object { "IpProtocol=tcp,FromPort=$_,ToPort=$_,IpRanges=[{CidrIp=$myip/32}]" }
Invoke-Aws ec2 authorize-security-group-ingress --group-id $sg --ip-permissions @perms | Out-Null
Write-Output "Firewall open to $myip only"

$arn = Invoke-Aws stepfunctions list-state-machines --query "stateMachines[?name=='$Machine'].stateMachineArn | [0]" --output text
if (-not $arn -or $arn -eq "None") { throw "State machine missing. Run deploy\orchestrator-setup.ps1 first." }
$inFile = Join-Path $env:TEMP "demo-input.json"
[IO.File]::WriteAllText($inFile, (@{ instanceId = $id; seconds = $Hours * 3600 } | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding $false))
$exec = Invoke-Aws stepfunctions start-execution --state-machine-arn $arn --name ("demo-" + (Get-Date -Format "yyyyMMdd-HHmmss")) --input "file://$inFile" --query executionArn --output text
Remove-Item $inFile
Write-Output "Starting $id. It will stop by itself in $Hours h."

Invoke-Aws ec2 wait instance-running --instance-ids $id
$ip = Invoke-Aws ec2 describe-instances --instance-ids $id --query "Reservations[0].Instances[0].PublicIpAddress" --output text
Write-Output "Box is running at $ip, waiting for the API and Fission to come up..."

function Wait-Url([string]$url, [string]$label) {
  for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $url).StatusCode -eq 200) { Write-Output "  $label up"; return } } catch { }
    Start-Sleep 5
  }
  Write-Warning "$label did not answer within 5 minutes: $url"
}
Wait-Url "http://${ip}:8000/health-check" "API"
Wait-Url "http://${ip}:31314/router-healthz" "Fission router"

$secs = [int]((Get-Date) - $began).TotalSeconds
$stopAt = (Get-Date).AddHours($Hours).ToString("HH:mm")
Write-Output ""
Write-Output "Ready in $secs s.  API: http://${ip}:8000/docs   Fission: http://${ip}:31314/welcome"
Write-Output "Auto-stop at about $stopAt local time. Stop earlier with deploy\demo-down.ps1."
