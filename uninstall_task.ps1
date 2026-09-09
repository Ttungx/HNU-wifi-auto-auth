# 校园网自动认证卸载脚本
schtasks /delete /tn "CampusWiFiAutoAuth" /f >$null 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[+] 校园网自动认证计划任务 (CampusWiFiAutoAuth) 已成功卸载。" -ForegroundColor Green
} else {
    Write-Host "[-] 计划任务不存在或此前已被删除。" -ForegroundColor Yellow
}
