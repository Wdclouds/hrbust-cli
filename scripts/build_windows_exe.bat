@echo off
chcp 65001 > nul
title HRBUST Toolkit · Windows 单文件独立 EXE 编译流水线
echo ===============================================================================
echo   HRBUST Toolkit (哈理工数字化校园) Windows 独立绿色版 EXE 打包流水线
echo ===============================================================================
echo.

set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"

echo [1/4] 检查 Python 与编译依赖环境...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未在系统 PATH 中检测到 Python，请先安装 Python 3.9+ 并勾选 Add to PATH。
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>nul
python -m pip install pyinstaller textual rich typer requests beautifulsoup4 pillow pycryptodome ddddocr >nul 2>nul

echo [2/4] 清理旧的编译缓存与产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] 正在使用 PyInstaller 编译单文件绿色独立可执行程序 (hrbust.exe)...
pyinstaller --noconfirm --onedir --console ^
    --name "hrbust" ^
    --add-data "hrbust/tui/styles.tcss;hrbust/tui" ^
    --hidden-import "rich" ^
    --hidden-import "typer" ^
    --hidden-import "textual" ^
    --hidden-import "textual.widgets" ^
    --hidden-import "Crypto" ^
    --hidden-import "Crypto.Cipher.AES" ^
    --hidden-import "PIL" ^
    --hidden-import "ddddocr" ^
    --hidden-import "bs4" ^
    hrbust/cli/main.py

if %errorlevel% neq 0 (
    echo [错误] 编译构建失败，请检查上方日志。
    pause
    exit /b 1
)

echo.
echo ===============================================================================
echo   🎉 编译完成！绿色可执行程序已输出至: dist\hrbust\hrbust.exe
echo   可以将该程序直接分发给哈理工同学/室友，无需安装任何环境即可双击或终端运行！
echo ===============================================================================
echo.
pause
