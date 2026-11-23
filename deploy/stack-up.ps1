# Creates the demo box: one c7i-flex.large in Sydney that runs the API (Docker, image pulled from ECR), and later k3s + Fission.
# Run:  powershell -File deploy\stack-up.ps1      (push the image first: deploy\push-image.ps1)
# Needs: AWS CLI, ssh/scp (Windows 10+), backend\.env. Firewall is open only to your current IP.
# shortcut: one box for everything, no HTTPS. Split the API out and add TLS before real users.
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-stack"
$Type = "c7i-flex.large"   # 4 GB RAM; swap added below as a safety net
$Profile = "upskilling-p2-ec2-ecr-pull"
$Root = Split-Path $PSScriptRoot -Parent
$Pem = Join-Path $env:USERPROFILE ".ssh\$Name.pem"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$myip = (Invoke-RestMethod https://checkip.amazonaws.com).Trim()
Write-Output "Allowing your IP only: $myip"

$vpc = Invoke-Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
$sg = Invoke-Aws ec2 create-security-group --group-name $Name --description "Onboarding Buddy stack" --vpc-id $vpc --query GroupId --output text
# 22 ssh, 8000 API, 31314 Fission router
$ports = 22, 8000, 31314
$perms = $ports | ForEach-Object { "IpProtocol=tcp,FromPort=$_,ToPort=$_,IpRanges=[{CidrIp=$myip/32}]" }
Invoke-Aws ec2 authorize-security-group-ingress --group-id $sg --ip-permissions @perms | Out-Null

New-Item -ItemType Directory -Force (Split-Path $Pem) | Out-Null
Invoke-Aws ec2 create-key-pair --key-name $Name --query KeyMaterial --output text | Out-File -Encoding ascii $Pem
icacls $Pem /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null

# 30 GB disk: k3s and Fission images don't fit in the default 8 GB
$bdm = Join-Path $env:TEMP "bdm.json"
'[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true}}]' | Out-File -Encoding ascii $bdm

$ami = Invoke-Aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text
$id = Invoke-Aws ec2 run-instances --image-id $ami --instance-type $Type --key-name $Name --security-group-ids $sg --iam-instance-profile "Name=$Profile" --block-device-mappings "file://$bdm" --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$Name},{Key=project,Value=upskilling-p2}]" --query "Instances[0].InstanceId" --output text
Remove-Item $bdm
Write-Output "Instance $id launching..."
Invoke-Aws ec2 wait instance-status-ok --instance-ids $id
$ip = Invoke-Aws ec2 describe-instances --instance-ids $id --query "Reservations[0].Instances[0].PublicIpAddress" --output text

$ssh = @("-i", $Pem, "-o", "StrictHostKeyChecking=accept-new", "-o", "LogLevel=ERROR")
scp @ssh (Join-Path $Root "backend\.env") "ec2-user@${ip}:/home/ec2-user/api.env"
scp @ssh (Join-Path $PSScriptRoot "remote-api.sh") "ec2-user@${ip}:/home/ec2-user/remote-api.sh"
ssh @ssh "ec2-user@$ip" "bash remote-api.sh"
if ($LASTEXITCODE -ne 0) { throw "API setup failed" }

# k3s + Fission + the welcome function
scp @ssh (Join-Path $PSScriptRoot "remote-k3s.sh") (Join-Path $PSScriptRoot "remote-fission-fn.sh") (Join-Path $Root "fission\welcome\welcome.py") "ec2-user@${ip}:/home/ec2-user/"
# sed removes Windows line endings if git converted the scripts
ssh @ssh "ec2-user@$ip" "sed -i 's/\r$//' remote-k3s.sh remote-fission-fn.sh && bash remote-k3s.sh && bash remote-fission-fn.sh"
if ($LASTEXITCODE -ne 0) { throw "k3s/Fission setup failed" }
Write-Output "Stack box ready. Instance: $id  API: http://${ip}:8000  Fission: http://${ip}:31314/welcome"
Write-Output "Next: stop it with deploy\demo-down.ps1, start it for demos with deploy\demo-up.ps1 -Hours N (run deploy\orchestrator-setup.ps1 once)."
