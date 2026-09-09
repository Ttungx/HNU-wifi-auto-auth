#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""校园网自动认证实现"""

import json, os, socket, sys, time, urllib.parse, urllib.request, uuid

HOST, PORT = "10.101.2.194", 6060
STATUS_URL = "http://10.101.2.239/clean-mac/ext/online/user/getUserByRequestIp"
OFFLINE_URL = "http://10.101.2.205:8081/ext/offline-operator"
SCHOOL_CODE = "3def184ad8f4755ff269862ea77393dd"
SUFFIX_MAP = {"lt": "@lt", "yd": "@yd", "dx": "@dx", "jzg": "@hsd", "xnzy": "@hsd"}


def is_online() -> bool:
    """检测是否已认证连网 (优先内网用户接口，兜底 Captive 探针)"""
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=2) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
            if data.get("code") == 1 and data.get("data", {}).get("userId"):
                return True
    except Exception:
        pass
    try:
        with urllib.request.urlopen("http://captive.apple.com/hotspot-detect.html", timeout=2) as r:
            return r.status == 200 and b"Success" in r.read()
    except Exception:
        return False


def get_local_ip() -> str:
    for _ in range(5):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((HOST, PORT))
                ip = s.getsockname()[0]
                if not ip.startswith("169.254") and ip != "127.0.0.1":
                    return ip
        except Exception:
            pass
        time.sleep(1)
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
    """设备超限时踢下线最旧设备"""
    try:
        data = urllib.parse.urlencode({"schoolCode": SCHOOL_CODE, "userId": userid, "password": passwd}).encode()
        urllib.request.urlopen(OFFLINE_URL, data=data, timeout=3)
        time.sleep(2.5)
        return True
    except Exception:
        return False


def login(user: str, passwd: str, op: str = "lt", retries: int = 3) -> bool:
    if is_online():
        print("[+] 网络已在线，跳过认证。")
        return True

    full_user = user if "@" in user else f"{user}{SUFFIX_MAP.get(op.lower(), '@lt')}"
    masked_user = full_user[:3] + "****" + full_user[-5:] if len(full_user) > 8 else "***"
    print(f"[*] 开始认证账号: {masked_user}")

    sniffed = sniff_redirect()
    host = sniffed.get("_host", HOST)
    port = sniffed.get("_port", PORT)
    ip = sniffed.get("wlanuserip") or get_local_ip()
    mac = sniffed.get("mac") or get_local_mac()
    acname = sniffed.get("wlanacname", "HSD-BRAS-2")

    # 获取网关会话参数
    session = {}
    try:
        q = urllib.parse.urlencode({"wlanuserip": ip, "wlanacname": acname, "mac": mac, "viewStatus": "1"})
        with urllib.request.urlopen(f"http://{host}:{port}/PortalJsonAction.do?{q}", timeout=3) as r:
            session = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        pass

    pc = session.get("portalconfig") or {}
    sf = session.get("serverForm") or {}
    pf = session.get("portalForm") or {}

    params = {
        "userid": full_user,
        "passwd": passwd,
        "wlanuserip": ip,
        "wlanuseripv6": "",
        "wlanacname": acname,
        "wlanacIp": sf.get("serverip", ""),
        "ssid": "",
        "vlan": pf.get("vlan") or sniffed.get("vlan", ""),
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
                print("[+] 认证成功！已连通互联网。")
                return True

            print(f"[-] 认证失败 (code={code}): {msg}")
            if ("21" in msg or "Limit" in msg) and kick_device(full_user, passwd):
                print("[*] 已踢下线旧设备，正在重试...")
                continue
            if any(k in msg for k in ["密码", "不存在", "余额"]):
                return False
        except Exception as e:
            print(f"[!] 请求异常: {e}")
        time.sleep(2)

    return False


def main():
    cfg = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass

    # 支持命令行参数优先: python portal_auth.py [学号] [密码] [运营商: lt/yd/dx]
    user = sys.argv[1] if len(sys.argv) > 1 else cfg.get("username")
    passwd = sys.argv[2] if len(sys.argv) > 2 else cfg.get("password")
    op = sys.argv[3] if len(sys.argv) > 3 else cfg.get("operator", "lt")

    if not user or not passwd:
        if is_online():
            print("[+] 当前设备已在线，无需认证。")
            sys.exit(0)
        print("用法: python portal_auth.py [学号] [密码] [运营商: lt/yd/dx]")
        print("或者在 config.json 中配置 username 与 password 后直接运行。")
        sys.exit(1)

    sys.exit(0 if login(user, passwd, op) else 1)


if __name__ == "__main__":
    main()
