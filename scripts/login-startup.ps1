param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$taskName = 'DayframeAtLogin'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output 'Dayframe login startup removed. Archive data is unchanged.'
    exit
}
$launchPath = Join-Path $PSScriptRoot 'start.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "{0}"' -f $launchPath)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Start local Dayframe and open the journal on login (user opted in).' -Force | Out-Null
Write-Output 'Enabled. Docker Desktop must also start at login. Remove with: ./scripts/login-startup.ps1 -Remove'
