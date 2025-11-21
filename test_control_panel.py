#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试控制面板是否能正常打开
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 导入必要的模块
from modules.constants import *
from modules.data_manager import *

def test_control_panel():
    """测试控制面板"""
    print("开始测试控制面板...")

    # 加载数据
    try:
        data = load_data()
        print("数据加载成功")
    except Exception as e:
        print(f"数据加载失败，使用默认数据: {e}")
        data = {
            "daily_tasks": {
                "2024-11-18": [
                    {"id": "task_1", "content": "测试任务", "priority": "high", "completed": False}
                ]
            }
        }

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    try:
        # 导入控制面板类
        from daily_reminder_qt61017 import ControlPanelDialog
        print("控制面板类导入成功")

        # 创建控制面板对话框
        dialog = ControlPanelDialog(None, data)
        print("控制面板对话框创建成功")

        # 显示对话框
        result = dialog.exec()
        print(f"控制面板测试完成，结果: {result}")

    except Exception as e:
        print(f"控制面板测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = test_control_panel()
    sys.exit(0 if success else 1)


