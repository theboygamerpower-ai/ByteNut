

class BytenutRenewal:

    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        self.had_failure = False
        self.failures = []
        os.makedirs(self.screenshot_dir, exist_ok=True)

    # ========== 脱敏工具 ==========
    def mask_account(self, u):
        if not u:
            return "Unknown"
        u = u.strip()
        if "@" in u:
            local, domain = u.split("@", 1)
            masked_local = (
                local[:2] + "*" * (len(local) - 2)
                if len(local) > 2
                else local[0] + "*"
            )
            return f"{masked_local}@{domain}"
        return u[:2] + "*" * (len(u) - 2) if len(u) > 2 else u[0] + "*"

    def mask_server_id(self, sid):
        return "[server]"

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] [INFO] {msg}", flush=True)

    def shot(self, sb, name):
        path = os.path.join(self.screenshot_dir, name)
        sb.save_screenshot(path)
        return path

    def mark_failed(self, reason):
        self.had_failure = True
        self.failures.append(reason)
        self.log(f"WORKFLOW_FAILURE: {reason}")

    def manual_verification_present(self, sb):
        """Detect OTP/email-code screens without trying to bypass them."""
        try:
            script = (
                "var text = (document.body && document.body.innerText || '').toLowerCase();"
                "var selectors = ["
                "'input[name*=otp i]',"
                "'input[id*=otp i]',"
                "'input[placeholder*=otp i]',"
                "'input[name*=code i]',"
                "'input[id*=code i]',"
                "'input[placeholder*=code i]',"
                "'input[placeholder*=email i]'"
                "];"
                "var hasInput = selectors.some(function(sel) {"
                "  try { return !!document.querySelector(sel); }"
                "  catch (e) { return false; }"
                "});"
                "return hasInput"
                " || text.indexOf('otp') !== -1"
                " || text.indexOf('verification code') !== -1"
                " || text.indexOf('email code') !== -1"
                " || text.indexOf('sent to your email') !== -1;"
            )
            return bool(sb.execute_script(script))
        except Exception:
            return False

    # ========== TG 通知 ==========
    def send_tg(self, icon, title, account_name, server_id,
                state_str, expiry_str, extra="", screenshot=None):
        if icon not in ("\u2705", "\u23f3"):
            self.mark_failed(f"{title}: {server_id} {state_str} {extra}".strip())
        if not TG_TOKEN or not TG_CHAT_ID:
            return
        msg = (
            f"{icon} {title}\n\n"
            f"账号: {account_name}\n"
            f"服务器: {server_id}\n"
            f"状态: {state_str}\n"
            f"到期时间: {expiry_str}\n"
        )
        if extra:
            msg += f"\n{extra}\n"
        msg += "\nByteNut Auto Renew"
        try:
            if screenshot and os.path.exists(screenshot):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(screenshot, "rb") as f:
                    requests.post(
                        url,
                        data={"chat_id": TG_CHAT_ID, "caption": msg},
                        files={"photo": f},
                    )
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg})
        except Exception as e:
            self.log(f"TG发送失败: {e}")

    # ========== 浏览器内 fetch（变量嵌入脚本）==========
    def fetch_api(self, sb, url, method="GET", referer=None):
        """
        在浏览器上下文执行 fetch，变量直接嵌入脚本字符串。
        返回解析后的 data，失败返回 None。
        """
        if referer is None:
            referer = URL_HOMEPAGE

        # 用 json.dumps 确保字符串正确转义
        import json
        url_js = json.dumps(url)
        method_js = json.dumps(method)
        referer_js = json.dumps(referer)

        script = f"""
        var callback = arguments[0];
        var token = localStorage.getItem('yl-token')
                 || sessionStorage.getItem('yl-token') || '';
        var headers = {{
            'Accept': 'application/json, text/plain, */*',
            'Referer': {referer_js}
        }};
        if (token) {{ headers['Yl-Token'] = token; }}
        fetch({url_js}, {{
            method: {method_js},
            headers: headers,
            credentials: 'include'
        }})
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{ callback({{ok: true, data: data}}); }})
        .catch(function(e) {{ callback({{ok: false, error: e.toString()}}); }});
        """
        try:
            result = sb.execute_async_script(script)
            if result and result.get("ok"):
                resp = result["data"]
                if resp.get("code") == 200:
                    return resp.get("data")
                self.log(f"API 业务错误: {resp.get('message')}")
            else:
                err = result.get("error") if result else "None"
                self.log(f"fetch 失败: {err}")
        except Exception as e:
            self.log(f"fetch_api 异常: {e}")
        return None

    def fetch_api_post(self, sb, url, referer=None):
        """POST 版本"""
        if referer is None:
            referer = URL_HOMEPAGE

        import json
        url_js = json.dumps(url)
        referer_js = json.dumps(referer)

        script = f"""
        var callback = arguments[0];
        var token = localStorage.getItem('yl-token')
                 || sessionStorage.getItem('yl-token') || '';
        var headers = {{
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': {referer_js}
        }};
        if (token) {{ headers['Yl-Token'] = token; }}
        fetch({url_js}, {{
            method: 'POST',
            headers: headers,
            credentials: 'include'
        }})
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{ callback({{ok: true, data: data}}); }})
        .catch(function(e) {{ callback({{ok: false, error: e.toString()}}); }});
        """
        try:
            result = sb.execute_async_script(script)
            if result and result.get("ok"):
                resp = result["data"]
                if resp.get("code") == 200:
                    return resp.get("data")
                self.log(f"API 业务错误: {resp.get('message')}")
            else:
                err = result.get("error") if result else "None"
                self.log(f"fetch POST 失败: {err}")
        except Exception as e:
            self.log(f"fetch_api_post 异常: {e}")
        return None

    # ========== API 封装 ==========
    def get_servers_data(self, sb):
        return self.fetch_api(sb, API_SERVER_LIST, referer=URL_HOMEPAGE)

    def get_extension_data(self, sb, server_id):
        ref = f"https://www.bytenut.com/free-gamepanel/{server_id}"
        return self.fetch_api(sb, API_EXTENSION_INFO.format(server_id),
                              referer=ref)

    def get_start_status(self, sb, server_id):
        ref = f"https://www.bytenut.com/free-gamepanel/{server_id}"
        return self.fetch_api(sb, API_START_STATUS.format(server_id),
                              referer=ref)

    # ========== 等待页面就绪 ==========
    def wait_for_panel_ready(self, sb, server_id, timeout=30):
        self.log("⏳ 等待页面加载...")
        try:
            sb.wait_for_element_present(PAGE_READY_INDICATOR, timeout=timeout)
        except Exception:
            self.log("⚠️ 侧边栏未出现，继续...")

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if sb.is_element_present(RENEW_MENU):
                    self.log("✅ 页面就绪（RENEW SERVER 可见）")
                    return True
            except Exception:
                pass
            self.remove_overlay_ads(sb)
            time.sleep(1)
        self.log("⚠️ RENEW SERVER 等待超时")
        return False

    # ========== 轮询开机队列 ==========
    def poll_start_status(self, sb, server_id, timeout=300, interval=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.get_start_status(sb, server_id)
            if data:
                in_queue = data.get("inQueue", True)
                can_start = data.get("canStart", False)
                pos = data.get("queuePosition", 0)
                wait_sec = data.get("estimatedWaitSeconds")
                msg = data.get("statusMessage", "")
                self.log(f"  队列: inQueue={in_queue}, pos={pos}, "
                         f"wait={wait_sec}s, msg={msg}")
                if not in_queue and can_start:
                    self.log("✅ 服务器启动成功（队列完成）")
                    return True, "running"
            time.sleep(interval)
        return False, "timeout"

    def wait_until_running(self, sb, server_id, timeout=120, interval=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            servers = self.get_servers_data(sb)
            if servers:
