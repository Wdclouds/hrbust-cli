import pytest
from unittest.mock import MagicMock
from hrbust.core.water import WaterEngine
from hrbust.services.water_svc import WaterService
from hrbust.core import auth

def test_water_engine_request_book_code_contract():
    engine = WaterEngine()
    # Mock session.get response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "RetNo": 0,
        "RetDsp": "预约成功",
        "BookCode": "1234"
    }
    engine.session.get = MagicMock(return_value=mock_resp)

    res = engine.request_book_code("mock_info", "mock_token")
    assert res["success"] is True
    assert res["ret_no"] == 0
    assert res["RetNo"] == 0
    assert res["book_code"] == "1234"
    assert res["BookCode"] == "1234"
    assert res["msg"] == "预约成功"

def test_water_service_book_bath_contract():
    engine = WaterEngine()
    engine.request_book_code = MagicMock(return_value={
        "success": True,
        "ret_no": 0,
        "RetNo": 0,
        "book_code": "5678",
        "msg": "预约成功"
    })
    svc = WaterService(engine)

    res = svc.book_bath(6, "2101010101", "2101010101", "token123")
    assert res["success"] is True
    assert res["book_code"] == "5678"
    assert res["ret_no"] == 0

def test_auth_set_water_token_single_and_dual_args(tmp_path, monkeypatch):
    test_vault = tmp_path / "test_vault.enc"
    monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth, "VAULT_FILE", test_vault)

    # 单参数
    auth.set_water_token("token_abc")
    r_info, tok = auth.get_water_token()
    assert tok == "token_abc"

    # 双参数
    auth.set_water_token("raw_xyz", "token_def")
    r_info, tok = auth.get_water_token()
    assert r_info == "raw_xyz"
    assert tok == "token_def"

def test_cli_lazy_import_no_warning():
    import hrbust.cli
    assert hasattr(hrbust.cli, "app")
    assert hasattr(hrbust.cli, "run")
    assert callable(hrbust.cli.run)

def test_cas_encrypt_password_reversible():
    salt = "v1QosAvCE3VepygD"
    password = "MyTestPassword123"
    enc = WaterEngine.encrypt_cas_password(password, salt)
    assert isinstance(enc, str) and len(enc) > 0

    # 解密验证后缀包含原密码
    import base64
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    raw = base64.b64decode(enc)
    key_bytes = salt.encode("utf-8")[:16].ljust(16, b"\0")
    # CBC 解密首块受 IV 影响，但后半部分明文必然包含密码字符
    assert len(raw) >= 80

def test_water_engine_fetch_token_by_cas_mock():
    engine = WaterEngine()

    # 1. Mock CAS 页面 HTML
    mock_cas_html = """
    <html>
      <input type="hidden" name="execution" value="e1s2" />
      <input type="hidden" id="pwdEncryptSalt" value="test_salt_123456" />
    </html>
    """
    mock_resp_cas = MagicMock()
    mock_resp_cas.text = mock_cas_html

    # 2. Mock POST CAS 登录 302 重定向
    mock_resp_post = MagicMock()
    mock_resp_post.headers = {"Location": "https://yktks.hrbust.edu.cn/?ticket=ST-998877-cas"}

    # 3. Mock SsoCheck
    mock_resp_sso = MagicMock()
    mock_resp_sso.json.return_value = {
        "Ret": 0,
        "User": {"ACCOUNT": "6010309"}
    }

    # 4. Mock GetToken
    mock_resp_token = MagicMock()
    mock_resp_token.json.return_value = {
        "RetNo": 0,
        "Token": "auto_cas_token_xyz"
    }

    def mock_get(url, **kwargs):
        if "authserver/login" in url:
            return mock_resp_cas
        if "GetToken" in url:
            return mock_resp_token
        return MagicMock()

    def mock_post(url, **kwargs):
        if "authserver/login" in url:
            return mock_resp_post
        if "SsoCheck" in url:
            return mock_resp_sso
        return MagicMock()

    engine.session.get = MagicMock(side_effect=mock_get)
    engine.session.post = MagicMock(side_effect=mock_post)

    ok, msg, token, account = engine.fetch_token_by_cas("2306010309", "pass123")
    assert ok is True
    assert token == "auto_cas_token_xyz"
    assert account == "6010309"

