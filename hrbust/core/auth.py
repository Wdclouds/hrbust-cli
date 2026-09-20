"""
HRBUST Toolkit 凭证安全管理模块
采用双轨存储架构：
1. 主轨: 系统底层 Keyring (Windows Credential Manager / macOS Keychain / Linux SecretService)
2. 备轨: 机器特征绑定的 AES-256-GCM 密文保险箱 (无头 / WSL / 容器环境，绝不存明文)
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

SERVICE_NAME = "hrbust-cli"
CONFIG_DIR = Path.home() / ".hrbust"
VAULT_FILE = CONFIG_DIR / "vault.bin"

def _get_machine_key() -> bytes:
    try:
        user = os.getlogin()
    except Exception:
        user = "root"
    node = os.uname().nodename
    seed = f"{node}-{user}-hrbust-safe-salt"
    return hashlib.sha256(seed.encode("utf-8")).digest()

def _vault_encrypt(plain_text: str) -> str:
    from Crypto.Cipher import AES
    key = _get_machine_key()
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plain_text.encode("utf-8"))
    payload = cipher.nonce + tag + ciphertext
    return base64.b64encode(payload).decode("utf-8")

def _vault_decrypt(b64_cipher: str) -> Optional[str]:
    from Crypto.Cipher import AES
    try:
        raw = base64.b64decode(b64_cipher.encode("utf-8"))
        nonce = raw[:16]
        tag = raw[16:32]
        ciphertext = raw[32:]
        cipher = AES.new(_get_machine_key(), AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
    except Exception:
        return None

def set_password(key: str, val: str) -> bool:
    try:
        import keyring
        keyring.set_password(SERVICE_NAME, key, val)
        return True
    except Exception:
        pass
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if VAULT_FILE.exists():
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                dec = _vault_decrypt(f.read().strip())
                if dec:
                    data = json.loads(dec)
        except Exception:
            data = {}
    data[key] = val
    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        f.write(_vault_encrypt(json.dumps(data)))
    try:
        os.chmod(VAULT_FILE, 0o600)
    except Exception:
        pass
    return True

def get_password(key: str) -> Optional[str]:
    try:
        import keyring
        val = keyring.get_password(SERVICE_NAME, key)
        if val:
            return val
    except Exception:
        pass
    if VAULT_FILE.exists():
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                dec = _vault_decrypt(f.read().strip())
                if dec:
                    data = json.loads(dec)
                    return data.get(key)
        except Exception:
            return None
    return None

def delete_password(key: str) -> bool:
    try:
        import keyring
        keyring.delete_password(SERVICE_NAME, key)
    except Exception:
        pass
    if VAULT_FILE.exists():
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                dec = _vault_decrypt(f.read().strip())
                if dec:
                    data = json.loads(dec)
                    if key in data:
                        del data[key]
                        with open(VAULT_FILE, "w", encoding="utf-8") as fw:
                            fw.write(_vault_encrypt(json.dumps(data)))
        except Exception:
            pass
    return True

def get_credentials() -> Tuple[Optional[str], Optional[str]]:
    return get_password("username"), get_password("password")

def set_credentials(u: str, p: str):
    set_password("username", u)
    set_password("password", p)

def get_water_token() -> Tuple[Optional[str], Optional[str]]:
    return get_password("water_raw_info"), get_password("water_token")

def set_water_token(raw_info: str, token: str):
    set_password("water_raw_info", raw_info)
    set_password("water_token", token)

def clear_all_credentials():
    delete_password("username")
    delete_password("password")
    delete_password("water_raw_info")
    delete_password("water_token")
    if VAULT_FILE.exists():
        try:
            VAULT_FILE.unlink()
        except Exception:
            pass

def load_config() -> Dict[str, Any]:
    u, p = get_credentials()
    w_info, w_tok = get_water_token()
    return {
        "username": u or "",
        "password": p or "",
        "water_raw_info": w_info or "",
        "water_token": w_tok or ""
    }

def save_config(cfg: Dict[str, Any]):
    if "username" in cfg and "password" in cfg:
        set_credentials(cfg["username"], cfg["password"])
    if "water_raw_info" in cfg and "water_token" in cfg:
        set_water_token(cfg["water_raw_info"], cfg["water_token"])
