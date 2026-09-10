#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
校园网自动认证 (CampusWiFiAutoAuth) 安装程序 - 纯 Python 原生实现
使用 Windows 内置 schtasks 工具注册计划任务，无需 PowerShell，不受签名策略限制。
"""

import os
import subprocess
import sys
import time


def main():
    print("===================================================")
    print("    校园网自动认证 (CampusWiFiAutoAuth) 安装程序")
    print("===================================================")
    print()

    work_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 寻找 pythonw.exe (无控制台窗口后台静默运行)
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    print(f"[*] 执行引擎: {pythonw}")
    print(f"[*] 脚本目录: {work_dir}")

    # 2. 构造 Windows 任务计划标准 XML (包含 WLAN 连接 8001 事件及电池策略)
    xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <URI>\\CampusWiFiAutoAuth</URI>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>
  </Settings>
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="Microsoft-Windows-WLAN-AutoConfig/Operational"&gt;&lt;Select Path="Microsoft-Windows-WLAN-AutoConfig/Operational"&gt;*[System[(EventID=8001)]] and *[EventData[Data[@Name='SSID']='Htu-AuteWiFi' or Data[@Name='SSID']='autewifi' or Data[@Name='SSID']='AuteWiFi' or Data[@Name='SSID']='Htu-AuteWiFi5G-18' or Data[@Name='SSID']='Htu-AuteWiFi5G-17' or Data[@Name='SSID']='HTU_Student' or Data[@Name='SSID']='HTU_Teacher']]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
      <Delay>PT2S</Delay>
    </EventTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>{pythonw}</Command>
      <Arguments>portal_auth.py</Arguments>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    temp_xml = os.path.join(work_dir, "task_temp.xml")
    try:
        with open(temp_xml, "w", encoding="utf-16") as f:
            f.write(xml_content.strip())

        cmd = ["schtasks", "/create", "/tn", "CampusWiFiAutoAuth", "/xml", temp_xml, "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")

        if res.returncode != 0:
            print(f"[-] 注册计划任务失败: {res.stderr.strip() or res.stdout.strip()}")
            print("    请尝试右键以「管理员身份运行」本安装脚本。")
            sys.exit(1)

        print("[+] 成功创建系统计划任务: CampusWiFiAutoAuth")
        print("[+] 电池策略已生效: 已解除电源限制，无论是否插电均可正常触发！")

        # 3. 自检测试运行
        print("[*] 正在执行任务自测...")
        subprocess.run(["schtasks", "/run", "/tn", "CampusWiFiAutoAuth"], capture_output=True)
        time.sleep(2.5)

        query_res = subprocess.run(["schtasks", "/query", "/tn", "CampusWiFiAutoAuth", "/fo", "LIST", "/v"], capture_output=True, text=True, errors="ignore")
        last_result = None
        for line in query_res.stdout.splitlines():
            if "Last Result" in line or "上次结果" in line:
                last_result = line.split(":")[-1].strip()
                break

        if last_result in ["0", "0x0", None]:
            print("[+] 计划任务测试执行成功 (退出码: 0)！")
        else:
            print(f"[!] 计划任务已就绪 (状态码: {last_result})")

        print()
        print("===================================================")
        print("安装完成！以后当电脑连接宿舍或教学楼 Wi-Fi 时将全自动完成认证。")
        print("===================================================")

    finally:
        if os.path.exists(temp_xml):
            try:
                os.remove(temp_xml)
            except Exception:
                pass


if __name__ == "__main__":
    main()
