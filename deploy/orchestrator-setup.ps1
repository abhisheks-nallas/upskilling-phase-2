# One-time (safe to re-run): creates the IAM role and the Step Functions state machine behind demo-up / demo-down.
# Run:  powershell -File deploy\orchestrator-setup.ps1
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Role = "upskilling-p2-demo-session"
$Machine = "upskilling-p2-demo-session"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }
function Write-Json([string]$path, [string]$json) { [IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding $false)) }

$account = Invoke-Aws sts get-caller-identity --query Account --output text
$trust = Join-Path $env:TEMP "sfn-trust.json"
Write-Json $trust '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"states.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
# Start/stop only instances tagged project=upskilling-p2. Describe can't be limited by tag.
$policy = Join-Path $env:TEMP "sfn-policy.json"
Write-Json $policy ('{"Version":"2012-10-17","Statement":[' +
  '{"Effect":"Allow","Action":["ec2:StartInstances","ec2:StopInstances"],"Resource":"arn:aws:ec2:' + $Region + ':' + $account + ':instance/*","Condition":{"StringEquals":{"aws:ResourceTag/project":"upskilling-p2"}}},' +
  '{"Effect":"Allow","Action":"ec2:DescribeInstances","Resource":"*"}]}')

$ErrorActionPreference = "Continue"  # "role not found" is expected on the first run, and PowerShell 5.1 treats stderr as an error
& aws iam get-role --role-name $Role *> $null
$roleMissing = $LASTEXITCODE -ne 0
$ErrorActionPreference = "Stop"
if ($roleMissing) {
  Invoke-Aws iam create-role --role-name $Role --assume-role-policy-document "file://$trust" --tags "Key=project,Value=upskilling-p2" | Out-Null
  Write-Output "Created role $Role"
}
Invoke-Aws iam put-role-policy --role-name $Role --policy-name start-stop-demo-box --policy-document "file://$policy"
$roleArn = Invoke-Aws iam get-role --role-name $Role --query Role.Arn --output text
if ($roleMissing) { Start-Sleep 12 }  # new roles take a few seconds to be usable

$arn = Invoke-Aws stepfunctions list-state-machines --query "stateMachines[?name=='$Machine'].stateMachineArn | [0]" --output text
$def = "file://" + (Join-Path $PSScriptRoot "demo-session.asl.json")
if ($arn -and $arn -ne "None") {
  Invoke-Aws stepfunctions update-state-machine --state-machine-arn $arn --definition $def --role-arn $roleArn | Out-Null
  Write-Output "Updated state machine $arn"
} else {
  $arn = Invoke-Aws stepfunctions create-state-machine --name $Machine --definition $def --role-arn $roleArn --type STANDARD --tags "key=project,value=upskilling-p2" --query stateMachineArn --output text
  Write-Output "Created state machine $arn"
}
Remove-Item $trust, $policy
