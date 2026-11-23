# Deploys backend/ to one small EC2 instance in Sydney and runs it in Docker.
# Run from anywhere:  powershell -File deploy\deploy-ec2.ps1
# Needs: AWS CLI with working credentials, ssh/scp/tar (built into Windows 10+), backend\.env with GROQ_API_KEY.
# shortcut: one instance, firewall open only to your current IP, no HTTPS or login. Add them before sharing it with others.
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-onboarding-buddy"
$Type = "t3.small"   # 2 GB RAM: the Docker build is too heavy for a micro instance
$Backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"
$Pem = Join-Path $env:USERPROFILE ".ssh\$Name.pem"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$myip = (Invoke-RestMethod https://checkip.amazonaws.com).Trim()
Write-Output "Allowing your IP only: $myip"

$vpc = Invoke-Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
$sg = Invoke-Aws ec2 create-security-group --group-name $Name --description "Onboarding Buddy demo" --vpc-id $vpc --query GroupId --output text
Invoke-Aws ec2 authorize-security-group-ingress --group-id $sg --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$myip/32}]" "IpProtocol=tcp,FromPort=8000,ToPort=8000,IpRanges=[{CidrIp=$myip/32}]" | Out-Null

if (-not (Test-Path $Pem)) {
  New-Item -ItemType Directory -Force (Split-Path $Pem) | Out-Null
  Invoke-Aws ec2 create-key-pair --key-name $Name --query KeyMaterial --output text | Out-File -Encoding ascii $Pem
  icacls $Pem /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null
}

$ami = Invoke-Aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text
$id = Invoke-Aws ec2 run-instances --image-id $ami --instance-type $Type --key-name $Name --security-group-ids $sg --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$Name},{Key=project,Value=upskilling-p2}]" --query "Instances[0].InstanceId" --output text
Write-Output "Instance $id launching..."
Invoke-Aws ec2 wait instance-status-ok --instance-ids $id
$ip = Invoke-Aws ec2 describe-instances --instance-ids $id --query "Reservations[0].Instances[0].PublicIpAddress" --output text

$tgz = Join-Path $env:TEMP "buddy.tgz"
tar -czf $tgz -C $Backend --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.env --exclude=tests .
$sshopts = @("-i", $Pem, "-o", "StrictHostKeyChecking=accept-new", "-o", "LogLevel=ERROR")
scp @sshopts $tgz "ec2-user@${ip}:/home/ec2-user/buddy.tgz"
scp @sshopts (Join-Path $Backend ".env") "ec2-user@${ip}:/home/ec2-user/buddy.env"
Remove-Item $tgz

$remote = "set -e; sudo dnf install -y -q docker; sudo systemctl enable --now docker; rm -rf app; mkdir app; tar -xzf buddy.tgz -C app; mv buddy.env app/.env; chmod 600 app/.env; cd app; sudo docker build -q -t buddy .; sudo docker rm -f buddy 2>/dev/null || true; sudo docker run -d --restart unless-stopped --name buddy -p 8000:8000 -v /home/ec2-user/app/.env:/app/.env:ro buddy"
ssh @sshopts "ec2-user@$ip" $remote
if ($LASTEXITCODE -ne 0) { throw "remote setup failed" }

Write-Output "Deployed. Instance: $id  URL: http://${ip}:8000  (docs at /docs)"
