#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自检测试套件：在本地模拟网关响应，验证核心认证与重试逻辑"""

import json, unittest
from unittest.mock import MagicMock, patch
import portal_auth


class TestCorePortalAuth(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_is_online_via_api(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"code": 1, "data": {"userId": "20240001@lt"}}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        self.assertTrue(portal_auth.is_online())

    @patch("portal_auth.is_online", return_value=True)
    def test_login_skips_when_online(self, _):
        self.assertTrue(portal_auth.login("20240001", "dummy_pass", "lt"))

    @patch("portal_auth.is_online", return_value=False)
    @patch("urllib.request.urlopen")
    def test_login_success(self, mock_urlopen, _):
        # 依次返回 PortalJsonAction.do 和 quickauth.do 模拟响应
        r_session = MagicMock()
        r_session.read.return_value = json.dumps({"portalconfig": {"id": 46, "uuid": "u1", "timestamp": 123}}).encode()

        r_auth = MagicMock()
        r_auth.read.return_value = json.dumps({"code": "0", "message": "success"}).encode()

        mock_urlopen.return_value.__enter__.side_effect = [r_session, r_auth]
        self.assertTrue(portal_auth.login("20240001", "correct_pwd", "lt", retries=1))

    @patch("portal_auth.is_online", return_value=False)
    @patch("portal_auth.kick_device", return_value=True)
    @patch("urllib.request.urlopen")
    def test_login_limit_and_kick(self, mock_urlopen, mock_kick, _):
        r_session = MagicMock()
        r_session.read.return_value = b"{}"

        r_limit = MagicMock()
        r_limit.read.return_value = json.dumps({"code": "1", "message": "认证失败,原因:21"}).encode()

        r_ok = MagicMock()
        r_ok.read.return_value = json.dumps({"code": "0", "message": "success"}).encode()

        mock_urlopen.return_value.__enter__.side_effect = [r_session, r_limit, r_ok]
        self.assertTrue(portal_auth.login("20240001", "my_pwd", "lt", retries=2))
        mock_kick.assert_called_once()


if __name__ == "__main__":
    unittest.main()
