from setuptools import setup, find_packages
import sys

# 检查是否请求 Cython 编译
USE_CYTHON = "--cython" in sys.argv
if USE_CYTHON:
    sys.argv.remove("--cython")
    try:
        from Cython.Build import cythonize
        ext_modules = cythonize(
            [
                "hrbust/core/jwzx.py",
                "hrbust/core/water.py",
            ],
            compiler_directives={"language_level": "3"}
        )
    except ImportError:
        print("[警告] 未检测到 Cython 环境，将以纯 Python 源码模式打包。")
        ext_modules = []
else:
    ext_modules = []

setup(
    name="hrbust-cli",
    version="1.0.0",
    description="哈尔滨理工大学（HRBUST）数字化校园全栈开源 CLI 与 SDK 工具箱",
    packages=find_packages(),
    ext_modules=ext_modules,
    entry_points={
        "console_scripts": [
            "hrbust=hrbust.cli.main:run",
        ],
    },
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "ddddocr>=1.4.7",
        "pycryptodome>=3.18.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
    ],
)
