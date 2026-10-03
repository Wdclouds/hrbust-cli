"""
HRBUST TUI Command Center 自动化冒烟测试
针对全新布局：居中大 ASCII Logo + 底部常驻命令条 + 右侧 1/4 学校动态侧边栏
"""

import sys
import asyncio
from pathlib import Path

# 将项目根目录注入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from hrbust.tui.app import HrbustTuiApp
from textual.widgets import Header, Footer, Input, Static, DataTable


async def run_smoke_test():
    print("[1/5] 初始化 HrbustTuiApp 实例...")
    app = HrbustTuiApp()

    print("[2/5] 进入 Textual 模拟驱动 (run_test)...")
    async with app.run_test(size=(140, 40)) as pilot:
        # 1. 验证基础框架组件
        header = app.query_one(Header)
        footer = app.query_one(Footer)
        main_deck = app.query_one("#main-deck")
        news_sidebar = app.query_one("#news-sidebar")
        cmd_input = app.query_one("#command-input", Input)

        assert header is not None, "Header 应该成功挂载"
        assert footer is not None, "Footer 应该成功挂载"
        assert main_deck is not None, "左侧主操作台应该成功挂载"
        assert news_sidebar is not None, "右侧 1/4 动态侧边栏应该成功挂载"
        assert cmd_input is not None, "底部常驻命令输入框应该成功挂载"
        print("  ✓ 核心骨架 (左侧 3/4 主甲板 + 右侧 1/4 公告侧边栏) 挂载正常")

        # 2. 验证中间首页区域与 ASCII Logo
        hero_view = app.query_one("#hero-view")
        logo_static = app.query_one(".ascii-logo", Static)
        assert hero_view is not None, "居中 Hero View 应该展示"
        assert "██╗" in str(logo_static.render()), "ASCII Logo 应该正常渲染"
        print("  ✓ 居中巨幅 ASCII Logo 与快捷指引面板渲染就绪")

        # 3. 模拟在底部命令输入条输入 "water"
        print("[3/5] 模拟底部命令输入条交互: 输入 'water'...")
        cmd_input.value = "water"
        await pilot.press("enter")
        await pilot.pause(0.2)

        # 验证工作区已切换至水控大盘表格
        water_table = app.query_one("#table-water-deck", DataTable)
        assert water_table is not None, "输入 water 后应展示水控大盘表格"
        assert app.active_view == "water"
        print("  ✓ 底部命令调度正常: 成功唤起水控大盘视图")

        # 4. 模拟按 Escape 返回居中 Logo 首页
        print("[4/5] 模拟按 'Escape' 键返回主页...")
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app.active_view == "hero"
        assert app.query_one("#hero-view") is not None
        print("  ✓ 一键 Esc 丝滑切回居中 Logo 首页")

        # 5. 模拟按 'q' 触发优雅退出
        print("[5/5] 模拟按 'q' 触发优雅退出...")
        await pilot.press("q")

    print("\n🎉 [PASS] HRBUST TUI 命令中枢全链路自动化冒烟测试 100% 成功通过！\n")


def test_tui_smoke():
    """Pytest 标准用例入口"""
    asyncio.run(run_smoke_test())


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
