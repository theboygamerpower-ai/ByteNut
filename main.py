import time
import os
import sys
import requests
import platform
from datetime import datetime

if "DISPLAY" not in os.environ:
    if platform.system().lower() == "linux":
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1920, 1080))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
        except:
            pass

from seleniumbase import SB

# ================= 配置区域 =================
PROXY = os.getenv("PROXY") or None
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
ACCOUNTS = os.getenv("BYTENUT", "")

URL_LOGIN_PANEL = "https://www.bytenut.com/auth/login"
URL_HOMEPAGE = "https://www.bytenut.com/homepage"
API_SERVER_LIST = "https://www.bytenut.com/game-panel/api/gpPanelServer/user/servers"
API_EXTENSION_INFO = "https://www.bytenut.com/game-panel/api/gp-free-server/extension-info/{}"
API_START_STATUS = "https://www.bytenut.com/game-panel/api/serverStartQueue/status/{}"

RENEW_MENU = '//li[contains(., "RENEW SERVER")]'
EXTEND_BTN = "button.extend-btn"
START_BTN = "button.start-btn"
START_VERIFY_DIALOG = "div.el-dialog"
MANAGEMENT_MENU = '//li[contains(@class,"el-sub-menu")]//span[text()="Management"]'
CONSOLE_MENU_ITEM = '//li[contains(@class,"el-menu-item")]//span[text()="Console"]'
PAGE_READY_INDICATOR = '//li[contains(@class,"el-menu-item")]'


def parse_accounts(raw: str):
    accounts = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or "-----" not in line:
            continue
        parts = line.split("-----", 1)
        if len(parts) == 2:
            accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts


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
            return bool(sb.execute_script("""
                var text = (document.body && document.body.innerText || '')
                    .toLowerCase();
                var selectors = [
                    'input[name*="otp" i]',
