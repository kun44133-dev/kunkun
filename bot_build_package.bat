@echo off
REM ============================================
REM  自动化打包脚本 (Windows .bat)
REM  执行方式：双击或在命令行运行该批处理文件
REM ============================================

SETLOCAL EnableDelayedExpansion

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" >nul 2>&1
IF ERRORLEVEL 1 (
    ECHO 未检测到 PyInstaller，请先执行：pip install pyinstaller
    EXIT /b 1
)

REM 清理旧的构建产物
IF EXIST build (
    ECHO 正在删除旧的 build 目录...
    rmdir /s /q build
)
IF EXIST dist (
    ECHO 正在删除旧的 dist 目录...
    rmdir /s /q dist
)
IF EXIST daily_reminder_qt61017.spec (
    ECHO 删除旧的 spec 文件...
    del /f /q daily_reminder_qt61017.spec
)

REM 构造基本命令 (打包成单个 exe)
SET CMD=python -m PyInstaller --noconfirm --noconsole --clean --onefile --name DailyReminderBot
REM 项目内的 Python 包会被自动分析打入，无需额外 add-data

REM 附加图标文件
IF EXIST "app_icon.ico" (
    SET CMD=%CMD% --icon "app_icon.ico" --add-data "app_icon.ico;."
)
IF EXIST "tray_icon.ico" (
    SET CMD=%CMD% --add-data "tray_icon.ico;."
)

REM 常见隐藏依赖（按需添加）
FOR %%M IN (
    "PyQt6.QtCore"
    "PyQt6.QtGui"
    "PyQt6.QtWidgets"
    "chinese_calendar"
    "lunardate"
    "requests"
    "openpyxl"
    "dateutil"
    "qrcode"
    "PIL"
) DO (
    python -c "import importlib.util as u; exit(0 if u.find_spec('%%~M') else 1)" >nul 2>&1
    IF NOT ERRORLEVEL 1 (
        SET CMD=%CMD% --hidden-import "%%~M"
    )
)

REM Windows 专属模块
python -c "import importlib.util as u; exit(0 if u.find_spec('winreg') else 1)" >nul 2>&1
IF NOT ERRORLEVEL 1 (
    SET CMD=%CMD% --hidden-import "winreg"
)

SET CMD=%CMD% daily_reminder_qt61017.py

ECHO 执行命令：
ECHO !CMD!

REM 运行打包命令
CALL !CMD!
IF ERRORLEVEL 1 (
    ECHO 打包失败。
    EXIT /b 1
)

ECHO 打包完成，可执行文件位于 dist\DailyReminderBot 目录。
ENDLOCAL
EXIT /b 0

