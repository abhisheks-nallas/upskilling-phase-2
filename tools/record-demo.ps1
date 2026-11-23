# Records the whole demo with OBS, hands-off: terminal run of Part 1, API docs and LangSmith in the browser, Part 2 (stop).
#   powershell -File tools\record-demo.ps1 -LangSmithUrl "https://smith.langchain.com/o/.../projects/p/..."
# Needs: OBS running or installable at -ObsExe with the WebSocket server on (see tools\obs_record.py), Brave, AWS CLI.
# Close WhatsApp and turn on Do Not Disturb first: the whole primary monitor is recorded.
param(
  [string]$LangSmithUrl = "",
  [int]$Pause = 6,
  [string]$ObsExe = "D:\Softwares\obs-studio\bin\64bit\obs64.exe",
  [string]$BrowserExe = "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$py = Join-Path $env:TEMP "obs-venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv (Join-Path $env:TEMP "obs-venv"); & $py -m pip install -q obsws-python python-dotenv }

if (-not (Get-Process obs64 -ErrorAction SilentlyContinue)) {
  Start-Process $ObsExe -WorkingDirectory (Split-Path $ObsExe) -ArgumentList "--disable-shutdown-check", "--minimize-to-tray"
  Start-Sleep 8
}

function Wait-File([string]$path, [int]$seconds) {
  for ($i = 0; $i -lt $seconds; $i++) { if (Test-Path $path) { return }; Start-Sleep 1 }
  throw "Timed out waiting for $path"
}
function Start-Demo([int]$part) {
  Start-Process powershell -WindowStyle Maximized -PassThru -ArgumentList "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "tools\demo.ps1", "-Part", "$part", "-Pause", "$Pause"
}


# Windows will not let a background process pull a window to the front. Minimizing the other windows and
# maximizing the wanted one works without focus rights, so that is how each scene is brought on screen.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinFront {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hgt, bool repaint);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  // cmd 3 = move onto the primary monitor (top left is 0,0) and maximize there, 6 = minimize. Returns how many windows matched.
  public static int Apply(string titlePart, int cmd) {
    int n = 0;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(256);
      GetWindowText(h, sb, 256);
      if (!sb.ToString().Contains(titlePart)) return true;
      if (cmd == 3) {
        ShowWindow(h, 9);                       // restore, a maximized window cannot be moved
        MoveWindow(h, 100, 100, 1500, 850, true); // browsers can open on the other monitor
        ShowWindow(h, 3);
        SetForegroundWindow(h);
      } else { ShowWindow(h, cmd); }
      n++;
      return true;
    }, IntPtr.Zero);
    return n;
  }
}
"@
function Show-Window([string]$titlePart, [string[]]$hide = @()) {
  for ($i = 0; $i -lt 10; $i++) {
    if ([WinFront]::Apply($titlePart, 3) -gt 0) { break }
    Start-Sleep 1
  }
  foreach ($h in $hide) { [void][WinFront]::Apply($h, 6) }
  Start-Sleep 2
}

New-Item -ItemType Directory -Force recordings | Out-Null
Remove-Item recordings\demo-part1.done, recordings\demo-part2.done, recordings\demo-ip.txt -ErrorAction SilentlyContinue
# Start every take from the same state: box stopped, so the start-up is on camera
& (Join-Path $PSScriptRoot "..\deploy\demo-down.ps1")
$windows = @()
& $py tools\obs_record.py start
try {
  Start-Sleep 3
  $windows += Start-Demo 1
  Show-Window "demo part 1"
  Wait-File recordings\demo-part1.done 900
  Start-Sleep 8

  $ip = (Get-Content recordings\demo-ip.txt).Trim()
  Start-Process $BrowserExe -ArgumentList "--new-window", "--start-maximized", "http://${ip}:8000/docs"
  Start-Sleep 5
  Show-Window "Swagger" @("demo part 1", "LangSmith")
  Start-Sleep 18
  if ($LangSmithUrl) {
    Start-Process $BrowserExe -ArgumentList "--new-window", "--start-maximized", $LangSmithUrl
    Start-Sleep 5
    Show-Window "LangSmith" @("Swagger", "demo part 1")
    Start-Sleep 30
  }

  $windows += Start-Demo 2
  Show-Window "demo part 2" @("LangSmith", "Swagger", "demo part 1")
  Wait-File recordings\demo-part2.done 600
  Start-Sleep 10
}
finally {
  & $py tools\obs_record.py stop
  $windows | ForEach-Object { Stop-Process -Id $_.Id -ErrorAction SilentlyContinue }
}
