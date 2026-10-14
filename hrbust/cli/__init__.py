"""
HRBUST Toolkit CLI 模块导出
"""

def __getattr__(name: str):
    if name in ("app", "run"):
        from .main import app, run
        return app if name == "app" else run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["app", "run"]
