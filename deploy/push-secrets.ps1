# Uploads backend\.env to AWS Parameter Store as one encrypted (SecureString) parameter, and lets the box's role read it.
# Run after every change to backend\.env:  powershell -File deploy\push-secrets.ps1
# The box fetches it at every boot, so the next demo-up picks the new values up.
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Param = "/upskilling-p2/onboarding-buddy/env"
$Role = "upskilling-p2-ec2-ecr-pull"
$Root = Split-Path $PSScriptRoot -Parent

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }
function Write-Json([string]$path, [string]$text) { [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false)) }

# Drop a byte-order mark and Windows line endings so the keys on the server are clean
$text = [IO.File]::ReadAllText((Join-Path $Root "backend\.env")).TrimStart([char]0xFEFF) -replace "`r", ""
$tmp = Join-Path $env:TEMP "env-param.txt"
Write-Json $tmp $text
Invoke-Aws ssm put-parameter --name $Param --type SecureString --value "file://$tmp" --overwrite --description "Onboarding Buddy .env (upskilling-p2)" | Out-Null
Remove-Item $tmp
Write-Output "Stored $Param (encrypted with the default AWS-managed key)"

# Read-only access to this one parameter, and decrypting through SSM only
$account = Invoke-Aws sts get-caller-identity --query Account --output text
$policy = Join-Path $env:TEMP "ssm-read-policy.json"
Write-Json $policy ('{"Version":"2012-10-17","Statement":[' +
  '{"Effect":"Allow","Action":"ssm:GetParameter","Resource":"arn:aws:ssm:' + $Region + ':' + $account + ':parameter' + $Param + '"},' +
  '{"Effect":"Allow","Action":"kms:Decrypt","Resource":"*","Condition":{"StringEquals":{"kms:ViaService":"ssm.' + $Region + '.amazonaws.com"}}}]}')
Invoke-Aws iam put-role-policy --role-name $Role --policy-name read-onboarding-buddy-env --policy-document "file://$policy"
Remove-Item $policy
Write-Output "Role $Role can read it"
