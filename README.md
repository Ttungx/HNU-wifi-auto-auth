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
  - **精准触发**：仅在接入宿舍 Wi-Fi（`Htu-AuteWiFi` / `autewifi` 及其 5G 频段）时自动唤醒后台认证，连接其他 Wi-Fi 不触发。
  - **后台静默**：自动调用 `pythonw.exe` 运行，不弹黑框。
  - **电池策略**：已解除电源限制，未插电状态下正常工作。
  - **在线保护**：已在线时 0.05 秒退出，不影响正常连接。

### 3. 一键卸载
- 双击 `uninstall_auto_auth.bat` 即可删除计划任务。

### 4. 手动运行 (可选)
```bash
python portal_auth.py
```

## TODO
- [ ] 教学楼区域自动认证落实
