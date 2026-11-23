# Pushes the current backend/ code and backend\.env to the EXISTING instance and restarts the container.
# Does not touch the firewall or any other AWS setting.
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-onboarding-buddy"
$Backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"
$Pem = Join-Path $env:USERPROFILE ".ssh\$Name.pem"
function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$ip = Invoke-Aws ec2 describe-instances --filters "Name=tag:Name,Values=$Name" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].PublicIpAddress" --output text
if (-not $ip -or $ip -eq "None") { throw "No running instance named $Name. Run deploy-ec2.ps1 first." }

$tgz = Join-Path $env:TEMP "buddy.tgz"
tar -czf $tgz -C $Backend --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.env --exclude=tests .
$sshopts = @("-i", $Pem, "-o", "StrictHostKeyChecking=accept-new", "-o", "LogLevel=ERROR")
scp @sshopts $tgz "ec2-user@${ip}:/home/ec2-user/buddy.tgz"
scp @sshopts (Join-Path $Backend ".env") "ec2-user@${ip}:/home/ec2-user/buddy.env"
Remove-Item $tgz

$remote = "set -e; rm -rf app; mkdir app; tar -xzf buddy.tgz -C app; mv buddy.env app/.env; chmod 600 app/.env; cd app; sudo docker build -q -t buddy .; sudo docker rm -f buddy 2>/dev/null || true; sudo docker run -d --restart unless-stopped --name buddy -p 8000:8000 -v /home/ec2-user/app/.env:/app/.env:ro buddy"
ssh @sshopts "ec2-user@$ip" $remote
if ($LASTEXITCODE -ne 0) { throw "remote update failed" }
Write-Output "Updated. URL: http://${ip}:8000"
