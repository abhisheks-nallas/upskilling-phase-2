# Builds the API image on this PC and pushes it to ECR as :latest. The server only ever pulls it, it never builds.
# Run:  powershell -File deploy\push-image.ps1
$ErrorActionPreference = "Stop"
$Region = "ap-southeast-2"
$Repo = "upskilling-p2/onboarding-buddy"
$Backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"

function Invoke-Aws { & aws @args --region $Region; if ($LASTEXITCODE -ne 0) { throw "aws failed: $args" } }

$account = Invoke-Aws sts get-caller-identity --query Account --output text
$registry = "$account.dkr.ecr.$Region.amazonaws.com"
$image = "$registry/${Repo}:latest"

$ErrorActionPreference = "Continue"  # PowerShell 5.1 turns a native command's stderr into an error, and "repo not found" is expected here
& aws ecr describe-repositories --repository-names $Repo --region $Region *> $null
$missing = $LASTEXITCODE -ne 0
$ErrorActionPreference = "Stop"
if ($missing) {
  Invoke-Aws ecr create-repository --repository-name $Repo --tags "Key=project,Value=upskilling-p2" | Out-Null
  Write-Output "Created ECR repository $Repo"
}

docker build -t $image $Backend
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
# the token goes straight from aws to docker, it is never printed
Invoke-Aws ecr get-login-password | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { throw "docker login failed" }
docker push $image
if ($LASTEXITCODE -ne 0) { throw "docker push failed" }
Write-Output "Pushed $image"
