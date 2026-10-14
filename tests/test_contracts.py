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
