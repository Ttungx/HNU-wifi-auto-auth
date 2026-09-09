# -*- coding: utf-8 -*-
# 校园网自动认证 (纯 PowerShell 核心版)
param(
    [string]$Username,
    [string]$Password,
    [string]$Operator = "lt",
    [int]$Retries = 3
)

$HOST_IP = "10.101.2.194"
$PORT = 6060
$STATUS_URL = "http://10.101.2.239/clean-mac/ext/online/user/getUserByRequestIp"
$OFFLINE_URL = "http://10.101.2.205:8081/ext/offline-operator"
$SCHOOL_CODE = "3def184ad8f4755ff269862ea77393dd"
$SUFFIX_MAP = @{ "lt" = "@lt"; "yd" = "@yd"; "dx" = "@dx"; "jzg" = "@hsd"; "xnzy" = "@hsd" }

# 1. 检查连网状态
function Test-IsOnline {
    try {
        $r = Invoke-RestMethod -Uri $STATUS_URL -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.code -eq 1 -and $r.data.userId) { return $true }
    } catch {}
    try {
        $r = Invoke-WebRequest -Uri "http://captive.apple.com/hotspot-detect.html" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200 -and $r.Content -match "Success") { return $true }
    } catch {}
    return $false
}

# 2. 获取本地 IP
function Get-LocalIp {
    for ($i = 0; $i -lt 5; $i++) {
        try {
            $udp = New-Object System.Net.Sockets.UdpClient
            $udp.Connect($HOST_IP, $PORT)
            $ip = $udp.Client.LocalEndPoint.Address.ToString()
            $udp.Close()
            if ($ip -and -not $ip.StartsWith("169.254") -and $ip -ne "127.0.0.1") { return $ip }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return ([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1).IPAddressToString
}

# 3. 获取物理网卡 MAC
function Get-LocalMac {
    try {
        $adapter = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'Virtual|VMware|Hyper-V|Loopback' } | Select-Object -First 1
        if ($adapter -and $adapter.MacAddress) { return ($adapter.MacAddress -replace '-', ':').ToLower() }
    } catch {}
    return "00:00:00:00:00:00"
}

# 4. 踢下线旧设备 (后踢前)
function Invoke-KickDevice($userId, $pwd) {
    try {
        $body = @{ schoolCode = $SCHOOL_CODE; userId = $userId; password = $pwd }
        Invoke-RestMethod -Uri $OFFLINE_URL -Method Post -Body $body -TimeoutSec 3 -ErrorAction Stop | Out-Null
        Start-Sleep -Seconds 3
        return $true
    } catch { return $false }
}

# 5. 主认证逻辑
function Start-CampusLogin($user, $pwd, $op) {
    if (Test-IsOnline) {
        Write-Host "[+] 网络已在线，跳过认证。" -ForegroundColor Green
        return $true
    }

    $suffix = if ($SUFFIX_MAP.ContainsKey($op.ToLower())) { $SUFFIX_MAP[$op.ToLower()] } else { "@lt" }
    $fullUser = if ($user -match "@") { $user } else { "$user$suffix" }
    $maskedUser = if ($fullUser.Length -gt 8) { $fullUser.Substring(0, 3) + "****" + $fullUser.Substring($fullUser.Length - 5) } else { "***" }
    Write-Host "[*] 开始认证账号: $maskedUser" -ForegroundColor Cyan

    $ip = Get-LocalIp
    $mac = Get-LocalMac
    $acname = "HSD-BRAS-2"

    # 获取网关动态会话参数
    $session = $null
    try {
        $sessionUrl = "http://${HOST_IP}:${PORT}/PortalJsonAction.do?wlanuserip=$ip&wlanacname=$acname&mac=$mac&viewStatus=1"
        $session = Invoke-RestMethod -Uri $sessionUrl -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    } catch {}

    $pc = if ($session) { $session.portalconfig } else { $null }
    $sf = if ($session) { $session.serverForm } else { $null }
    $pf = if ($session) { $session.portalForm } else { $null }

    $serverip = if ($sf -and $sf.serverip) { $sf.serverip } else { "" }
    $portalVer = if ($sf -and $sf.portalVer) { $sf.portalVer } else { "0" }
    $portalpageid = if ($pc -and $pc.id) { $pc.id } else { "46" }
    $timestamp = if ($pc -and $pc.timestamp) { $pc.timestamp } else { [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
    $tokenUuid = if ($pc -and $pc.uuid) { $pc.uuid } else { [Guid]::NewGuid().ToString() }
    $vlan = if ($pf -and $pf.vlan) { $pf.vlan } else { "" }
    $hostname = [System.Net.Dns]::GetHostName()

    $params = @{
        userid = $fullUser
        passwd = $pwd
        wlanuserip = $ip
        wlanuseripv6 = ""
        wlanacname = $acname
        wlanacIp = $serverip
        ssid = ""
        vlan = $vlan
        mac = $mac
        version = $portalVer
        portalpageid = $portalpageid
        validateCode = ""
        timestamp = $timestamp
        uuid = $tokenUuid
        portaltype = "0"
        hostname = $hostname
        bindCtrlId = ""
    }

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            $qs = ($params.GetEnumerator() | ForEach-Object { "$([System.Uri]::EscapeDataString($_.Key))=$([System.Uri]::EscapeDataString($_.Value))" }) -join '&'
            $authUrl = "http://${HOST_IP}:${PORT}/quickauth.do?$qs"

            $res = Invoke-RestMethod -Uri $authUrl -TimeoutSec 4 -UseBasicParsing -ErrorAction Stop
            $code = "$($res.code)"
            $msg = "$($res.message)"

            if ($code -eq "0") {
                Write-Host "[+] 认证成功！已连通互联网。" -ForegroundColor Green
                return $true
            }

            Write-Host "[-] 认证失败 (code=$code): $msg" -ForegroundColor Yellow
            if (($msg -match "21" -or $msg -match "Limit") -and (Invoke-KickDevice $fullUser $pwd)) {
                Write-Host "[*] 已踢下线旧设备，正在重试..." -ForegroundColor Gray
                continue
            }
            if ($msg -match "密码" -or $msg -match "不存在" -or $msg -match "余额") {
                return $false
            }
        } catch {
            Write-Host "[!] 请求异常: $_" -ForegroundColor Red
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

# 入口分流
$workDir = $PSScriptRoot
if (-not $workDir) { $workDir = (Get-Location).Path }
$configPath = Join-Path $workDir "config.json"

if (-not $Username -and (Test-Path $configPath)) {
    try {
        $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $Username = $cfg.username
        $Password = $cfg.password
        if ($cfg.operator) { $Operator = $cfg.operator }
    } catch {}
}

if (-not $Username -or -not $Password) {
    if (Test-IsOnline) {
        Write-Host "[+] 当前设备已在线，无需认证。" -ForegroundColor Green
        exit 0
    }
    Write-Host "用法: .\portal_auth.ps1 -Username <学号> -Password <密码> [-Operator lt/yd/dx]" -ForegroundColor Yellow
    Write-Host "或在 config.json 中配置 username 与 password 后直接运行。" -ForegroundColor Yellow
    exit 1
}

$success = Start-CampusLogin $Username $Password $Operator
if ($success) { exit 0 } else { exit 1 }
