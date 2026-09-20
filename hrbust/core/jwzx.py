"""
HRBUST Toolkit 教务在线系统底层引擎
封装验证码抓取、自动打码校验、账号密码登录与动态模块安全路由
"""

import time
from bs4 import BeautifulSoup
import ddddocr
from .network import CampusSession

class JwzxEngine:
    """教务在线系统底层交互客户端"""
    BASE_URL = "http://jwzx.hrbust.edu.cn"

    def __init__(self):
        self.session = CampusSession()
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.logged_in = False
        self.username = None

    def get_captcha(self) -> bytes:
        """获取验证码原始图片字节流"""
        url = f"{self.BASE_URL}/academic/getCaptcha.do"
        res = self.session.get(url, timeout=5)
        return res.content

    def check_captcha(self, code: str) -> bool:
        """服务端预校验验证码是否正确"""
        url = f"{self.BASE_URL}/academic/checkCaptcha.do"
        res = self.session.post(url, data={"captchaCode": code}, timeout=5)
        return res.text.strip().lower() == "true"

    def login(self, username: str, password: str, max_retries: int = 10) -> bool:
        """登录教务系统（带本地 OCR 与自动打码重试）"""
        self.username = username
        login_url = f"{self.BASE_URL}/academic/j_acegi_security_check"

        for attempt in range(max_retries):
            img_bytes = self.get_captcha()
            code = self.ocr.classification(img_bytes).strip()

            if len(code) != 4 or not self.check_captcha(code):
                time.sleep(0.3)
                continue

            data = {
                "j_username": username,
                "j_password": password,
                "j_captcha": code
            }
            res = self.session.post(login_url, data=data, timeout=8)
            text = res.content.decode("gbk", errors="ignore")

            # 校验是否重定向或命中欢迎主页
            if "index_new.jsp" in res.url or "欢迎" in text or "您好" in text:
                self.logged_in = True
                return True

            if "密码错误" in text or "用户不存在" in text:
                return False

            time.sleep(0.5)

        return False

    def access_module(self, module_id: int) -> str:
        """
        通过教务系统的动态安全分发接口 (accessModule.do) 换取物理访问 URL
        直接访问物理 URL 会被安全机制拦截，必须经过本方法中转
        """
        url = f"{self.BASE_URL}/academic/accessModule.do?moduleId={module_id}&groupId="
        res = self.session.get(url, allow_redirects=True, timeout=8)
        return res.url

    def get_page(self, url: str, params: dict = None) -> BeautifulSoup:
        """拉取页面并解析为 BeautifulSoup (自动 GBK 容错解码)"""
        res = self.session.get(url, params=params, timeout=8)
        text = res.content.decode("gbk", errors="ignore")
        return BeautifulSoup(text, "html.parser")
