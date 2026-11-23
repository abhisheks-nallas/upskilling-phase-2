# Scripted demo of Milestones 1 and 2 for a screen recording. Output is paced and kept short.
#   powershell -File tools\demo.ps1 -Part 1   # tests, start the stack, chat agent, plan agents, Fission, cold start
#   powershell -File tools\demo.ps1 -Part 2   # stop the stack through Step Functions
# The API key is read from backend\.env and never printed. ASCII only on purpose (Windows PowerShell 5.1).
param([int]$Part = 1, [int]$Pause = 5, [int]$Hours = 1)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8  # the model answers with non-ASCII characters
$Root = Split-Path $PSScriptRoot -Parent
$Host.UI.RawUI.WindowTitle = "Onboarding Buddy demo part $Part"  # lets tools\record-demo.ps1 find this window
Set-Location $Root
$Region = "ap-southeast-2"
$key = ((Get-Content backend\.env | Where-Object { $_ -match '^API_KEY=' }) -split '=', 2)[1].Trim().Trim('"', "'")

function Step([string]$title, [bool]$first = $false) {
  if (-not $first) { Start-Sleep $Pause; Clear-Host }
  Write-Host ""
  Write-Host "=== $title ===" -ForegroundColor Cyan
  Write-Host ""
}

function Get-BoxIp {
  aws ec2 describe-instances --region $Region --filters "Name=tag:Name,Values=upskilling-p2-stack" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].PublicIpAddress | [0]" --output text
}

# Calls a streaming endpoint and yields one object per server-sent event
function Invoke-Sse([string]$ip, [string]$path, [string]$json) {
  $f = Join-Path $env:TEMP "demo-body.json"
  [IO.File]::WriteAllText($f, $json, (New-Object Text.UTF8Encoding $false))
  $event = "message"
  curl.exe -s -N -m 120 -H "X-API-Key: $key" -H "Content-Type: application/json" --data-binary "@$f" "http://${ip}:8000$path" | ForEach-Object {
    if ($_ -match '^event:\s*(.+)$') { $event = $Matches[1].Trim() }
    elseif ($_ -match '^data:\s*(.*)$') { [pscustomobject]@{ Event = $event; Data = ($Matches[1] | ConvertFrom-Json) } }
  }
}

