# 河南师范大学校园网自动认证 (AuteWiFi - 纯 Python 原生版)

针对河南师范大学宿舍校园网（AuteWiFi / HSD-BRAS-2）的自动认证工具。纯 Python 标准库编写，**无任何第三方包依赖、无任何 PowerShell 签名或安全策略限制**，在任何装有 Python 的 Windows 电脑上均可开箱即用。

---

## 快速开始

### 1. 配置账号密码
在当前目录下的 `config.json` 填入你的学号与宽带密码：
```json
{
  "username": "240832xxxx",
  "password": "your_password_here",
  "operator": "lt"
}
```
*(注：运营商代码：联通 `lt`、移动 `yd`、电信 `dx`)*

### 2. 一键配置自动认证 (连 Wi-Fi 毫秒级静默唤醒)
- **直接双击运行** `install_auto_auth.bat`（或在终端运行 `python install_task.py`）
- **特性**：
  - **纯 Python 原生**：注册 Windows 原生计划任务，不依赖 PowerShell，彻底杜绝“未对文件进行数字签名”或“执行策略受限”等报错。
  - **精准触发**：通过 Windows 内核 WLAN 8001 事件监听，仅在接入宿舍 Wi-Fi（`Htu-AuteWiFi` / `autewifi` 及其 5G 频段）时触发，连接其他 Wi-Fi 完全不唤醒。
  - **后台静默**：自动寻找 `pythonw.exe` 静默运行，不弹 cmd 黑框。
  - **电池策略**：已解除电源限制，纯电池供电（未插电）状态下正常工作。
  - **在线保护**：连上后优先检测网络状态，已在线时 0.05 秒退出，不影响正常连接。
  - **自动日志**：运行过程自动写入同目录下的 `portal_auth.log`（自动限容 256KB）。

### 3. 一键卸载
- 如果不再需要自动认证，直接双击 `uninstall_auto_auth.bat` 即可彻底删除计划任务。

---

## 手动运行测试 (可选)
```bash
# 直接运行（自动读取 config.json）
python portal_auth.py

# 或命令行临时指定参数运行
python portal_auth.py 240832xxxx your_password lt
```
