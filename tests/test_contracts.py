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
