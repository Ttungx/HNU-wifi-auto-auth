# 校园网自动认证安装脚本
$ErrorActionPreference = 'Stop'

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    校园网自动认证安装程序" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$workDir = $PSScriptRoot
if (-not $workDir) {
    $workDir = (Get-Location).Path
}

# 1. 直接使用 Windows 自带的 powershell.exe
$psExe = "powershell.exe"
$psScript = "portal_auth.ps1"
$fullScriptPath = Join-Path $workDir $psScript

if (-not (Test-Path $fullScriptPath)) {
    Write-Host "[-] 错误: 未找到认证核心脚本 $psScript！" -ForegroundColor Red
    exit 1
}

Write-Host "[*] 核心引擎: Windows 原生 PowerShell (无需安装 Python)" -ForegroundColor Green
Write-Host ("[*] 脚本工作目录: " + $workDir) -ForegroundColor Gray

# 2. 构造静默执行动作 (-WindowStyle Hidden 完全隐藏控制台窗口)
$action = New-ScheduledTaskAction -Execute $psExe -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$fullScriptPath`"" -WorkingDirectory $workDir

# 3. 构造 WLAN 8001 事件触发器 (针对宿舍 autewifi)
$query = @'
<QueryList>
  <Query Id="0" Path="Microsoft-Windows-WLAN-AutoConfig/Operational">
    <Select Path="Microsoft-Windows-WLAN-AutoConfig/Operational">*[System[(EventID=8001)]] and *[EventData[Data[@Name="SSID"]="Htu-AuteWiFi" or Data[@Name="SSID"]="autewifi" or Data[@Name="SSID"]="AuteWiFi" or Data[@Name="SSID"]="Htu-AuteWiFi5G-18" or Data[@Name="SSID"]="Htu-AuteWiFi5G-17"]]</Select>
  </Query>
</QueryList>
'@

$trigger = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler | New-CimInstance -ClientOnly
$trigger.Enabled = $true
$trigger.Subscription = $query
$trigger.Delay = 'PT2S'

# 4. 电源策略设置：无论是否有电源限制（使用电池/未插电）都允许启动并执行
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

# 5. 注册系统计划任务
Register-ScheduledTask -TaskName 'CampusWiFiAutoAuth' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "[+] 成功创建系统计划任务: CampusWiFiAutoAuth" -ForegroundColor Green
Write-Host "[+] 电池策略已生效: 已解除电源限制，无论是否接通电源(插电/纯电池供电)均可正常触发！" -ForegroundColor Green

# 6. 自检测试运行
Write-Host "[*] 正在执行任务自检..." -ForegroundColor Gray
Start-ScheduledTask -TaskName 'CampusWiFiAutoAuth'
Start-Sleep -Seconds 2
$res = (Get-ScheduledTaskInfo -TaskName 'CampusWiFiAutoAuth').LastTaskResult

if ($res -eq 0) {
    Write-Host "[+] 计划任务测试执行成功 (退出码: 0)！" -ForegroundColor Green
} else {
    Write-Host ("[!] 计划任务已就绪，测试返回值: " + $res) -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "安装完成！以后当电脑连接宿舍 Wi-Fi 时将全自动完成认证。" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