if ($Part -eq 1) {
  Step "Onboarding Buddy: Milestone 1 + 2 demo" $true
  Write-Host "Branch and recent commits"
  git branch --show-current
  git log --oneline -8
  Write-Host ""
  Write-Host "Files"
  Get-ChildItem backend -File | Where-Object { $_.Extension -in ".py", ".txt", ".ini" -or $_.Name -eq "Dockerfile" } | ForEach-Object { "  backend\" + $_.Name }
  Write-Host "  fission\welcome\welcome.py"
  Write-Host "  deploy\  (ECR push, stack-up, demo-up, demo-down, Step Functions definition)"

  Step "Tests (no outside services are called)"
  Set-Location backend
  & .\.venv\Scripts\python.exe -m pytest -q 2>&1 | Select-Object -Last 4
  Set-Location $Root

  Step "Start the staging stack with one command (Step Functions arms the auto-stop)"
  & .\deploy\demo-up.ps1 -Hours $Hours
  $ip = Get-BoxIp
  Set-Content -Path recordings\demo-ip.txt -Value $ip

  Step "Milestone 1: the API needs a key"
  $hi = Join-Path $env:TEMP "demo-hi.json"
  [IO.File]::WriteAllText($hi, '{"message":"hi"}', (New-Object Text.UTF8Encoding $false))
  $nokey = curl.exe -s -o NUL -w "%{http_code}" -X POST -H "Content-Type: application/json" --data-binary "@$hi" "http://${ip}:8000/chat/stream"
  Write-Host "POST /chat/stream without a key  -> HTTP $nokey"
  $health = curl.exe -s -o NUL -w "%{http_code}" "http://${ip}:8000/health-check"
  Write-Host "GET  /health-check               -> HTTP $health"

  Step "Milestone 1: streaming agent with two tools"
  Write-Host 'Question: I am a QA engineer starting on 2026-12-01. What access do I need and what is my first week? Keep it short.' -ForegroundColor Yellow
  Write-Host ""
  Invoke-Sse $ip "/chat/stream" '{"message":"I am a QA engineer starting on 2026-12-01. What access do I need and what is my first week? Keep it short."}' | ForEach-Object {
    if ($_.Event -eq "message") { Write-Host -NoNewline $_.Data.text }
    elseif ($_.Event -eq "error") { Write-Host $_.Data.error -ForegroundColor Red }
  }
  Write-Host ""

  Step "Milestone 2: Planner and Reviewer agents (first draft is damaged on purpose)"
  Invoke-Sse $ip "/plan/stream" '{"role":"developer","start_date":"2026-12-01","spoil_first_draft":true}' | ForEach-Object {
    $d = $_.Data
    if ($_.Event -eq "progress") {
      if ($d.step -eq "planner") { Write-Host "Planner  : writing draft $($d.attempt)" -ForegroundColor Yellow }
      elseif ($d.step -eq "reviewer" -and $d.approved) { Write-Host "Reviewer : approved" -ForegroundColor Green }
      elseif ($d.step -eq "reviewer") { $fb = [string]$d.feedback; if ($fb.Length -gt 95) { $fb = $fb.Substring(0, 95) + "..." }; Write-Host "Reviewer : REJECTED - $fb" -ForegroundColor Red }
      elseif ($d.step -eq "fallback") { Write-Host "Fallback : using the plain template" -ForegroundColor Magenta }
    }
    elseif ($_.Event -eq "result") {
      Write-Host ""
      Write-Host "Result   : source=$($d.source), $($d.plan.Count) working days" -ForegroundColor Cyan
      $d.plan | Select-Object -First 4 | ForEach-Object { $t = $_.task; if ($t.Length -gt 80) { $t = $t.Substring(0, 80) + "..." }; Write-Host "  $($_.date) $($_.day)  $t" }
    }
    elseif ($_.Event -eq "error") { Write-Host $d.error -ForegroundColor Red }
  }

  Step "Milestone 2: Fission function with an HTTP trigger, and its cold start"
  $f = Join-Path $env:TEMP "demo-welcome.json"
  [IO.File]::WriteAllText($f, '{"name":"Asha","role":"developer"}', (New-Object Text.UTF8Encoding $false))
  foreach ($n in 1, 2) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = curl.exe -s -m 60 -H "X-API-Key: $key" -H "Content-Type: application/json" --data-binary "@$f" "http://${ip}:31314/welcome" | ConvertFrom-Json
    $sw.Stop()
    $kind = if ($r.pod_call_number -eq 1) { "COLD (new pod)" } else { "warm" }
    if ($r.source -ne "groq") { $kind = "(Groq unavailable, plain fallback note)" }
    Write-Host ("POST /welcome #{0}: {1,5:N2}s  pod call {2}  {3}" -f $n, $sw.Elapsed.TotalSeconds, $r.pod_call_number, $kind)
    if ($n -eq 1) { Write-Host "  $($r.note)" -ForegroundColor Yellow }
  }
  Write-Host ""
  Write-Host "Logged measurements (docs\cold-start.csv):"
  Import-Csv docs\cold-start.csv | Group-Object kind | ForEach-Object {
    $avg = ($_.Group | ForEach-Object { [double]$_.total_seconds } | Measure-Object -Average).Average
    Write-Host ("  {0,-5} {1} calls, average {2:N2}s" -f $_.Name, $_.Count, $avg)
  }

  Step "Traces and API docs are in the browser next"
  Write-Host "API docs : http://${ip}:8000/docs"
  Write-Host "LangSmith: smith.langchain.com (Planner, Reviewer and chat runs)"
  Set-Content -Path recordings\demo-part1.done -Value (Get-Date)
}

if ($Part -eq 2) {
  Step "Stop everything through Step Functions" $true
  & .\deploy\demo-down.ps1
  Write-Host ""
  Write-Host "Recent runs of the state machine:"
  $arn = aws stepfunctions list-state-machines --region $Region --query "stateMachines[?name=='upskilling-p2-demo-session'].stateMachineArn | [0]" --output text
  aws stepfunctions list-executions --region $Region --state-machine-arn $arn --max-results 4 --query "executions[].[name,status]" --output table
  Write-Host ""
  aws ec2 describe-instances --region $Region --filters "Name=tag:project,Values=upskilling-p2" --query "Reservations[].Instances[].[Tags[?Key=='Name']|[0].Value,InstanceType,State.Name]" --output table
  Set-Content -Path recordings\demo-part2.done -Value (Get-Date)
}
