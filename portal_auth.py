#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
校园网自动认证 (纯 Python 核心版)
针对安冉云 AuteWiFi (HSD-BRAS-2 / Ace Admin Portal)

- 零第三方依赖 (纯标准库)
- 开机/唤醒竞态自愈: 先等 DHCP 就绪, 就绪前不空转, 总窗口内自动重试
- 快速在线检查: 内网接口可达时一次请求即判定, 已在线毫秒级跳过
- 非校园网环境 (非 10.x 网段) 自动安静退出, 不干扰外网/热点使用
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
CAMPUS_PREFIXES = ("10.",)
AUTH_WINDOW = 150
PROBE_INTERVAL = 0.25
RETRY_INTERVAL = 1.0

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
    """检测是否已连网 (内网接口可达时以其返回为准，一次请求即判定)"""
    try:
        req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.2) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        d = data.get("data")
        return isinstance(d, dict) and bool(d.get("userId"))
    except Exception:
        pass
    try:
        req = urllib.request.Request("http://captive.apple.com/hotspot-detect.html", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.2) as r:
            return r.status == 200 and b"Success" in r.read()
    except Exception:
        return False


def wait_for_ip(deadline: float):
    """等待 DHCP 分配有效 IP, 超时返回 None"""
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((HOST, PORT))
                ip = s.getsockname()[0]
            if ip and not ip.startswith(("127.", "169.254")):
                return ip
        except OSError:
            pass
        time.sleep(PROBE_INTERVAL)
    return None


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


def fetch_session(ip: str, mac: str, verbose: bool = False):
    """获取网关会话参数，失败时回退嗅探重定向。返回 (session, host, port, acname, vlan) 或 None"""
    try:
        q = urllib.parse.urlencode({"wlanuserip": ip, "wlanacname": "HSD-BRAS-2", "mac": mac, "viewStatus": "1"})
        req = urllib.request.Request(f"http://{HOST}:{PORT}/PortalJsonAction.do?{q}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8", "ignore")), HOST, PORT, "HSD-BRAS-2", ""
    except Exception as e:
        if verbose:
            log(f"[!] 直连网关异常，尝试嗅探重定向: {e}")
    sniffed = sniff_redirect()
    if sniffed:
        return {}, sniffed.get("_host", HOST), sniffed.get("_port", PORT), sniffed.get("wlanacname", "HSD-BRAS-2"), sniffed.get("vlan", "")
    return None


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


def login(user: str, passwd: str, op: str = "lt", retries: int = 3, window: float = AUTH_WINDOW,
          retry_delay: float = RETRY_INTERVAL) -> bool:
    t0 = time.monotonic()
    deadline = t0 + window

    ip = wait_for_ip(deadline)
    if ip is None:
        log(f"[!] 等待网络就绪超时 ({window:.0f}s)，本次跳过，等待计划任务重试。")
        return False
    if not ip.startswith(CAMPUS_PREFIXES):
        log(f"[*] 非校园网环境 (IP={ip})，跳过认证。")
        return True
    if time.monotonic() - t0 > 1:
        log(f"[*] 网络就绪耗时 {time.monotonic() - t0:.1f}s (IP={ip})")

    if is_online():
        log("[+] 网络已在线，跳过认证。")
        return True

    mac = get_local_mac()
    log(f"[*] 探测参数: IP={ip}, MAC={mac}, AC=HSD-BRAS-2")

    session = None
    host, port, acname, vlan = HOST, PORT, "HSD-BRAS-2", ""
    first = True
    while session is None and time.monotonic() < deadline:
        got = fetch_session(ip, mac, verbose=first)
        first = False
        if got is not None:
            session, host, port, acname, vlan = got
            break
        time.sleep(RETRY_INTERVAL)
    if session is None:
        log("[!] 无法获取网关会话参数，本次跳过，等待计划任务重试。")
        return False

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
            with urllib.request.urlopen(req, timeout=3) as r:
                res = json.loads(r.read().decode("utf-8", "ignore"))

            code, msg = str(res.get("code")), res.get("message", "")
            if code == "0":
                log(f"[+] 认证成功！总耗时 {time.monotonic() - t0:.2f}s")
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
        if attempt < retries:
            time.sleep(retry_delay)

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

    ok = login(user, passwd, op,
               retries=int(cfg.get("max_retries", 3)),
               window=float(cfg.get("auth_window_seconds", AUTH_WINDOW)),
               retry_delay=float(cfg.get("retry_delay_seconds", RETRY_INTERVAL)))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
