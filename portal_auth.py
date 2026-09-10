#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
校园网自动认证 (纯 Python 核心版)
针对安冉云 AuteWiFi (HSD-BRAS-2 / Ace Admin Portal)

- 零第三方依赖 (纯标准库)
- 双重在线状态检查 (已在线则 0.05 秒跳过，绝不重复登录或误踢设备)
- 动态参数解析与后踢前 (设备达上限时自动踢旧设备并重试)
- 运行日志自动写入同目录 portal_auth.log (自动限容 256KB)
"""

import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
import uuid

HOST, PORT = "10.101.2.194", 6060
STATUS_URL = "http://10.101.2.239/clean-mac/ext/online/user/getUserByRequestIp"
OFFLINE_URL = "http://10.101.2.205:8081/ext/offline-operator"
SCHOOL_CODE = "3def184ad8f4755ff269862ea77393dd"
SUFFIX_MAP = {"lt": "@lt", "yd": "@yd", "dx": "@dx", "jzg": "@hsd", "xnzy": "@hsd", "htu": "@htu"}

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(WORK_DIR, "portal_auth.log")


def log(msg: str) -> None:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now_str}] {msg}"
    print(msg)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 256 * 1024:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def is_online() -> bool:
    """检测是否已连网 (优先内网用户接口，离线快速返回)"""
    try:
        req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
            if data.get("code") == 1:
                return bool(data.get("data", {}).get("userId"))
    except Exception:
        pass
    try:
        req = urllib.request.Request("http://captive.apple.com/hotspot-detect.html", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return r.status == 200 and b"Success" in r.read()
    except Exception:
        return False


def get_local_ip() -> str:
    for _ in range(15):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((HOST, PORT))
                ip = s.getsockname()[0]
                if not ip.startswith("169.254") and ip != "127.0.0.1":
                    return ip
        except Exception:
            pass
        time.sleep(0.2)
    return socket.gethostbyname(socket.gethostname())


def get_local_mac() -> str:
    n = uuid.getnode()
    return ":".join(f"{(n >> i) & 0xff:02x}" for i in range(0, 48, 8)[::-1])


def sniff_redirect() -> dict:
    """捕获未认证时的 302 重定向动态参数"""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers): return fp
        http_error_301 = http_error_307 = http_error_302
    try:
        opener = urllib.request.build_opener(NoRedirect)
        resp = opener.open("http://www.msftconnecttest.com/redirect", timeout=2)
        loc = resp.headers.get("Location", "")
        if "portal.do" in loc:
            p = urllib.parse.urlparse(loc)
            qs = {k: v[0] for k, v in urllib.parse.parse_qs(p.query).items()}
            qs["_host"], qs["_port"] = p.hostname or HOST, p.port or PORT
            return qs
    except Exception:
        pass
    return {}


def kick_device(userid: str, passwd: str) -> bool:
    """设备超限时踢下线最旧设备 (后踢前)"""
    try:
        data = urllib.parse.urlencode({"schoolCode": SCHOOL_CODE, "userId": userid, "password": passwd}).encode()
        req = urllib.request.Request(OFFLINE_URL, data=data, headers={"User-Agent": "Mozilla/5.0"})
        urllib.request.urlopen(req, timeout=3)
        time.sleep(2.5)
        return True
    except Exception:
        return False


def login(user: str, passwd: str, op: str = "lt", retries: int = 3) -> bool:
    if is_online():
        log("[+] 网络已在线，跳过认证。")
        return True

    host, port, acname = HOST, PORT, "HSD-BRAS-2"
    ip = get_local_ip()
    mac = get_local_mac()

    log(f"[*] 探测参数: IP={ip}, MAC={mac}, AC={acname}")

    # 优先直接获取网关会话参数 (内网直连 ~20ms)
    session = {}
    vlan = ""
    try:
        q = urllib.parse.urlencode({"wlanuserip": ip, "wlanacname": acname, "mac": mac, "viewStatus": "1"})
        req = urllib.request.Request(f"http://{host}:{port}/PortalJsonAction.do?{q}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            session = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        log(f"[!] 直连网关异常，尝试嗅探重定向: {e}")
        sniffed = sniff_redirect()
        host = sniffed.get("_host", host)
        port = sniffed.get("_port", port)
        acname = sniffed.get("wlanacname", acname)
        vlan = sniffed.get("vlan", "")

    pc = session.get("portalconfig") or {}
    sf = session.get("serverForm") or {}
    pf = session.get("portalForm") or {}

    # 自动识别区域 (教学区 hsd-jxq / 宿舍区 hsd_dq)
    is_jxq = "jxq" in pc.get("tname", "") or str(pc.get("id")) == "82"
    if "@" in user:
        full_user = user
    elif is_jxq:
        full_user = f"{user}@htu.edu.cn" if op.lower() == "jzg" else f"{user}@htu"
    else:
        full_user = f"{user}{SUFFIX_MAP.get(op.lower(), '@lt')}"

    masked_user = full_user[:3] + "****" + full_user[-5:] if len(full_user) > 8 else "***"
    area_name = "教学区" if is_jxq else "宿舍区"
    log(f"[*] 开始认证账号: {masked_user} ({area_name})")

    params = {
        "userid": full_user,
        "passwd": passwd,
        "wlanuserip": ip,
        "wlanuseripv6": "",
        "wlanacname": acname,
        "wlanacIp": sf.get("serverip", ""),
        "ssid": "",
        "vlan": pf.get("vlan") or vlan,
        "mac": mac,
        "version": str(sf.get("portalVer", 0)),
        "portalpageid": str(pc.get("id", 46)),
        "validateCode": "",
        "timestamp": str(pc.get("timestamp", int(time.time() * 1000))),
        "uuid": str(pc.get("uuid", uuid.uuid4())),
        "portaltype": "0",
        "hostname": socket.gethostname(),
        "bindCtrlId": ""
    }

    for attempt in range(1, retries + 1):
        try:
            url = f"http://{host}:{port}/quickauth.do?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                res = json.loads(r.read().decode("utf-8", "ignore"))

            code, msg = str(res.get("code")), res.get("message", "")
            if code == "0":
                log("[+] 认证成功！已连通互联网。")
                return True

            log(f"[-] 认证失败 (code={code}): {msg}")
            if ("21" in msg or "Limit" in msg) and kick_device(full_user, passwd):
                log("[*] 已踢下线旧设备，正在重试...")
                continue
            if any(k in msg for k in ["密码", "不存在", "余额"]):
                log(f"[-] 凭据或账号异常，终止重试: {msg}")
                return False
        except Exception as e:
            log(f"[!] 认证请求异常: {e}")
        time.sleep(2)

    return False


def main():
    cfg = {}
    config_path = os.path.join(WORK_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            log(f"[-] 读取 config.json 失败: {e}")

    user = sys.argv[1] if len(sys.argv) > 1 else cfg.get("username")
    passwd = sys.argv[2] if len(sys.argv) > 2 else cfg.get("password")
    op = sys.argv[3] if len(sys.argv) > 3 else cfg.get("operator", "lt")

    if not user or not passwd:
        if is_online():
            log("[+] 当前设备已在线，无需认证。")
            sys.exit(0)
        log("[-] 错误: 未配置账号或密码。")
        log("    用法: python portal_auth.py [学号] [密码] [运营商: lt/yd/dx]")
        log("    或者在 config.json 中配置 username 与 password 后直接运行。")
        sys.exit(1)

    sys.exit(0 if login(user, passwd, op) else 1)


if __name__ == "__main__":
    main()
