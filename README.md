# 河南师范大学校园网自动认证

原生 PowerShell 实现

---

## 快速使用

### 1. 配置账号密码
在当前目录下的 `config.json` 填入你的学号与宽带密码：
```json
{
  "username": "240832xxxx", // 学号
  "password": "your_password_here", // WiFi 密码
  "operator": "lt" // SIM卡运营商
}
```
*(注：运营商代码：联通 `lt`、移动 `yd`、电信 `dx`)*

### 2. 一键安装 Windows 自动触发
- **直接双击运行** `install_auto_auth.bat`
- **特性**：
  - **零环境依赖**：完全基于系统自带的 `powershell.exe`，免装 Python。
  - **精准触发**：仅在接入宿舍 Wi-Fi（`Htu-AuteWiFi` / `autewifi` 及其 5G 频段）时触发，连接其他 Wi-Fi 完全不唤醒。
  - **电池策略**：已解除电源限制，未插电状态下正常工作。
  - **在线保护**：已在线状态下 0.05 秒退出，不影响正常网络连接。

### 3. 一键卸载
- 如果不再需要自动认证，直接双击 `uninstall_auto_auth.bat` 即可彻底删除计划任务。

## TODO
- [ ] 教学楼区域自动认证落实
