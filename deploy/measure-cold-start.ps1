# Measures Fission cold start vs warm calls for the welcome function and appends the results to docs\cold-start.csv.
# Run:  powershell -File deploy\measure-cold-start.ps1 -Ip 1.2.3.4 [-IdleSeconds 180]
# Cold = the first call after the function pod has been idle long enough for Fission to remove it (default ~2 min).
param(
  [Parameter(Mandatory = $true)][string]$Ip,
  [int]$IdleSeconds = 180,   # use 0 to skip the wait (the first call is then only cold if nothing has called it recently)
  [int]$WarmCalls = 5
)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $Root "backend\.env"
$key = ((Get-Content $envFile | Where-Object { $_ -match '^API_KEY=' }) -split '=', 2)[1].Trim().Trim('"', "'")
$csv = Join-Path $Root "docs\cold-start.csv"
New-Item -ItemType Directory -Force (Split-Path $csv) | Out-Null
if (-not (Test-Path $csv)) { "timestamp_utc,kind,call,total_seconds,handler_seconds,pod_call_number,source" | Out-File -Encoding ascii $csv }

$bodyFile = Join-Path $env:TEMP "welcome.json"
'{"name":"Asha","role":"developer"}' | Out-File -Encoding ascii $bodyFile

function Invoke-Welcome([string]$kind, [int]$n) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $raw = curl.exe -s -m 60 -H "X-API-Key: $key" -H "Content-Type: application/json" --data-binary "@$bodyFile" "http://${Ip}:31314/welcome"
  $sw.Stop()
  try { $r = $raw | ConvertFrom-Json } catch { throw "Bad reply: $raw" }
  if ($r.error -and -not $r.source) { throw "Function error: $($r.error)" }
  $total = [math]::Round($sw.Elapsed.TotalSeconds, 2)
  $line = "{0},{1},{2},{3},{4},{5},{6}" -f (Get-Date).ToUniversalTime().ToString("s"), $kind, $n, $total, $r.handler_seconds, $r.pod_call_number, $r.source
  Add-Content -Encoding ascii $csv $line
  Write-Output ("{0,-5} #{1}: {2}s total (handler {3}s, pod call {4}, {5})" -f $kind, $n, $total, $r.handler_seconds, $r.pod_call_number, $r.source)
}

if ($IdleSeconds -gt 0) { Write-Output "Waiting $IdleSeconds s so the function pod goes idle..."; Start-Sleep $IdleSeconds }
Invoke-Welcome "cold" 1
1..$WarmCalls | ForEach-Object { Invoke-Welcome "warm" $_ }
Write-Output "Logged to $csv"