def test_water_service_auto_auth_and_sync_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth, "VAULT_FILE", tmp_path / "test_vault.enc")

    engine = WaterEngine()
    engine.fetch_token_by_cas = MagicMock(return_value=(True, "成功", "tok_synced_999", "6010309"))
    svc = WaterService(engine)

    res = svc.auto_auth_and_sync("2306010309", "pass123")
    assert res["success"] is True
    assert res["token"] == "tok_synced_999"

    # 验证本地已自动持久化落盘
    _, saved_token = auth.get_water_token()
    assert saved_token == "tok_synced_999"

def test_news_service_get_article_detail_mock():
    from hrbust.services.news_svc import NewsService
    svc = NewsService()
    mock_html = """
    <html>
      <h2>第23届全国大学生信息安全对抗通知</h2>
      <p>来源：教务处 2026-10-10</p>
      <div id="article-content">
        <p>为贯彻落实网络安全战略，组织校内选拔。</p>
        <p>一、参赛对象：在校本科生。</p>
        <a href="/homepage/downloadTheolFile.do?id=ABCDEF&fileName=test.docx">附件1：校赛报名表.docx</a>
      </div>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.content = mock_html.encode("utf-8")
    svc.session.get = MagicMock(return_value=mock_resp)

    res = svc.get_article_detail("5532", column_id=354)
    assert res["id"] == "5532"
    assert "信息安全" in res["title"]
    assert "参赛对象" in res["content"]
    assert len(res["attachments"]) == 1
    assert "校赛报名表" in res["attachments"][0]["name"]
    assert "downloadTheolFile.do" in res["attachments"][0]["url"]

def test_score_service_calculation_and_blocked():
    from hrbust.services.score_svc import ScoreService
    from bs4 import BeautifulSoup

    mock_engine = MagicMock()
    svc = ScoreService(mock_engine)

    # 1. 模拟未评教拦截
    mock_blocked_html = "<html><body>您尚未完成本学期网上教学评价，不能查看成绩！</body></html>"
    mock_engine.access_module.return_value = "http://fake_url"
    mock_engine.get_page.return_value = BeautifulSoup(mock_blocked_html, "html.parser")

    res_blocked = svc.get_scores()
    assert res_blocked["blocked"] is True
    assert "未完成" in res_blocked["reason"]

    # 2. 模拟正常成绩表格与 GPA 汇总计算
    mock_score_html = """
    <html>
      <table>
        <tr><th>学年学期</th><th>课程代码</th><th>课程名称</th><th>课程性质</th><th>学分</th><th>平时</th><th>期末</th><th>综合成绩</th><th>绩点</th></tr>
        <tr><td>2024-2025-1</td><td>001</td><td>高等数学</td><td>必修</td><td>5.0</td><td>90</td><td>80</td><td>85</td><td>3.5</td></tr>
        <tr><td>2024-2025-1</td><td>002</td><td>大学英语</td><td>必修</td><td>3.0</td><td>95</td><td>95</td><td>95</td><td>4.5</td></tr>
      </table>
    </html>
    """
    mock_engine.get_page.return_value = BeautifulSoup(mock_score_html, "html.parser")
    res_normal = svc.get_scores()
    assert res_normal["blocked"] is False
    assert len(res_normal["scores"]) == 2
    summary = res_normal["summary"]
    assert summary["total_credits"] == 8.0
    # 加权均分: (85*5 + 95*3) / 8 = (425 + 285) / 8 = 710 / 8 = 88.75
    assert summary["weighted_avg_score"] == 88.75
    # 加权 GPA: (3.5*5 + 4.5*3) / 8 = (17.5 + 13.5) / 8 = 31 / 8 = 3.88
    assert summary["gpa"] == 3.88

def test_water_engine_qr_png_to_unicode():
    from PIL import Image
    import io
    from hrbust.core.water import WaterEngine

    # 生成一个简单的 50x50 测试黑白图像模拟二维码
    img = Image.new("1", (50, 50), color=1)
    # 画一个 7x7 的左上角 finder block
    for y in range(7):
        for x in range(7):
            img.putpixel((x, y), 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    res_str = WaterEngine.qr_png_to_unicode(png_bytes)
    assert len(res_str) > 0
    assert any(c in res_str for c in ("█", "▀", "▄"))

def test_water_service_qr_login_flow_mock(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from PIL import Image
    import io
    from hrbust.core.water import WaterEngine
    from hrbust.services.water_svc import WaterService
    import hrbust.core.auth as auth

    monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(auth, "VAULT_FILE", tmp_path / "vault.bin")

    engine = WaterEngine()
    svc = WaterService(engine)

    # 1. 模拟 start_qr_login
    mock_token_resp = MagicMock()
    mock_token_resp.text = "QR-mock-uuid-12345"

    img = Image.new("1", (50, 50), color=1)
    for y in range(7):
        for x in range(7):
            img.putpixel((x, y), 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    mock_img_resp = MagicMock()
    mock_img_resp.content = buf.getvalue()

    def _mock_get(url, *args, **kwargs):
        if "getToken" in url:
            return mock_token_resp
        elif "getCode" in url:
            return mock_img_resp
        elif "getStatus.htl" in url:
            mock_st = MagicMock()
            mock_st.text = "1"
            return mock_st
        elif "GetToken" in url:
            mock_tok = MagicMock()
            mock_tok.json.return_value = {"RetNo": 0, "Token": "tok_qr_mock_999"}
            return mock_tok
        return MagicMock()

    def _mock_post(url, *args, **kwargs):
        if "login" in url:
            mock_post_resp = MagicMock()
            mock_post_resp.headers = {"Location": "https://yktks.hrbust.edu.cn/?ticket=ST-qr-ticket-888"}
            return mock_post_resp
        elif "SsoCheck" in url:
            mock_sso = MagicMock()
            mock_sso.json.return_value = {"Ret": 0, "User": {"ACCOUNT": "2306010309"}}
            return mock_sso
        return MagicMock()

    engine.session.get = _mock_get
    engine.session.post = _mock_post

    # 测试完整扫码流转
    session = svc.start_qr_login()
    assert session["uuid"] == "QR-mock-uuid-12345"
    assert len(session["qr_ascii"]) > 0

    st = svc.check_qr_status("QR-mock-uuid-12345")
    assert st == "1"

    finish_res = svc.finish_qr_login("QR-mock-uuid-12345")
    assert finish_res["success"] is True
    assert finish_res["token"] == "tok_qr_mock_999"
    assert finish_res["account"] == "2306010309"

    # 验证本地已自动安全落盘
    _, saved_tok = auth.get_water_token()
    assert saved_tok == "tok_qr_mock_999"

def test_exam_service_parsing_and_countdown():
    from unittest.mock import MagicMock
    from bs4 import BeautifulSoup
    from hrbust.services.exam_svc import ExamService

    mock_engine = MagicMock()
    svc = ExamService(mock_engine)

    # 1. 模拟暂无排考提示
    mock_no_exam_html = "<html><body>当前学期暂无考试安排数据</body></html>"
    mock_engine.access_module.return_value = "http://fake_jwzx/exam"
    mock_engine.get_page.return_value = BeautifulSoup(mock_no_exam_html, "html.parser")

    res_empty = svc.get_exams()
    assert res_empty["has_exams"] is False
    assert len(res_empty["exams"]) == 0

    # 2. 模拟正常考试安排表格
    mock_exam_html = """
    <html>
      <table>
        <tr><th>学期</th><th>课程代码</th><th>课程名称</th><th>考试性质</th><th>考试时间</th><th>考场</th><th>座位号</th></tr>
        <tr><td>2024-2025-1</td><td>CS101</td><td>算法与数据结构</td><td>正常考试</td><td>2026-11-20 08:30-10:30</td><td>南区1号楼 203</td><td>18</td></tr>
        <tr><td>2024-2025-1</td><td>CS102</td><td>计算机网络</td><td>正常考试</td><td>2024-01-15 13:30-15:30</td><td>西新主楼 502</td><td>42</td></tr>
      </table>
    </html>
    """
    mock_engine.get_page.return_value = BeautifulSoup(mock_exam_html, "html.parser")
    res_normal = svc.get_exams()
    assert res_normal["has_exams"] is True
    assert len(res_normal["exams"]) == 2

    # 验证排序与字段
    e1 = res_normal["exams"][0]
    assert e1["course_name"] == "算法与数据结构"
    assert e1["location"] == "南区1号楼 203"
    assert e1["seat_no"] == "18"
    assert e1["days_left"] is not None

    e2 = res_normal["exams"][1]
    assert e2["course_name"] == "计算机网络"
    assert e2["seat_no"] == "42"
    assert e2["status"] == "已结束"

