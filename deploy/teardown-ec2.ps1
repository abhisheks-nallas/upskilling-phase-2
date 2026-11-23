# Removes everything deploy-ec2.ps1 created (instance, security group, key pair, local .pem).
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Name = "upskilling-p2-onboarding-buddy"
$Pem = Join-Path $env:USERPROFILE ".ssh\$Name.pem"
function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$ids = Invoke-Aws ec2 describe-instances --filters "Name=tag:Name,Values=$Name" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query "Reservations[].Instances[].InstanceId" --output text
if ($ids) {
  Invoke-Aws ec2 terminate-instances --instance-ids ($ids -split "\s+") | Out-Null
  Invoke-Aws ec2 wait instance-terminated --instance-ids ($ids -split "\s+")
}
$sg = Invoke-Aws ec2 describe-security-groups --filters "Name=group-name,Values=$Name" --query "SecurityGroups[0].GroupId" --output text
if ($sg -and $sg -ne "None") { Invoke-Aws ec2 delete-security-group --group-id $sg }
Invoke-Aws ec2 delete-key-pair --key-name $Name
if (Test-Path $Pem) { Remove-Item $Pem }
Write-Output "Torn down."
