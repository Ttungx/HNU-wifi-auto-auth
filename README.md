# 河南师范大学校园网自动认证

纯 Python 实现，零第三方依赖。

---

## 快速使用

### 1. 配置账号密码
编辑 `config.json` 填入你的学号与宽带密码：
```json
{
  "username": "240832xxxx",
  "password": "your_password_here",
  "operator": "lt"
}
```
*(注：运营商代码：联通 `lt`、移动 `yd`、电信 `dx`)*

### 2. 一键安装自动认证
- **双击运行** `install_auto_auth.bat`
- **特性**：
  - **精准触发**：仅在接入宿舍 Wi-Fi（`Htu-AuteWiFi`）或教学楼 Wi-Fi（`HTU_Student` / `HTU_Teacher`）时自动唤醒后台认证，连接其他 Wi-Fi 不触发。
  - **智能识别**：自动识别所在区域，宿舍区走运营商宽带（`@lt` 等），教学楼走校园网（`@htu`），无需反复修改配置。
  - **后台静默**：自动调用 `pythonw.exe` 运行，不弹黑框。
  - **电池策略**：已解除电源限制，未插电状态下正常工作。
  - **在线保护**：已在线时 0.05 秒退出，不影响正常连接。

### 3. 一键卸载
- 双击 `uninstall_auto_auth.bat` 即可删除计划任务。

### 4. 手动运行 (可选)
```bash
python portal_auth.py
```

## 已支持区域
- [x] 宿舍区（Htu-AuteWiFi）
- [x] 教学楼/教学办公区（HTU_Student / HTU_Teacher）
