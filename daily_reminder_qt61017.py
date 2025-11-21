# daily_reminder_qt6.py
# -*- coding: utf-8 -*-
"""
昱景每日工作提醒 - PyQt6版本
"""

import sys
import os
import logging
import datetime
import glob
import copy
import shutil
import uuid

# 节日模块导入
try:
    import chinese_calendar
    HOLIDAY_MODULE_AVAILABLE = True
except ImportError:
    HOLIDAY_MODULE_AVAILABLE = False
    print("提示：未安装 chinese-calendar 模块，节日功能将使用内置数据")
    print("安装命令：pip install chinese-calendar")

# lunardate 模块导入（农历库）
try:
    import lunardate
    LUNARDATE_MODULE_AVAILABLE = True
except ImportError:
    LUNARDATE_MODULE_AVAILABLE = False
    print("提示：未安装 lunardate 模块，农历功能将使用默认值")
    print("安装命令：pip install lunardate")

# qrcode 模块导入（二维码库）
try:
    import qrcode
    from PIL import Image
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("提示：未安装 qrcode 和 Pillow 模块，二维码功能将不可用")
    print("安装命令：pip install qrcode[pil] Pillow")

# 网络请求模块导入
try:
    import requests
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False
    print("提示：未安装 requests 模块，农历功能将使用内置数据")
    print("安装命令：pip install requests")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QScrollArea, QMessageBox, QDialog,
    QLineEdit, QCheckBox, QComboBox, QSpinBox, QDateEdit,
    QFileDialog, QSystemTrayIcon, QMenu, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QStyle,
    QToolButton, QSplitter, QGroupBox, QFormLayout, QGridLayout,
    QRadioButton, QButtonGroup, QSlider, QTimeEdit,
    QGraphicsDropShadowEffect, QSizePolicy, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import (
    Qt, QTimer, QTime, QDate, pyqtSignal, QThread, QSize,
    QPropertyAnimation, QEasingCurve, QRect, QSettings, QPoint
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QFontMetrics,
    QLinearGradient, QBrush, QPen, QAction, QGuiApplication, QPageSize, QPageLayout,
    QImage
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

from modules.constants import (
    BUILTIN_HOLIDAYS,
    MAX_AGE,
    MAX_DISPLAY_ORDERS,
    OVERDUE_NOTIFICATION_INTERVAL,
)
from modules.data_manager import (
    HOME,
    LOG_FILE,
    SAVE_DIR,
    load_data,
    save_data,
    set_storage_path,
)

# 可选依赖项处理
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    openpyxl = None
    EXCEL_AVAILABLE = False

try:
    from dateutil.parser import parse as date_parse
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

# requests 模块已在上面导入，这里不需要重复导入
REQUESTS_AVAILABLE = NETWORK_AVAILABLE

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

# -------------------- 全局配置 --------------------

# 订单状态常量
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_MAKING = "making"
ORDER_STATUS_DONE = "done"
ORDER_STATUS_PAUSED = "paused"

ORDER_STATUS_DISPLAY = {
    ORDER_STATUS_PENDING: "⏳ 未完成",
    ORDER_STATUS_MAKING: "🔨 制作中",
    ORDER_STATUS_DONE: "✅ 完成",
    ORDER_STATUS_PAUSED: "⏸️ 暂停"
}

ORDER_STATUS_CYCLE = [ORDER_STATUS_PENDING, ORDER_STATUS_MAKING, ORDER_STATUS_DONE, ORDER_STATUS_PAUSED]

# 设置日志
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

def today_str():
    """获取今天的字符串"""
    return datetime.date.today().isoformat()

def get_day_night_icon():
    """根据当前时间返回白天或晚上的图标"""
    current_hour = datetime.datetime.now().hour
    # 6:00-18:00 为白天，显示太阳图标
    if 6 <= current_hour < 18:
        return "☀️"  # 太阳图标
    else:
        return "🌙"  # 月亮图标

def get_lunar_date(date_obj=None):
    """获取农历日期"""
    if date_obj is None:
        date_obj = datetime.date.today()
    
    # 使用 lunardate 模块获取农历日期
    if LUNARDATE_MODULE_AVAILABLE:
        try:
            lunar = lunardate.LunarDate.fromSolarDate(date_obj.year, date_obj.month, date_obj.day)
            return {
                "lunar_str": f"农历{lunar.month}月{lunar.day}日",
                "lunar_year": lunar.year,
                "lunar_month": lunar.month,
                "lunar_day": lunar.day,
                "lunar_month_name": f"{lunar.month}月",
                "lunar_day_name": f"{lunar.day}日",
                "source": "lunardate"
            }
        except Exception as e:
            logging.error(f"lunardate 模块出错: {e}")
    
    # 如果 lunardate 不可用，返回默认值
    return {
        "lunar_str": f"农历{date_obj.month}月{date_obj.day}日",
        "lunar_year": date_obj.year,
        "lunar_month": date_obj.month,
        "lunar_day": date_obj.day,
        "lunar_month_name": f"{date_obj.month}月",
        "lunar_day_name": f"{date_obj.day}日",
        "source": "default"
    }


def get_holiday_info(date_obj=None):
    """获取节日信息"""
    if date_obj is None:
        date_obj = datetime.date.today()
    
    # 使用内置节日数据常量
    builtin_holidays = BUILTIN_HOLIDAYS
    
    # 农历节日（需要农历转换，这里简化处理）
    lunar_holidays = {
        "正月初一": "春节",
        "正月十五": "元宵节",
        "二月初二": "龙抬头",
        "五月初五": "端午节",
        "七月初七": "七夕节",
        "七月十五": "中元节",
        "八月十五": "中秋节",
        "九月初九": "重阳节",
        "腊月初八": "腊八节",
        "腊月二十三": "小年",
        "腊月三十": "除夕",
    }
    
    # 优先使用 chinese-calendar 模块
    if HOLIDAY_MODULE_AVAILABLE:
        try:
            # 检查是否为节假日
            if chinese_calendar.is_holiday(date_obj):
                # 获取节日详情
                holiday_detail = chinese_calendar.get_holiday_detail(date_obj)
                if holiday_detail:
                    return {
                        "is_holiday": True,
                        "holiday_name": holiday_detail,
                        "is_workday": False,
                        "source": "chinese-calendar"
                    }
        except Exception as e:
            logging.warning(f"chinese-calendar 模块出错: {e}")
    
    # 使用内置数据
    date_str = date_obj.strftime("%m-%d")
    if date_str in builtin_holidays:
        return {
            "is_holiday": True,
            "holiday_name": builtin_holidays[date_str],
            "is_workday": False,
            "source": "builtin"
        }
    
    # 检查是否为工作日（简化版）
    weekday = date_obj.weekday()
    is_workday = weekday < 5  # 周一到周五为工作日
    
    return {
        "is_holiday": False,
        "holiday_name": None,
        "is_workday": is_workday,
        "source": "builtin"
    }

# -------------------- 工具函数 --------------------
def compute_life_ui(data):
    """计算生命进度UI，剩余天数每日递减"""
    try:
        life_settings = data.get("life_settings", {})
        ideal_age_years = int(life_settings.get("ideal_age", 80))

        # 根据生日计算当前年龄
        birthday_str = life_settings.get("birthday", "")
        if birthday_str:
            try:
                birthday = datetime.date.fromisoformat(birthday_str)
                today = datetime.date.today()
                current_age_years = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
            except (ValueError, AttributeError):
                # 如果生日格式错误，使用默认年龄
                current_age_years = 25
        else:
            # 向后兼容，如果没有生日但有current_age，使用旧值
            current_age_years = int(life_settings.get("current_age", 25))

        if ideal_age_years <= 0:
            ideal_age_years = 80

        # 每日递减基线
        today = datetime.date.today()
        base_days_key = "remain_base_days"
        base_date_key = "remain_base_date"

        if base_days_key not in life_settings or base_date_key not in life_settings:
            life_settings[base_days_key] = max(ideal_age_years - current_age_years, 0) * 365
            life_settings[base_date_key] = today.isoformat()
            save_data(data)

        try:
            base_date = datetime.date.fromisoformat(life_settings.get(base_date_key, today.isoformat()))
        except ValueError:
            base_date = today

        base_remaining_days = int(life_settings.get(base_days_key, 0))
        delta_days = (today - base_date).days
        remaining_days = max(base_remaining_days - max(delta_days, 0), 0)

        # 生命阶段
        if current_age_years < 12:
            stage_icon, stage_text = "👶", "幼年"
        elif current_age_years < 30:
            stage_icon, stage_text = "🧑", "青年"
        elif current_age_years < 50:
            stage_icon, stage_text = "👨", "中年"
        else:
            stage_icon, stage_text = "👴", "老年"

        # 计算进度
        ideal_total_days = max(ideal_age_years, 1) * 365
        elapsed_days = max(ideal_total_days - remaining_days, 0)
        value = min(max(elapsed_days / ideal_total_days, 0.0), 1.0)

        return value, stage_icon, stage_text, f"余生 {remaining_days:,} 天"
    except Exception as e:
        logging.error(f"Failed to compute life UI: {e}")
        return 0.3, "🧑", "青年", "余生 20,075 天"

def import_orders_from_excel(data):
    """从Excel导入订单"""
    if not EXCEL_AVAILABLE:
        return 0
    
    excel_dir = data.get("excel_dir")
    if not excel_dir or not os.path.exists(excel_dir):
        return 0
    
    count = 0
    files = glob.glob(os.path.join(excel_dir, "*.xlsx"))
    for f in files:
        try:
            wb = openpyxl.load_workbook(f, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                
                date_cell = row[0]
                if isinstance(date_cell, (datetime.datetime, datetime.date)):
                    date_str = date_cell.date().isoformat() if isinstance(date_cell, datetime.datetime) else date_cell.isoformat()
                else:
                    date_str = str(date_cell).strip()
                
                try:
                    if DATEUTIL_AVAILABLE:
                        date_obj = date_parse(date_str, dayfirst=False, yearfirst=True)
                    else:
                        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    date_iso = date_obj.date().isoformat()
                except ValueError:
                    logging.warning(f"Invalid date format in file {f}: {date_str}")
                    continue
                
                order = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                typ = str(row[2]).strip() if len(row) > 2 and row[2] else "发货"
                
                if not order:
                    continue
                
                key = "shipping_orders" if "发货" in typ else "pre_shipping_orders"
                data.setdefault(key, {}).setdefault(date_iso, [])
                
                if order not in [o if isinstance(o, str) else o.get("order", "") for o in data[key][date_iso]]:
                    data[key][date_iso].append(order)
                    count += 1
            
            wb.close()
        except Exception as e:
            logging.error(f"Failed to read Excel file {f}: {e}")
    return count

def set_startup(enable: bool):
    """设置自动启动"""
    if sys.platform != "win32" or not WINREG_AVAILABLE:
        return
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        if enable:
            winreg.SetValueEx(key, "DailyReminder", 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, "DailyReminder")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        logging.error(f"Failed to set startup: {e}")

def create_styled_button(text, color="#2563EB", hover_color="#1D4ED8"):
    """创建统一样式的按钮"""
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {color};
            color: white;
            border: none;
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 9pt;
            min-width: 65px;
            min-height: 26px;
            max-height: 26px;
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {hover_color};
            padding: 6px 12px 4px 12px;
        }}
    """)
    return btn

# -------------------- 现代化生命进度条 --------------------
class ModernProgressBar(QWidget):
    """现代化进度条组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.stage_icon = "🧑"
        self.stage_text = "青年"
        self.days_text = "余生 20,075 天"
        self.setMinimumHeight(60)  # 缩小纵向空白
        self.setStyleSheet("background: white; border-radius: 8px;")
        
    def set_values(self, value, stage_icon, stage_text, days_text):
        """设置进度值"""
        self.value = max(0.0, min(1.0, value))
        self.stage_icon = stage_icon
        self.stage_text = stage_text
        self.days_text = days_text
        self.update()
    
    def paintEvent(self, event):
        """绘制进度条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 定义布局区域 - 填满红框位置
        total_content_width = width - 20  # 填满整个宽度，只留10px边距
        start_x = 10  # 左边距10px
        
        icon_width = 60  # 左侧图标区域宽度
        right_text_width = 120  # 右侧文字区域宽度
        margin = 5  # 减少左右边距
        
        # 计算进度条区域（增加纵向显示范围）
        bar_x = start_x + icon_width
        bar_width = total_content_width - icon_width - right_text_width
        bar_y = height // 2 - 16  # 垂直居中，进度条高度约32（增加）
        bar_height = 32  # 增加进度条高度
        
        # 绘制整体背景
        painter.fillRect(0, 0, width, height, QColor("white"))
        
        # 绘制进度条背景（灰色，居中）
        painter.setBrush(QBrush(QColor("#F3F4F6")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 8, 8)
        
        # 绘制进度条填充 - 渐变效果
        if self.value > 0:
            fill_width = int(bar_width * self.value)
            if fill_width > 0:
                gradient = QLinearGradient(bar_x, 0, bar_x + fill_width, 0)
                gradient.setColorAt(0, QColor("#10B981"))  # 绿色
                gradient.setColorAt(0.5, QColor("#F59E0B"))  # 橙色
                gradient.setColorAt(1, QColor("#EF4444"))  # 红色
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bar_x, bar_y, fill_width, bar_height, 8, 8)
        
        # 绘制进度百分比（在进度条中央，垂直居中）
        painter.setPen(QColor("#1F2937"))
        painter.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        percent_text = f"{int(self.value*100)}%"
        percent_rect = QRect(bar_x, 0, bar_width, height)
        painter.drawText(percent_rect, Qt.AlignmentFlag.AlignCenter, percent_text)
        
        # 绘制左侧图标（放大5倍，垂直居中）
        painter.setFont(QFont("Segoe UI Emoji", 36))
        icon_rect = QRect(start_x + margin, 0, icon_width - margin, height)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self.stage_icon)
        
        # 绘制右侧剩余天数（垂直居中）
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#1F2937"))
        days_rect = QRect(start_x + total_content_width - right_text_width, 0, right_text_width - margin, height)
        painter.drawText(days_rect, Qt.AlignmentFlag.AlignCenter, self.days_text)

# -------------------- 气泡通知 --------------------
class BubbleNotification(QWidget):
    """桌面右下角气泡通知"""
    def __init__(self, title="提醒", message="", duration=5000):
        super().__init__()
        self.title = title
        self.message = message
        self.duration = duration
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(350)  # 只固定宽度，高度根据内容调整
        
        self.setup_ui()
        self.setup_animation()
        
        # 设置位置到右下角
        self.position_to_bottom_right()
        
        # 自动关闭定时器
        self.close_timer = QTimer()
        self.close_timer.timeout.connect(self.close_notification)
        self.close_timer.setSingleShot(True)
        
        # 强制关闭定时器（5秒后强制关闭）
        self.force_close_timer = QTimer()
        self.force_close_timer.timeout.connect(self.force_close)
        self.force_close_timer.setSingleShot(True)
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        # 主容器
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        
        # 添加鼠标点击事件
        self.container.mousePressEvent = self.on_container_clicked
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(6)
        
        # 标题行（只包含标题）
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel(f"🔔 {self.title}")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 10pt;
                font-weight: bold;
                color: #1F2937;
                background: transparent;
            }
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        container_layout.addLayout(title_layout)
        
        # 消息内容
        self.message_label = QLabel(self.message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("""
            QLabel {
                font-size: 10pt;
                color: #6B7280;
                background: transparent;
                line-height: 1.4;
            }
        """)
        container_layout.addWidget(self.message_label)
        
        layout.addWidget(self.container)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)
        
    def setup_animation(self):
        """设置动画"""
        # 淡入动画
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        
        # 滑动动画
        self.slide_animation = QPropertyAnimation(self, b"geometry")
        self.slide_animation.setDuration(300)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def position_to_bottom_right(self):
        """定位到右下角，避免与任务栏重叠"""
        screen = QGuiApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 10  # 距离右边缘10像素
        
        # 确保窗口完全显示在屏幕内，避免与任务栏重叠
        # 使用实际窗口高度计算位置
        actual_height = self.height()
        y = screen.height() - actual_height - 60  # 距离底部60像素，往下移动2行文字的距离
        
        # 确保窗口不会超出屏幕顶部
        y = max(10, y)
        
        self.move(x, y)
        
        # 设置滑动动画的起始和结束位置
        start_rect = QRect(screen.width(), y, self.width(), self.height())
        end_rect = QRect(x, y, self.width(), self.height())
        self.slide_animation.setStartValue(start_rect)
        self.slide_animation.setEndValue(end_rect)
        
    def show_notification(self):
        """显示通知"""
        try:
            # 先显示窗口以计算实际高度
            self.show()
            
            # 根据实际高度重新计算位置
            self.position_to_bottom_right()
            
            self.raise_()  # 确保窗口在最前面
            self.activateWindow()  # 激活窗口
            
            # 启动动画
            self.fade_animation.start()
            self.slide_animation.start()
            
            # 启动自动关闭定时器
            if self.duration > 0:
                self.close_timer.start(self.duration)
            
            # 启动强制关闭定时器（5秒后强制关闭）
            self.force_close_timer.start(5000)
                
        except Exception as e:
            logging.error(f"Failed to show notification: {e}")
            # 如果动画失败，至少显示窗口
            self.show()
            
    def on_container_clicked(self, event):
        """容器点击事件"""
        # 点击气泡本身可以关闭
        self.close_notification()
    
    def close_notification(self):
        """关闭通知"""
        try:
            logging.info("Closing bubble notification")
            # 停止所有定时器
            self.close_timer.stop()
            self.force_close_timer.stop()
            
            # 检查窗口是否还存在
            if not self.isVisible():
                return
            
            # 淡出动画
            fade_out = QPropertyAnimation(self, b"windowOpacity")
            fade_out.setDuration(200)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.finished.connect(self.close)
            fade_out.start()
            
            # 如果动画在200ms内没有完成，强制关闭
            QTimer.singleShot(300, self.force_close)
            
        except Exception as e:
            logging.error(f"Failed to close notification: {e}")
            # 如果动画失败，直接关闭
            self.force_close()
    
    def force_close(self):
        """强制关闭通知（5秒后自动触发）"""
        try:
            logging.info("Force closing bubble notification")
            # 停止所有定时器
            if hasattr(self, 'close_timer'):
                self.close_timer.stop()
            if hasattr(self, 'force_close_timer'):
                self.force_close_timer.stop()
            
            # 检查窗口是否还存在
            if not self.isVisible():
                return
            
            # 直接关闭，不播放动画
            self.close()
        except Exception as e:
            logging.error(f"Failed to force close notification: {e}")
            # 最后的保险，尝试隐藏窗口
            try:
                self.hide()
            except:
                pass

# -------------------- 主窗口 --------------------
class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.setWindowTitle("每日工作提醒 - Qt6专业版")
        self.setMinimumSize(550, 680)  # 最小尺寸
        self.resize(550, 680)  # 默认尺寸
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)  # 支持缩放
        
        # 设置应用程序图标
        self.set_app_icon()
        
        # 应用现代化样式
        self.apply_modern_style()
        
        # 创建UI
        self.setup_ui()
        
        # 设置定时器
        self.reminder_timer = QTimer()
        self.reminder_timer.timeout.connect(self.check_reminders)
        
        # 订单闪烁定时器（用于未完成订单的红色闪烁效果）
        self.order_blink_timer = QTimer()
        self.order_blink_timer.timeout.connect(self.blink_overdue_orders)
        self.blink_state = False  # 闪烁状态
        self.overdue_order_rows = []  # 需要闪烁的订单行
        
        # 任务时间提醒定时器（默认每分钟检查一次）
        self.task_check_timer = QTimer()
        self.task_check_timer.timeout.connect(self.check_daily_task_notifications)
        self.task_notification_state = {}  # 记录任务提醒状态
        
        # 防止重复弹窗的标志
        self._last_dialog_show_time = None
        
        # 系统托盘
        self.setup_tray()
        
        # 居中显示
        self.center_window()
        
        # 启动定时器
        self.start_reminder_timer()
        
    def apply_modern_style(self):
        """应用现代化样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8FAFC;
            }
            QTabWidget::pane {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #F1F5F9;
                color: #64748B;
                padding: 10px 18px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 10pt;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: white;
                color: #DC2626;
                border-bottom: 3px solid #DC2626;
            }
            QTabBar::tab:hover {
                background: #E2E8F0;
            }
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 5px;
                font-size: 9pt;
                font-weight: normal;
                min-width: 70px;
                min-height: 28px;
                max-height: 28px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
            QTableWidget {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: white;
                gridline-color: #F3F4F6;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 7px;
                border-bottom: 1px solid #F3F4F6;
            }
            QTableWidget::item:selected {
                background-color: #EFF6FF;
                color: #1E40AF;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #374151;
                padding: 9px 7px;
                border: none;
                border-bottom: 2px solid #E2E8F0;
                font-weight: bold;
                font-size: 10pt;
            }
            QTextEdit {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: white;
                padding: 12px;
                font-size: 10pt;
            }
            QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 8px;
                background: white;
                font-size: 10pt;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 2px solid #2563EB;
            }
            QGroupBox {
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #2563EB;
            }
        """)
    
    def center_window(self):
        """窗口居中"""
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
    
    def set_app_icon(self):
        """设置应用程序图标"""
        try:
            # 方法1：尝试加载图标文件
            if getattr(sys, 'frozen', False):
                # 打包后的情况
                base_path = sys._MEIPASS
                icon_paths = [
                    os.path.join(base_path, "app_icon.ico"),
                    os.path.join(base_path, "tray_icon.ico"),
                    os.path.join(base_path, "icon.ico"),
                ]
            else:
                # 开发环境
                icon_paths = [
                    "app_icon.ico",      # Windows图标文件
                    "tray_icon.ico",     # 托盘图标文件
                    "app_icon.png",      # PNG图标文件
                    "icon.ico",          # 通用图标文件名
                    "icon.png",          # 通用PNG图标
                    "logo.ico",          # Logo图标
                    "logo.png"           # Logo PNG
                ]
            
            icon_set = False
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    self.setWindowIcon(QIcon(icon_path))
                    icon_set = True
                    logging.info(f"Loaded app icon from: {icon_path}")
                    break
            
            # 方法2：如果没有找到图标文件，创建程序化图标
            if not icon_set:
                self.create_programmatic_icon()
                
        except Exception as e:
            logging.error(f"Failed to set app icon: {e}")
            # 如果设置图标失败，创建默认图标
            self.create_programmatic_icon()
    
    def create_programmatic_icon(self):
        """创建程序化图标"""
        try:
            # 创建一个简单的图标
            pixmap = QPixmap(64, 64)
            pixmap.fill(QColor(239, 68, 68, 0))  # 透明背景
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制红色圆形背景
            painter.setBrush(QBrush(QColor(239, 68, 68)))
            painter.setPen(QPen(QColor(220, 38, 38), 2))
            painter.drawEllipse(4, 4, 56, 56)
            
            # 绘制时钟图标
            painter.setPen(QPen(QColor(255, 255, 255), 3))
            painter.drawEllipse(20, 20, 24, 24)
            
            # 绘制时钟指针
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(32, 32, 32, 26)  # 时针
            painter.drawLine(32, 32, 38, 32)  # 分针
            
            painter.end()
            
            self.setWindowIcon(QIcon(pixmap))
            logging.info("Created programmatic icon")
            
        except Exception as e:
            logging.error(f"Failed to create programmatic icon: {e}")
    
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(8)  # 减少间距
        layout.setContentsMargins(12, 12, 12, 12)  # 减少边距
        
        # 生命进度区域
        self.create_life_section(layout)
        
        # 工作提醒区域
        self.create_reminder_section(layout)
        
        # 订单管理选项卡
        self.create_order_tabs(layout)
        
        # 底部按钮
        self.create_bottom_buttons(layout)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 初始化数据显示
        self.update_all_displays()
        
        # 延迟刷新确保所有组件都已创建
        QTimer.singleShot(100, self.update_order_tables)
        QTimer.singleShot(300, self.update_order_tables)
        QTimer.singleShot(500, self.update_order_tables)
        
        # 打印调试信息
        logging.info(f"Initialization complete. Pre-orders: {self.data.get('pre_shipping_orders', {})}")
        
        # 延迟显示未完成订单提示对话框（程序启动后2秒）
        # 注意：showEvent也会触发检查，这里延迟较长避免重复
        QTimer.singleShot(2500, self.check_and_show_incomplete_orders)
    
    def create_life_section(self, parent_layout):
        """创建生命进度区域"""
        group = QGroupBox("⏰ 生命倒计时")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)  # 缩小上下边距，减少空白
        
        self.life_progress = ModernProgressBar()
        self.life_progress.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 固定高度
        layout.addWidget(self.life_progress)
        
        parent_layout.addWidget(group)
    
    def create_reminder_section(self, parent_layout):
        """创建工作提醒区域"""
        group = QGroupBox("📋 今日工作提醒")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)  # 减少上下边距，减少空白
        
        self.reminder_text = QLabel()
        self.reminder_text.setWordWrap(True)
        self.reminder_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.reminder_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.reminder_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reminder_text.setStyleSheet("""
            QLabel {
                font-size: 10pt;
                line-height: 1.4;
                border: none;
                background-color: #F9FAFB;
                padding: 6px 8px;
                border-radius: 4px;
            }
        """)
        
        # 添加红色发光闪烁效果
        self.reminder_glow_effect = QGraphicsDropShadowEffect()
        self.reminder_glow_effect.setBlurRadius(15)
        self.reminder_glow_effect.setColor(QColor(239, 68, 68, 150))  # 红色发光
        self.reminder_glow_effect.setOffset(0, 0)
        self.reminder_text.setGraphicsEffect(self.reminder_glow_effect)
        
        # 创建红色闪烁动画
        self.reminder_animation = QPropertyAnimation(self.reminder_glow_effect, b"color")
        self.reminder_animation.setDuration(2000)  # 2秒一个周期
        self.reminder_animation.setLoopCount(-1)  # 无限循环
        
        # 设置红色系颜色变化
        self.reminder_animation.setKeyValueAt(0, QColor(239, 68, 68, 150))   # 红色
        self.reminder_animation.setKeyValueAt(0.3, QColor(248, 113, 113, 200))  # 亮红色
        self.reminder_animation.setKeyValueAt(0.6, QColor(220, 38, 38, 180))  # 深红色
        self.reminder_animation.setKeyValueAt(1, QColor(239, 68, 68, 150))     # 回到红色
        
        # 启动动画
        self.reminder_animation.start()
        layout.addWidget(self.reminder_text)
        
        parent_layout.addWidget(group)
    
    def create_order_tabs(self, parent_layout):
        """创建订单管理选项卡"""
        self.order_tabs = QTabWidget()
        self.order_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.order_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #E2E8F0;
            }
        """)
        
        # 今日发货订单选项卡
        shipping_widget = QWidget()
        shipping_layout = QVBoxLayout(shipping_widget)
        shipping_layout.setContentsMargins(16, 16, 16, 16)
        
        self.shipping_table = self.create_order_table(["序号", "订单号", "备注"])
        self.shipping_table.setMinimumHeight(200)  # 最小高度
        # 不设置最大高度，让它完全跟随窗口缩放
        self.shipping_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.shipping_table.verticalHeader().setDefaultSectionSize(32)  # 降低10%行高
        shipping_layout.addWidget(self.shipping_table)
        
        self.order_tabs.addTab(shipping_widget, "🚚 今日发货订单")
        
        # 预备发货订单选项卡
        pre_widget = QWidget()
        pre_layout = QVBoxLayout(pre_widget)
        pre_layout.setContentsMargins(16, 16, 16, 16)
        
        self.pre_table = self.create_order_table(["发货日期", "订单号", "状态", "备注"])
        self.pre_table.setMinimumHeight(200)  # 最小高度
        # 不设置最大高度，让它完全跟随窗口缩放
        self.pre_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pre_table.verticalHeader().setDefaultSectionSize(32)  # 降低10%行高
        self.pre_table.cellDoubleClicked.connect(self.toggle_pre_order_status)
        
        # 设置列可以自由拉宽
        self.pre_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.pre_table.horizontalHeader().setStretchLastSection(True)
        
        pre_layout.addWidget(self.pre_table)
        
        self.order_tabs.addTab(pre_widget, "⌛ 预备发货订单")
        
        parent_layout.addWidget(self.order_tabs)
    
    def create_order_table(self, headers):
        """创建订单表格"""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)  # 显示网格线
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #E2E8F0;
            }
        """)
        
        # 设置列可以自由拉宽
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # 设置初始列宽
        if len(headers) == 3:
            if headers[0] == "序号":
                table.setColumnWidth(0, 60)
                table.setColumnWidth(1, 280)
            else:
                table.setColumnWidth(0, 100)
                table.setColumnWidth(2, 90)
        elif len(headers) == 4:  # 预备订单表格
            table.setColumnWidth(0, 100)
            table.setColumnWidth(1, 200)
            table.setColumnWidth(2, 80)
            table.setColumnWidth(3, 150)
        
        return table
    
    def create_bottom_buttons(self, parent_layout):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()
        
        # 立即提醒按钮
        remind_btn = QPushButton("🔔 立即提醒")
        remind_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                padding: 6px 14px;
                font-size: 9pt;
                min-width: 80px;
                min-height: 28px;
                max-height: 28px;
            }
            QPushButton:hover {
                background-color: #7C3AED;
            }
        """)
        remind_btn.clicked.connect(self.immediate_reminder)
        button_layout.addWidget(remind_btn)
        
        # 控制面板按钮
        control_btn = QPushButton("⚙️ 控制面板")
        control_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 14px;
                font-size: 9pt;
                min-width: 80px;
                min-height: 28px;
                max-height: 28px;
            }
        """)
        control_btn.clicked.connect(self.open_control_panel)
        button_layout.addWidget(control_btn)
        
        button_layout.addStretch()
        parent_layout.addLayout(button_layout)
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 设置菜单
        settings_menu = menubar.addMenu("⚙️ 设置")
        
        # 控制面板
        control_action = QAction("🎛️ 控制面板", self)
        control_action.triggered.connect(self.open_control_panel)
        settings_menu.addAction(control_action)
        
        settings_menu.addSeparator()
        
        # 生命倒计时设置
        life_action = QAction("⏰ 生命倒计时设置", self)
        life_action.triggered.connect(self.open_life_settings)
        settings_menu.addAction(life_action)
        
        # 节日管理已移除，节日功能自动运行
        
        
        # 自定义提醒
        custom_reminder_action = QAction("🔔 自定义提醒设置", self)
        custom_reminder_action.triggered.connect(self.open_custom_reminder_settings)
        settings_menu.addAction(custom_reminder_action)
        
        settings_menu.addSeparator()
        
        # 数据存储设置
        storage_action = QAction("💾 数据存储设置", self)
        storage_action.triggered.connect(self.open_storage_settings)
        settings_menu.addAction(storage_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("❓ 帮助")
        
        
        help_menu.addSeparator()
        
        # 关于
        about_action = QAction("ℹ️ 关于程序", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_tray(self):
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        
        try:
            # 尝试加载托盘图标文件
            tray_icon_paths = []
            
            if getattr(sys, 'frozen', False):
                # 打包后的情况
                base_path = sys._MEIPASS
                tray_icon_paths = [
                    os.path.join(base_path, "tray_icon.ico"),
                    os.path.join(base_path, "app_icon.ico"),
                    os.path.join(base_path, "icon.ico"),
                ]
            else:
                # 开发环境
                tray_icon_paths = [
                    "tray_icon.ico",
                    "app_icon.ico", 
                    "icon.ico",
                    "tray_icon.png",
                    "app_icon.png",
                ]
            
            icon_loaded = False
            for tray_icon_path in tray_icon_paths:
                if os.path.exists(tray_icon_path):
                    try:
                        self.tray_icon.setIcon(QIcon(tray_icon_path))
                        logging.info(f"Successfully loaded tray icon from: {tray_icon_path}")
                        icon_loaded = True
                        break
                    except Exception as e:
                        logging.warning(f"Failed to load tray icon from {tray_icon_path}: {e}")
                        continue
            
            if not icon_loaded:
                # 创建程序化托盘图标
                logging.info("Creating programmatic tray icon")
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(QColor(37, 99, 235)))
                painter.drawEllipse(4, 4, 56, 56)
                
                # 添加一个简单的图标
                painter.setPen(QPen(QColor(255, 255, 255), 3))
                painter.drawEllipse(20, 20, 24, 24)
                painter.drawLine(32, 32, 32, 26)  # 时针
                painter.drawLine(32, 32, 38, 32)  # 分针
                
                painter.end()
                
                self.tray_icon.setIcon(QIcon(pixmap))
                logging.info("Created programmatic tray icon")
                
        except Exception as e:
            logging.error(f"Failed to set tray icon: {e}")
            # 使用默认图标
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor(37, 99, 235)))
            painter.drawEllipse(4, 4, 56, 56)
            painter.end()
            self.tray_icon.setIcon(QIcon(pixmap))
        
        self.tray_icon.setToolTip("昱景每日工作提醒")
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("📂 打开程序", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("❌ 退出程序", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()
    
    def show_from_tray(self):
        """从托盘显示窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
        # 显示窗口后检查超期订单（showEvent也会触发，这里延迟避免重复）
        QTimer.singleShot(600, self.check_and_show_incomplete_orders)
    
    def update_all_displays(self):
        """更新所有显示"""
        self.update_life_progress()
        self.update_reminder_text()
        self.update_order_tables()
    
    def update_life_progress(self):
        """更新生命进度"""
        try:
            value, stage_icon, stage_text, days_text = compute_life_ui(self.data)
            self.life_progress.set_values(value, stage_icon, stage_text, days_text)
        except Exception as e:
            logging.error(f"Failed to update life progress: {e}")
    
    def update_reminder_text(self):
        """更新提醒文本"""
        try:
            today = datetime.date.today()
            weekday = today.weekday()
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            
            # 获取节日信息和农历日期
            festival_text = self.get_festival_text()
            lunar_info = get_lunar_date(today)
            day_night_icon = get_day_night_icon()
            
            # 日期和节日显示在同一行
            text = f"📅 {today.isoformat()} 星期{weekday_names[weekday]} {day_night_icon} {lunar_info['lunar_str']}"
            if festival_text:
                text += f" {festival_text}"
            task_text = self.build_today_tasks_text(today)
            if task_text:
                text += f"\n{task_text}"
            
            self.reminder_text.setText(text)
            
        except Exception as e:
            logging.error(f"Failed to update reminder text: {e}")

    
    def build_today_tasks_text(self, target_date=None):
        """构建指定日期的任务文本，用于标签和气泡弹窗"""
        try:
            target_date = target_date or datetime.date.today()
            date_str = target_date.strftime("%Y-%m-%d")
            daily_tasks = self.data.get("daily_tasks", {})
            tasks = daily_tasks.get(date_str, [])
            
            priority_symbols = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }
            
            header = "📝 今日任务："
            if not tasks:
                return header  # 返回标题，用于主界面显示
            
            lines = [header]
            for task in tasks:
                if isinstance(task, dict):
                    content = task.get("content", "未命名任务")
                    priority = task.get("priority", "medium")
                    completed = task.get("completed", False)
                    time_text = (task.get("time") or "").strip() or "全天"
                else:
                    content = str(task)
                    priority = "medium"
                    completed = False
                    time_text = "全天"
                
                status_icon = "✅" if completed else "⬜"
                priority_icon = priority_symbols.get(priority, "🟡")
                lines.append(f"{status_icon} {priority_icon} [{time_text}] {content}")
            
            return "\n".join(lines)
        except Exception as e:
            logging.error(f"Failed to build today tasks text: {e}")
            return "📝 今日任务：暂无"
    
    def get_festival_text(self):
        """获取节日文本"""
        try:
            today = datetime.date.today()
            festival_msgs = []
            
            for k, name in self.data.get("festival_reminders", {}).items():
                try:
                    mm, dd = map(int, k.split('-'))
                    fdate = datetime.date(today.year, mm, dd)
                    delta = (fdate - today).days
                    
                    if 0 <= delta <= 3:
                        if delta == 0:
                            festival_msgs.append(f"🎊 今天是{name}！")
                        elif delta == 1:
                            festival_msgs.append(f"🎈 明天是{name}")
                        else:
                            festival_msgs.append(f"🎁 {name}还有{delta}天")
                except ValueError:
                    continue
            
            return " | ".join(festival_msgs) if festival_msgs else ""
            
        except Exception as e:
            logging.error(f"Failed to get festival text: {e}")
            return ""
    
    def auto_sync_pre_to_shipping(self):
        """自动将到期的预备订单同步到发货订单（暂停状态的订单不自动同步）"""
        try:
            today = today_str()
            pre_orders = self.data.get("pre_shipping_orders", {})
            
            if not pre_orders:
                return 0
            
            transferred_count = 0
            dates_to_remove = []
            
            # 遍历所有预备订单日期，处理所有过期和今天的订单
            for date_str, date_pre_orders in pre_orders.items():
                # 跳过"TBD"（待定）订单
                if date_str == "TBD":
                    continue
                
                # 检查日期是否过期或等于今天
                try:
                    order_date = datetime.date.fromisoformat(date_str)
                    today_date = datetime.date.today()
                    
                    # 只处理过期和今天的订单
                    if order_date > today_date:
                        continue
                        
                except ValueError:
                    # 如果日期格式不正确，跳过
                    logging.warning(f"Invalid date format in pre-orders: {date_str}")
                    continue
                
                if not date_pre_orders:
                    dates_to_remove.append(date_str)
                    continue
                
                shipping_orders = self.data.setdefault("shipping_orders", {}).setdefault(date_str, [])
                paused_orders = []  # 保留的订单列表（暂停、未完成、旧格式订单）
                
                for pre_order in date_pre_orders:
                    if isinstance(pre_order, dict):
                        order_num = pre_order.get("order", "")
                        remark = pre_order.get("remark", "")
                        order_status = pre_order.get("status", ORDER_STATUS_PENDING)
                        
                        # 如果是暂停状态，保留不同步
                        if order_status == ORDER_STATUS_PAUSED:
                            paused_orders.append(pre_order)
                            logging.info(f"Skipped paused pre-order: {order_num}")
                            continue
                        
                        # 只有状态为"完成"的订单才自动同步到发货订单
                        if order_status != ORDER_STATUS_DONE:
                            # 未完成的订单（未完成、制作中等状态）保留在预备订单中，不删除
                            paused_orders.append(pre_order)
                            logging.info(f"Skipped incomplete pre-order: {order_num} (status: {order_status})")
                            continue
                        
                        # 状态为"完成"的订单，检查是否已存在后同步到发货订单
                        exists = any(
                            (ship_order.get("order", "") if isinstance(ship_order, dict) else str(ship_order)) == order_num
                            for ship_order in shipping_orders
                        )
                        
                        if not exists:
                            auto_remark = remark if remark else ""
                            auto_remark += " [自动同步]" if auto_remark else "[预备订单自动同步]"
                            shipping_orders.append({"order": order_num, "remark": auto_remark})
                            transferred_count += 1
                            logging.info(f"Auto-synced completed pre-order: {order_num} from {date_str}")
                    else:
                        # 旧格式订单（非字典格式），没有状态信息，不自动同步
                        # 保留在预备订单中，等待用户手动处理或更新格式
                        order_num = str(pre_order)
                        paused_orders.append(pre_order)
                        logging.info(f"Skipped old-format pre-order (no status): {order_num} - please update to new format")
                
                # 保留未完成的订单（暂停、未完成、旧格式），只有所有订单都已完成并同步后，才删除该日期条目
                if paused_orders:
                    self.data["pre_shipping_orders"][date_str] = paused_orders
                else:
                    dates_to_remove.append(date_str)
            
            # 删除已处理的日期条目
            for date_str in dates_to_remove:
                if date_str in self.data["pre_shipping_orders"]:
                    del self.data["pre_shipping_orders"][date_str]
            
            if transferred_count > 0:
                save_data(self.data)
                logging.info(f"Auto-synced {transferred_count} pre-orders from {len(dates_to_remove)} dates")
            
            return transferred_count
        except Exception as e:
            logging.error(f"Failed to auto-sync pre-orders: {e}")
            return 0
    
    def update_order_tables(self):
        """更新订单表格"""
        try:
            # 自动同步到期的预备订单
            synced_count = self.auto_sync_pre_to_shipping()
            if synced_count > 0:
                logging.info(f"Auto-synced {synced_count} pre-orders to shipping")
            
            # 注意：不重新加载数据，直接使用self.data（可能包含控制面板的修改）
            # 如果需要在其他地方刷新数据，可以显式调用load_data()
            
            # 更新今日发货订单
            today = today_str()
            shipping_orders = self.data.get("shipping_orders", {}).get(today, [])
            
            self.shipping_table.setRowCount(len(shipping_orders) if shipping_orders else 1)
            
            if shipping_orders:
                for i, order in enumerate(shipping_orders):
                    if isinstance(order, dict):
                        order_num = order.get("order", "")
                        remark = order.get("remark", "")
                    else:
                        order_num = str(order)
                        remark = ""
                    
                    self.shipping_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                    self.shipping_table.setItem(i, 1, QTableWidgetItem(order_num))
                    self.shipping_table.setItem(i, 2, QTableWidgetItem(remark))
            else:
                self.shipping_table.setItem(0, 0, QTableWidgetItem("-"))
                self.shipping_table.setItem(0, 1, QTableWidgetItem("今日无发货订单"))
                self.shipping_table.setItem(0, 2, QTableWidgetItem(""))
            
            # 更新预备发货订单
            pre_orders = self.data.get("pre_shipping_orders", {})
            future_pre = []
            
            logging.info(f"Pre-orders data keys: {list(pre_orders.keys())}")
            logging.info(f"Today: {today}")
            
            # 先处理待定订单
            if "TBD" in pre_orders:
                tbd_list = pre_orders.get("TBD", [])
                logging.info(f"TBD orders: {len(tbd_list)}")
                for item in tbd_list:
                    future_pre.append(("待定", item))
            
            # 处理其他日期订单，按日期前后顺序排列
            # 包括过期订单，让用户看到需要处理的超期订单
            date_keys = [d for d in pre_orders.keys() if d != "TBD"]
            # 按日期排序（字符串格式的日期可以直接比较）
            date_keys.sort()
            for d in date_keys:
                date_list = pre_orders.get(d, [])
                logging.info(f"Date {d} orders: {len(date_list)}")
                for item in date_list:
                    future_pre.append((d, item))
            
            logging.info(f"Total future_pre count: {len(future_pre)}")
            
            self.pre_table.setRowCount(len(future_pre) if future_pre else 1)
            
            # 重置过期订单行列表
            self.overdue_order_rows = []
            overdue_order_nums = []  # 用于提示
            
            if future_pre:
                today_date = datetime.date.today()
                for i, (date, item) in enumerate(future_pre):
                    if isinstance(item, dict):
                        order_num = item.get("order", "")
                        status_key = item.get("status", ORDER_STATUS_PENDING)
                        status = ORDER_STATUS_DISPLAY.get(status_key, "⏳ 未完成")
                        remark = item.get("remark", "")
                    else:
                        order_num = str(item)
                        status_key = ORDER_STATUS_PENDING  # 旧格式订单默认未完成
                        status = "⏳ 未完成"
                        remark = ""
                    
                    # 检查订单是否已到达发货日期但未完成
                    is_overdue = False
                    if date != "待定" and date != "TBD":
                        try:
                            order_date = datetime.date.fromisoformat(date)
                            # 订单日期已到达或已过期，且状态不是"完成"
                            if order_date <= today_date and status_key != ORDER_STATUS_DONE:
                                is_overdue = True
                                self.overdue_order_rows.append(i)
                                overdue_order_nums.append(order_num)
                        except (ValueError, AttributeError):
                            pass
                    
                    # 创建表格项
                    date_item = QTableWidgetItem(date)
                    order_item = QTableWidgetItem(order_num)
                    status_item = QTableWidgetItem(status)
                    remark_item = QTableWidgetItem(remark)
                    
                    # 如果是过期未完成订单，设置初始红色背景
                    if is_overdue:
                        red_brush = QBrush(QColor(255, 200, 200))  # 浅红色背景
                        date_item.setBackground(red_brush)
                        order_item.setBackground(red_brush)
                        status_item.setBackground(red_brush)
                        remark_item.setBackground(red_brush)
                        # 设置字体颜色为红色
                        order_item.setForeground(QBrush(QColor(220, 38, 38)))  # 深红色文字
                        status_item.setForeground(QBrush(QColor(220, 38, 38)))
                    
                    self.pre_table.setItem(i, 0, date_item)
                    self.pre_table.setItem(i, 1, order_item)
                    self.pre_table.setItem(i, 2, status_item)
                    self.pre_table.setItem(i, 3, remark_item)
            
            # 如果有过期订单，显示提示（避免频繁提示）
            should_notify = False
            if overdue_order_nums:
                # 检查是否需要显示提示（首次检测到或距离上次提示超过5分钟）
                current_time = datetime.datetime.now()

                if not hasattr(self, '_last_overdue_notify_time'):
                    # 首次检测到过期订单
                    should_notify = True
                    self._last_overdue_notify_time = current_time
                else:
                    # 检查是否距离上次提示超过5分钟
                    time_diff = (current_time - self._last_overdue_notify_time).total_seconds()
                    if time_diff > OVERDUE_NOTIFICATION_INTERVAL:
                        should_notify = True
                        self._last_overdue_notify_time = current_time
            
            if should_notify:
                order_list = "、".join(overdue_order_nums[:MAX_DISPLAY_ORDERS])
                if len(overdue_order_nums) > MAX_DISPLAY_ORDERS:
                    order_list += f"等{len(overdue_order_nums)}个"
                
                bubble = BubbleNotification(
                    title="⚠️ 订单提醒",
                    message=f"以下订单已到达发货日期但未完成：{order_list}\n请及时处理！",
                    duration=8000  # 8秒后自动关闭
                )
                bubble.show_notification()
                logging.info(f"Overdue order notification shown: {order_list}")
            
            # 如果没有订单，显示空状态
            if not future_pre:
                self.pre_table.setItem(0, 0, QTableWidgetItem("-"))
                self.pre_table.setItem(0, 1, QTableWidgetItem("暂无预备订单"))
                self.pre_table.setItem(0, 2, QTableWidgetItem(""))
                self.pre_table.setItem(0, 3, QTableWidgetItem(""))
            
            # 更新选项卡标题（在同步后重新获取最新的订单数量）
            # 重新获取今日发货订单数量（因为可能刚刚同步了订单）
            today = today_str()
            current_shipping_orders = self.data.get("shipping_orders", {}).get(today, [])
            shipping_count = len(current_shipping_orders) if current_shipping_orders else 0
            pre_count = len(future_pre) if future_pre else 0
            
            self.order_tabs.setTabText(0, f"🚚 今日发货订单 ({shipping_count})")
            # 如果有过期订单，在标题中显示警告
            if self.overdue_order_rows:
                self.order_tabs.setTabText(1, f"⌛ 预备发货订单 ({pre_count}) ⚠️")
            else:
                self.order_tabs.setTabText(1, f"⌛ 预备发货订单 ({pre_count})")
        except Exception as e:
            logging.error(f"Failed to update order tables: {e}")
    
    def blink_overdue_orders(self):
        """闪烁显示过期未完成的订单"""
        try:
            if not self.overdue_order_rows:
                return
            
            # 切换闪烁状态
            self.blink_state = not self.blink_state
            
            # 为过期订单行设置闪烁效果
            if self.blink_state:
                # 亮红色背景
                bright_red = QBrush(QColor(255, 100, 100))
                dark_red = QBrush(QColor(200, 0, 0))  # 深红色文字
            else:
                # 浅红色背景
                bright_red = QBrush(QColor(255, 200, 200))
                dark_red = QBrush(QColor(220, 38, 38))  # 深红色文字
            
            for row in self.overdue_order_rows:
                # 更新所有列的背景色
                for col in range(4):  # 4列：日期、订单号、状态、备注
                    item = self.pre_table.item(row, col)
                    if item:
                        item.setBackground(bright_red)
                
                # 订单号和状态列使用深红色文字
                order_item = self.pre_table.item(row, 1)
                status_item = self.pre_table.item(row, 2)
                if order_item:
                    order_item.setForeground(dark_red)
                if status_item:
                    status_item.setForeground(dark_red)
        except Exception as e:
            logging.error(f"Failed to blink overdue orders: {e}")
    
    def toggle_pre_order_status(self, row, col):
        """切换预备订单状态"""
        try:
            # 获取点击的订单信息
            date_item = self.pre_table.item(row, 0)
            order_item = self.pre_table.item(row, 1)
            
            if not date_item or not order_item:
                return
            
            date = date_item.text()
            order_num = order_item.text()
            
            # 转换"待定"为"TBD"
            if date == "待定":
                date = "TBD"
            
            # 在数据中查找订单
            pre_orders = self.data.get("pre_shipping_orders", {})
            if date not in pre_orders:
                return
            
            # 查找订单索引
            order_index = -1
            for i, item in enumerate(pre_orders[date]):
                item_order = item.get("order", "") if isinstance(item, dict) else str(item)
                if item_order == order_num:
                    order_index = i
                    break
            
            if order_index == -1:
                return
            
            # 显示状态切换对话框
            dialog = OrderStatusDialog(self, order_num, date, pre_orders[date][order_index])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_status, new_date = dialog.get_result()
                
                # 获取当前订单项
                current_item = pre_orders[date][order_index]
                if not isinstance(current_item, dict):
                    current_item = {"order": str(current_item), "status": ORDER_STATUS_PENDING}
                
                # 更新订单状态
                current_item["status"] = new_status
                
                # 检查是否需要移动订单到不同日期
                if new_date != date:
                    # 从当前日期移除订单
                    removed_item = pre_orders[date].pop(order_index)
                    if not pre_orders[date]:
                        del pre_orders[date]
                    
                    # 添加到新日期
                    pre_orders.setdefault(new_date, []).append(current_item)
                    
                    # 显示更新信息
                    if new_date == "TBD":
                        QMessageBox.information(self, "订单更新",
                            f"订单 '{order_num}' 已移动到待定日期\n状态：{ORDER_STATUS_DISPLAY.get(new_status, '未知')}")
                    else:
                        QMessageBox.information(self, "订单更新",
                            f"订单 '{order_num}' 已移动到 {new_date}\n状态：{ORDER_STATUS_DISPLAY.get(new_status, '未知')}")
                else:
                    # 只更新状态，不移动日期
                    pre_orders[date][order_index] = current_item
                    status_text = ORDER_STATUS_DISPLAY.get(new_status, "未知")
                    QMessageBox.information(self, "状态更新",
                        f"订单 '{order_num}' 状态已更新为：\n{status_text}")
                
                # 保存数据并刷新
                save_data(self.data)
                # 如果订单状态变为"完成"，可能需要同步到发货订单，所以先同步再更新
                self.auto_sync_pre_to_shipping()
                self.update_order_tables()
                
        except Exception as e:
            logging.error(f"Failed to toggle pre order status: {e}")
            QMessageBox.warning(self, "错误", f"切换状态失败：{e}")
    
    def start_reminder_timer(self):
        """启动定时提醒"""
        try:
            if self.data.get("reminder_enabled", True):
                interval_min = int(self.data.get("reminder_interval", 120))
                self.reminder_timer.start(interval_min * 60 * 1000)  # 转换为毫秒
                logging.info(f"Reminder timer started with interval: {interval_min} minutes")
                
                if not self.task_check_timer.isActive():
                    self.task_check_timer.start(60 * 1000)  # 每分钟检查任务提醒
                    logging.info("Task check timer started with interval: 1 minute")
            else:
                if self.task_check_timer.isActive():
                    self.task_check_timer.stop()
                logging.info("Reminder timer disabled by settings")
            
            # 启动订单闪烁定时器（每500毫秒闪烁一次）
            self.order_blink_timer.start(500)
        except Exception as e:
            logging.error(f"Failed to start reminder timer: {e}")
    
    def stop_reminder_timer(self):
        """停止定时提醒"""
        if self.reminder_timer.isActive():
            self.reminder_timer.stop()
            logging.info("Reminder timer stopped")
        
        if self.task_check_timer.isActive():
            self.task_check_timer.stop()
            logging.info("Task check timer stopped")
        
        if self.order_blink_timer.isActive():
            self.order_blink_timer.stop()
            logging.info("Order blink timer stopped")
    
    def check_reminders(self):
        """检查提醒"""
        try:
            if not self.data.get("reminder_enabled", True):
                return
            
            # 导入Excel订单
            count = import_orders_from_excel(self.data)
            if count > 0:
                save_data(self.data)
                self.update_order_tables()
            
            # 检查自定义提醒
            self.check_custom_reminders()
            
            # 检查任务时间提醒
            self.check_daily_task_notifications()
            
            # 显示提醒
            self.show_reminder()
            
            logging.info("Scheduled reminder triggered")
        except Exception as e:
            logging.error(f"Failed to check reminders: {e}")
    
    def check_custom_reminders(self):
        """检查自定义提醒"""
        try:
            current_time = QTime.currentTime()
            current_date = QDate.currentDate()
            
            for reminder in self.data.get("custom_reminders", []):
                if not reminder.get("enabled", True):
                    continue
                
                # 检查时间是否匹配
                reminder_time_str = reminder.get("time", "09:00")
                reminder_time = QTime.fromString(reminder_time_str, "HH:mm")
                
                # 检查是否是每日重复
                if reminder.get("daily", True):
                    # 每日重复：检查时间是否在前后1分钟内
                    if abs(current_time.secsTo(reminder_time)) <= 60:
                        self.show_custom_reminder_bubble(reminder)
                else:
                    # 特定日期：检查日期和时间
                    specific_date_str = reminder.get("specific_date", "")
                    if specific_date_str:
                        try:
                            specific_date = QDate.fromString(specific_date_str, "yyyy-MM-dd")
                            if current_date == specific_date and abs(current_time.secsTo(reminder_time)) <= 60:
                                self.show_custom_reminder_bubble(reminder)
                        except:
                            continue
                            
        except Exception as e:
            logging.error(f"Failed to check custom reminders: {e}")
    
    def show_custom_reminder_bubble(self, reminder):
        """显示自定义提醒气泡"""
        try:
            content = reminder.get("content", "提醒")
            bubble = BubbleNotification(
                title="自定义提醒",
                message=content,
                duration=6000  # 6秒后自动关闭
            )
            bubble.show_notification()
            logging.info(f"Custom reminder triggered: {content}")
        except Exception as e:
            logging.error(f"Failed to show custom reminder bubble: {e}")
    
    def check_daily_task_notifications(self):
        """检查当日任务的提前与到点提醒"""
        try:
            if not self.data.get("reminder_enabled", True):
                self.task_notification_state.clear()
                return
            
            today = datetime.date.today()
            today_str_val = today.strftime("%Y-%m-%d")
            now = datetime.datetime.now()
            daily_tasks = self.data.get("daily_tasks", {})
            today_tasks = daily_tasks.get(today_str_val, [])
            
            # 清理非当日的提醒状态
            expired_keys = [key for key, state in self.task_notification_state.items()
                            if state.get("date") != today_str_val]
            for key in expired_keys:
                self.task_notification_state.pop(key, None)
            
            for task in today_tasks:
                if isinstance(task, dict):
                    if task.get("completed", False):
                        continue
                    time_text = (task.get("time") or "").strip()
                    content = task.get("content", "未命名任务").strip() or "未命名任务"
                    task_id = task.get("id")
                else:
                    time_text = "全天"
                    content = str(task).strip() or "未命名任务"
                    task_id = None
                
                if not time_text or time_text.lower() == "全天":
                    continue  # 无具体时间不提醒
                
                try:
                    due_time_obj = datetime.datetime.strptime(time_text, "%H:%M").time()
                except ValueError:
                    logging.warning(f"Invalid task time format: {time_text}")
                    continue
                
                due_datetime = datetime.datetime.combine(today, due_time_obj)
                diff_minutes = (due_datetime - now).total_seconds() / 60.0
                
                key = task_id or f"{today_str_val}_{content}_{time_text}"
                state = self.task_notification_state.setdefault(
                    key,
                    {
                        "date": today_str_val,
                        "half": False,
                        "due": False,
                        "schedule_key": ""
                    }
                )
                
                # 如果用户调整了任务的日期或时间，重新允许提醒触发
                current_schedule_key = f"{today_str_val}_{time_text}"
                if state.get("schedule_key") != current_schedule_key:
                    state["schedule_key"] = current_schedule_key
                    state["half"] = False
                    state["due"] = False
                    state["date"] = today_str_val
                
                # 提前30分钟提醒
                if 0 < diff_minutes <= 30 and not state["half"]:
                    self.show_task_notification_bubble(content, time_text, mode="upcoming")
                    state["half"] = True
                
                # 到时间提醒（允许前后5分钟以内）
                if -5 <= diff_minutes <= 1 and not state["due"]:
                    self.prompt_task_completion(task, today_str_val, content, time_text)
                    state["due"] = True
                
                self.task_notification_state[key] = state
        except Exception as e:
            logging.error(f"Failed to check daily task notifications: {e}")
    
    def show_task_notification_bubble(self, content, time_text, mode="due"):
        """显示任务提醒气泡"""
        try:
            if mode == "upcoming":
                title = "任务即将开始"
                message = (
                    f"⏱️ {time_text} 任务即将开始：\n"
                    f"{content}\n\n"
                    "请提前准备，完成后记得在月视图标记。"
                )
            else:
                title = "任务提醒"
                message = f"{time_text} {content}"
            
            bubble = BubbleNotification(
                title=title,
                message=message,
                duration=7000
            )
            bubble.show_notification()
            logging.info(f"Task notification ({mode}) displayed for task: {content} @ {time_text}")
        except Exception as e:
            logging.error(f"Failed to show task notification bubble: {e}")
    
    def prompt_task_completion(self, task, date_str, content, time_text):
        """弹出对话框确认任务是否完成"""
        try:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("任务到点确认")
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setText(f"任务「{content}」已到设定时间 {time_text}")
            msg_box.setInformativeText("是否标记为已完成？")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            reply = msg_box.exec()
            if reply == QMessageBox.StandardButton.Yes:
                self.mark_task_completed(task, date_str, content, time_text)
            else:
                logging.info(f"Task completion declined for: {content} @ {time_text}")
        except Exception as e:
            logging.error(f"Failed to prompt task completion: {e}")
    
    def mark_task_completed(self, task, date_str, content, time_text):
        """将任务标记为完成并保存"""
        try:
            daily_tasks = self.data.setdefault("daily_tasks", {})
            tasks = daily_tasks.setdefault(date_str, [])
            
            if isinstance(task, dict):
                task["completed"] = True
            else:
                # 将旧格式任务转换为标准结构
                for idx, item in enumerate(tasks):
                    if item is task or (not isinstance(item, dict) and item == task):
                        tasks[idx] = {
                            "id": f"task_{uuid.uuid4().hex}",
                            "date": date_str,
                            "content": content,
                            "time": time_text,
                            "priority": "medium",
                            "completed": True
                        }
                        break
            
            save_data(self.data)
            self.update_reminder_text()
            logging.info(f"Task marked completed via prompt: {content} @ {time_text}")
        except Exception as e:
            logging.error(f"Failed to mark task completed: {e}")
    
    def show_reminder(self):
        """显示提醒弹窗"""
        try:
            today = datetime.date.today()
            today_str_val = today_str()
            shipping = self.data.get("shipping_orders", {}).get(today_str_val, [])
            
            task_text = self.build_today_tasks_text(today)
            
            shipping_lines = ["🚚 发货订单:"]
            if shipping:
                for order in shipping:
                    if isinstance(order, dict):
                        order_text = order.get("order", "")
                        remark = order.get("remark", "")
                        line = f"• {order_text}" if order_text else "• 未命名订单"
                        if remark:
                            line += f" ({remark})"
                        shipping_lines.append(line)
                    else:
                        shipping_lines.append(f"• {order}")
            else:
                shipping_lines.append("✨ 今日无订单")
            
            msg_sections = [
                task_text,
                "\n".join(shipping_lines)
            ]
            msg = "\n\n".join(section for section in msg_sections if section.strip())
            
            # 使用气泡通知显示提醒
            bubble = BubbleNotification(
                title="工作提醒",
                message=msg,
                duration=8000  # 8秒后自动关闭
            )
            bubble.show_notification()
        except Exception as e:
            logging.error(f"Failed to show reminder: {e}")
    
    def immediate_reminder(self):
        """立即提醒"""
        try:
            # 导入Excel订单
            count = import_orders_from_excel(self.data)
            if count > 0:
                save_data(self.data)
                logging.info(f"Imported {count} new orders from Excel")
            
            # 重新加载数据
            self.data = load_data()
            self.update_all_displays()
            self.show_reminder()
        except Exception as e:
            logging.error(f"Failed to trigger immediate reminder: {e}")
            QMessageBox.critical(self, "错误", f"立即提醒失败：{e}")
    
    def open_control_panel(self):
        """打开控制面板"""
        dialog = ControlPanelDialog(self, self.data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 获取更新后的数据（save_and_accept已经保存了，但我们需要更新主窗口的数据）
            self.data = dialog.get_data()
            # 如果对话框中的save_and_accept已经保存了数据，这里不需要重复保存
            # 但为了确保数据同步，我们再次保存一次（save_data是幂等的）
            save_data(self.data)
            
            # 设置开机自启动
            set_startup(self.data.get("startup_enabled", False))
            
            # 重启定时器
            self.stop_reminder_timer()
            self.start_reminder_timer()
            
            self.update_all_displays()
    
    def open_life_settings(self):
        """打开生命设置"""
        dialog = LifeSettingsDialog(self, self.data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data = dialog.get_data()
            save_data(self.data)
            self.update_life_progress()
    
    # 节日管理功能已移除，节日功能自动运行
    
    def open_custom_reminder_settings(self):
        """打开自定义提醒设置"""
        dialog = CustomReminderDialog(self, self.data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data = dialog.get_data()
            save_data(self.data)
    
    def open_storage_settings(self):
        """打开存储设置"""
        dialog = StorageSettingsDialog(self, self.data)
        dialog.exec()
    
    def check_and_show_incomplete_orders(self):
        """检查并显示未完成订单对话框"""
        try:
            # 防止短时间内重复弹窗（2秒内不重复弹窗）
            current_time = datetime.datetime.now()
            if self._last_dialog_show_time is not None:
                time_diff = (current_time - self._last_dialog_show_time).total_seconds()
                if time_diff < 2.0:  # 2秒内不重复弹窗
                    return
            
            # 重新加载数据，确保获取最新数据
            self.data = load_data()
            
            # 检查今天是否有到期的未完成订单
            incomplete_orders = []
            pre_orders = self.data.get("pre_shipping_orders", {})
            today = datetime.date.today()
            
            # 遍历所有预备订单，查找今天到期的未完成订单
            for date_str, orders in pre_orders.items():
                if date_str == "TBD":
                    continue  # 跳过待定订单
                
                try:
                    order_date = datetime.date.fromisoformat(date_str)
                    # 只检查今天到期的订单
                    if order_date != today:
                        continue
                except:
                    continue
                
                for order_info in orders:
                    if isinstance(order_info, dict):
                        status_key = order_info.get("status", ORDER_STATUS_PENDING)
                    else:
                        status_key = ORDER_STATUS_PENDING
                    
                    # 只显示未完成的订单（状态不是"完成"）
                    if status_key != ORDER_STATUS_DONE:
                        incomplete_orders.append(order_info)
            
            # 如果有今天到期的未完成订单，显示对话框
            if incomplete_orders:
                # 更新最后弹窗时间
                self._last_dialog_show_time = current_time
                # 确保主窗口显示在前
                self.show()
                self.raise_()
                self.activateWindow()
                
                # 创建并显示模态对话框
                dialog = IncompleteOrdersDialog(self, self.data)
                
                # 调整对话框大小，确保可以正确计算居中位置
                dialog.adjustSize()
                
                # 居中显示在主窗口
                if self.isVisible():
                    main_rect = self.geometry()
                    dialog_rect = dialog.geometry()
                    dialog.move(
                        main_rect.center().x() - dialog_rect.width() // 2,
                        main_rect.center().y() - dialog_rect.height() // 2
                    )
                else:
                    # 如果主窗口不可见，居中显示在屏幕
                    screen = QGuiApplication.primaryScreen().geometry()
                    dialog.move(
                        screen.center().x() - dialog.width() // 2,
                        screen.center().y() - dialog.height() // 2
                    )
                
                # 显示模态对话框（阻塞主窗口）
                dialog.exec()
                
                # 对话框关闭后，刷新数据
                self.data = load_data()
                self.update_order_tables()
        except Exception as e:
            logging.error(f"Failed to check and show incomplete orders: {e}")
    
    def show_about(self):
        """显示关于"""
        QMessageBox.about(self, "关于程序",
            "📌 程序名称：昱景每日提醒\n"
            "✨ 版本号：v3.0.2 Qt6版本\n"
            "👨‍💻 开发者：坤坤\n\n"
            "💡 感谢使用本程序！")
    
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 每次窗口显示时检查超期订单（延迟500ms，避免与启动检查冲突）
        QTimer.singleShot(500, self.check_and_show_incomplete_orders)
    
    def closeEvent(self, event):
        """关闭事件"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "昱景每日工作提醒",
            "程序已最小化到托盘，点击托盘图标可重新打开",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    
    def quit_app(self):
        """退出程序"""
        reply = QMessageBox.question(self, "退出确认",
                                    "确定要退出程序吗？",
                                    QMessageBox.StandardButton.Yes | 
                                    QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()

# -------------------- 订单状态对话框 --------------------
class IncompleteOrdersDialog(QDialog):
    """未完成订单提示对话框"""
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = copy.deepcopy(data)
        self.task_items = []  # 历史兼容字段，避免旧逻辑访问时报错
        self.setWindowTitle("到期订单提醒")
        self.setMinimumSize(520, 350)
        self.setMaximumSize(600, 450)
        self.order_checkboxes = {}  # 存储订单的复选框
        
        # 设置为模态对话框
        self.setModal(True)
        # 设置窗口标志，确保显示在最前面
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)  # 减少间距从20到10
        main_layout.setContentsMargins(15, 15, 15, 15)  # 减少边距从20到15
        
        # 标题区域
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)  # 减少间距从10到8
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 警告图标
        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 20px; color: #DC2626;")  # 缩小图标从24px到20px
        title_layout.addWidget(warning_icon)
        
        title_label = QLabel("到期订单提醒")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1F2937;")  # 缩小字体从14pt到12pt
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        main_layout.addLayout(title_layout)
        
        # 主要消息
        today = datetime.date.today()
        message_label = QLabel(f"📅 以下订单今天 ({today.isoformat()}) 到期，请确认是否完成:")
        message_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #DC2626; padding: 5px 0;")  # 减少padding和字体
        main_layout.addWidget(message_label)
        
        # 订单列表表格
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(4)
        self.orders_table.setHorizontalHeaderLabels(["选择", "订单号", "状态", "备注"])
        self.orders_table.horizontalHeader().setStretchLastSection(True)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.verticalHeader().setVisible(False)
        
        # 设置列宽
        header = self.orders_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # 复选框列固定
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # 订单号列可调整
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # 状态列固定
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # 备注列自动拉伸
        self.orders_table.setColumnWidth(0, 35)  # 复选框列
        self.orders_table.setColumnWidth(1, 180)  # 订单号列初始宽度
        self.orders_table.setColumnWidth(2, 100)  # 状态列固定宽度
        # 备注列会自动拉伸填充剩余空间
        
        # 设置表格样式
        self.orders_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #DC2626;
                border-radius: 8px;
                background-color: white;
                gridline-color: #E5E7EB;
            }
            QTableWidget::item {
                padding: 4px 4px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #DBEAFE;
            }
            QHeaderView::section {
                background-color: #F3F4F6;
                padding: 4px 4px;
                border: 1px solid #E5E7EB;
                font-weight: bold;
                color: #374151;
                font-size: 9pt;
            }
        """)
        
        main_layout.addWidget(self.orders_table)
        
        # 刷新订单列表
        self.refresh_orders()
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)  # 按钮间距
        button_layout.setContentsMargins(0, 5, 0, 0)  # 减少上边距
        button_layout.addStretch()
        
        # 确认按钮（绿色）- 使用统一按钮样式
        confirm_btn = create_styled_button("✓ 完成", "#10B981", "#059669")
        confirm_btn.clicked.connect(self.confirm_orders)
        button_layout.addWidget(confirm_btn)
        
        # 稍后处理按钮（灰色）- 使用统一按钮样式
        later_btn = create_styled_button("✕ 稍后处理", "#9CA3AF", "#6B7280")
        later_btn.clicked.connect(self.accept)
        button_layout.addWidget(later_btn)
        
        main_layout.addLayout(button_layout)
    
    def refresh_orders(self):
        """刷新未完成订单列表"""
        try:
            self.order_checkboxes.clear()
            
            # 收集今天到期的未完成订单
            incomplete_orders = []
            pre_orders = self.data.get("pre_shipping_orders", {})
            today = datetime.date.today()
            
            # 遍历所有预备订单
            for date_str, orders in pre_orders.items():
                if date_str == "TBD":
                    continue  # 跳过待定订单
                
                try:
                    order_date = datetime.date.fromisoformat(date_str)
                    # 只显示今天到期的订单
                    if order_date != today:
                        continue
                except:
                    continue
                
                for order_info in orders:
                    if isinstance(order_info, dict):
                        order_num = order_info.get("order", "")
                        status_key = order_info.get("status", ORDER_STATUS_PENDING)
                        remark = order_info.get("remark", "")
                    else:
                        order_num = str(order_info)
                        status_key = ORDER_STATUS_PENDING
                        remark = ""
                    
                    # 只显示未完成的订单（状态不是"完成"）
                    if status_key != ORDER_STATUS_DONE:
                        incomplete_orders.append({
                            "date": date_str,
                            "order_num": order_num,
                            "status": status_key,
                            "remark": remark,
                            "order_info": order_info
                        })
            
            # 设置表格行数
            if not incomplete_orders:
                self.orders_table.setRowCount(1)
                no_item = QTableWidgetItem("✅ 今天没有到期的未完成订单！")
                no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.orders_table.setItem(0, 0, no_item)
                self.orders_table.setSpan(0, 0, 1, 4)
                return
            
            self.orders_table.setRowCount(len(incomplete_orders))
            
            # 填充表格
            for i, order in enumerate(incomplete_orders):
                # 复选框列（使用与控制面板相同的样式，无自定义样式）
                checkbox = QCheckBox()
                checkbox.setChecked(False)
                checkbox.setProperty("order", order)
                self.order_checkboxes[order['order_num']] = checkbox
                self.orders_table.setCellWidget(i, 0, checkbox)
                
                # 订单号列（去掉图标，节省空间）
                order_item = QTableWidgetItem(order['order_num'])
                order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                order_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.orders_table.setItem(i, 1, order_item)
                
                # 状态列（去掉图标，节省空间）
                status_text = ORDER_STATUS_DISPLAY.get(order["status"], "⏳ 未完成")
                status_item = QTableWidgetItem(status_text)
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.orders_table.setItem(i, 2, status_item)
                
                # 备注列（去掉图标，节省空间）
                remark_text = order.get("remark", "") or "-"
                remark_item = QTableWidgetItem(remark_text)
                remark_item.setFlags(remark_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                remark_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 如果备注太长，设置工具提示
                if len(remark_text) > 15:
                    remark_item.setToolTip(remark_text)
                self.orders_table.setItem(i, 3, remark_item)
                
                # 设置行高（缩小）
                self.orders_table.setRowHeight(i, 28)  # 进一步缩小从32到28
            
        except Exception as e:
            logging.error(f"Failed to refresh incomplete orders: {e}")
            QMessageBox.critical(self, "错误", f"刷新订单列表失败：{e}")
    
    def confirm_orders(self):
        """确认选中的订单为已完成"""
        try:
            updated_count = 0
            pre_orders = self.data.get("pre_shipping_orders", {})
            
            # 遍历所有选中的复选框
            for order_num, checkbox in self.order_checkboxes.items():
                if checkbox.isChecked():
                    order = checkbox.property("order")
                    date = order["date"]
                    
                    # 更新订单状态为已完成
                    if date in pre_orders:
                        for i, order_info in enumerate(pre_orders[date]):
                            if isinstance(order_info, dict):
                                if order_info.get("order", "") == order_num:
                                    order_info["status"] = ORDER_STATUS_DONE
                                    updated_count += 1
                                    break
                            elif str(order_info) == order_num:
                                # 旧格式订单，转换为新格式
                                pre_orders[date][i] = {
                                    "order": order_num,
                                    "status": ORDER_STATUS_DONE,
                                    "remark": ""
                                }
                                updated_count += 1
                                break
            
            # 保存数据
            if updated_count > 0:
                save_data(self.data)
                
                # 更新主窗口数据
                if self.parent():
                    self.parent().data = load_data()
                    self.parent().update_order_tables()
                
                logging.info(f"Marked {updated_count} orders as completed")
                
                # 刷新列表
                self.refresh_orders()
                
                # 如果还有未完成订单，继续显示；否则关闭对话框
                if not self.order_checkboxes:
                    self.accept()
            else:
                QMessageBox.information(self, "提示", "请至少选择一个订单标记为已完成")
            
        except Exception as e:
            logging.error(f"Failed to confirm orders: {e}")
            QMessageBox.critical(self, "错误", f"确认订单失败：{e}")
    
    def get_data(self):
        """获取更新后的数据"""
        return self.data

class OrderStatusDialog(QDialog):
    """订单状态切换对话框"""
    def __init__(self, parent, order_num, date, order_info):
        super().__init__(parent)
        self.order_num = order_num
        self.date = date
        self.order_info = order_info
        self.setWindowTitle("状态与日期设置")
        self.setFixedSize(500, 450)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 订单信息
        info_group = QGroupBox("订单信息")
        info_layout = QFormLayout(info_group)
        
        info_layout.addRow("📦 订单号：", QLabel(self.order_num))
        display_date = "待定" if self.date == "TBD" else self.date
        info_layout.addRow("📅 发货日期：", QLabel(display_date))
        
        # 当前状态
        current_status = self.order_info.get("status", ORDER_STATUS_PENDING) if isinstance(self.order_info, dict) else ORDER_STATUS_PENDING
        current_status_text = ORDER_STATUS_DISPLAY.get(current_status, "⏳ 未完成")
        info_layout.addRow("📌 当前状态：", QLabel(current_status_text))
        
        layout.addWidget(info_group)
        
        # 状态选择
        status_group = QGroupBox("选择新状态")
        status_layout = QVBoxLayout(status_group)
        
        self.status_group = QButtonGroup()
        
        for status_key, status_label in ORDER_STATUS_DISPLAY.items():
            radio = QRadioButton(status_label)
            radio.setProperty("status_key", status_key)
            if status_key == current_status:
                radio.setChecked(True)
            self.status_group.addButton(radio)
            status_layout.addWidget(radio)
        
        layout.addWidget(status_group)
        
        # 日期选择（所有订单都可以修改日期）
        date_group = QGroupBox("📅 修改发货日期")
        date_layout = QVBoxLayout(date_group)
        
        # 日期类型选择
        self.date_type_group = QButtonGroup()
        self.specific_date_radio = QRadioButton("指定日期")
        self.tbd_radio = QRadioButton("设为待定")
        
        # 根据当前日期设置默认选择
        if self.date == "TBD":
            self.tbd_radio.setChecked(True)
        else:
            self.specific_date_radio.setChecked(True)
        
        self.date_type_group.addButton(self.specific_date_radio)
        self.date_type_group.addButton(self.tbd_radio)
        
        date_type_layout = QHBoxLayout()
        date_type_layout.addWidget(self.specific_date_radio)
        date_type_layout.addWidget(self.tbd_radio)
        date_type_layout.addStretch()
        date_layout.addLayout(date_type_layout)
        
        # 日期选择器
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        
        # 设置当前日期或今天
        if self.date != "TBD":
            try:
                current_date = QDate.fromString(self.date, "yyyy-MM-dd")
                if current_date.isValid():
                    self.date_edit.setDate(current_date)
                else:
                    self.date_edit.setDate(QDate.currentDate())
            except:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        
        date_layout.addWidget(self.date_edit)
        
        # 根据当前选择启用/禁用日期选择器
        self.date_edit.setEnabled(self.specific_date_radio.isChecked())
        self.specific_date_radio.toggled.connect(lambda checked: self.date_edit.setEnabled(checked))
        
        layout.addWidget(date_group)
        
        # 提示信息
        tip_label = QLabel("💡 提示：可以同时修改订单状态和发货日期")
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #F59E0B; padding: 10px; background: #FFF3CD; border-radius: 6px;")
        layout.addWidget(tip_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = create_styled_button("✅ 确定", "#10B981", "#059669")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = create_styled_button("❌ 取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def get_result(self):
        """获取结果"""
        selected_button = self.status_group.checkedButton()
        new_status = selected_button.property("status_key") if selected_button else ORDER_STATUS_PENDING
        
        # 获取新日期
        if self.tbd_radio.isChecked():
            new_date = "TBD"
        else:
            new_date = self.date_edit.date().toString("yyyy-MM-dd")
        
        return new_status, new_date

# -------------------- 月视图组件 --------------------
class MonthlyViewWidget(QWidget):
    """月视图组件"""
    task_selected = pyqtSignal(str)  # 发送选中的日期

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_month = datetime.date.today().replace(day=1)
        self.selected_date = None
        self.task_data = {}  # 存储任务数据
        self.task_area_visible = False
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 月份导航
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(36, 36)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-size: 14pt;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #D1D5DB;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
        """)
        self.prev_btn.clicked.connect(self.prev_month)
        nav_layout.addWidget(self.prev_btn)

        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet("""
            font-size: 16pt;
            font-weight: bold;
            color: #111827;
            padding: 8px;
        """)
        nav_layout.addWidget(self.month_label, 1)

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(36, 36)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-size: 14pt;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #D1D5DB;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
        """)
        self.next_btn.clicked.connect(self.next_month)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

        # 星期标题
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_layout = QHBoxLayout()
        weekday_layout.setSpacing(2)  # 减小间距
        for weekday in weekdays:
            label = QLabel(weekday)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(30)
            label.setStyleSheet("""
                font-weight: bold;
                font-size: 10pt;
                color: #6B7280;
                background-color: #F9FAFB;
                border-radius: 0px;
                border: 1px solid #E5E7EB;
                padding: 4px;
            """)
            weekday_layout.addWidget(label)
        layout.addLayout(weekday_layout)

        # 日历网格容器
        calendar_container = QWidget()
        calendar_container.setStyleSheet("background-color: #FFFFFF; border-radius: 0px; padding: 8px;")
        calendar_layout = QVBoxLayout(calendar_container)
        calendar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setHorizontalSpacing(6)
        self.calendar_grid.setVerticalSpacing(6)
        self.calendar_grid.setContentsMargins(4, 4, 4, 4)
        calendar_layout.addLayout(self.calendar_grid)
        
        layout.addWidget(calendar_container, 1)

        # 任务详情区域（初始隐藏）
        self.task_detail_widget = QWidget()
        self.task_detail_widget.setVisible(False)
        self.task_detail_widget.setFixedHeight(0)
        self.task_detail_widget.setStyleSheet("""
            QWidget {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        task_detail_layout = QVBoxLayout(self.task_detail_widget)
        task_detail_layout.setContentsMargins(15, 15, 15, 15)
        task_detail_layout.setSpacing(12)

        self.selected_date_label = QLabel()
        self.selected_date_label.setStyleSheet("""
            font-size: 13pt;
            font-weight: bold;
            color: #2563EB;
            padding: 8px 0px;
            border-bottom: 2px solid #E5E7EB;
        """)
        task_detail_layout.addWidget(self.selected_date_label)

        self.task_list = QListWidget()
        self.task_list.setMinimumHeight(120)
        self.task_list.setMaximumHeight(220)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
                font-size: 10pt;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #F3F4F6;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E40AF;
            }
        """)
        task_detail_layout.addWidget(self.task_list)

        layout.addWidget(self.task_detail_widget)

        self.update_calendar()

    def update_calendar(self):
        """更新日历显示"""
        # 清空现有网格
        self._clear_layout(self.calendar_grid)

        # 设置月份标签
        self.month_label.setText(f"{self.current_month.year}年{self.current_month.month}月")

        # 获取月份的第一天和最后一天
        first_day = self.current_month
        last_day = (first_day.replace(month=first_day.month % 12 + 1, day=1) - datetime.timedelta(days=1))

        # 计算起始位置（周一为第一列，Python默认0为周一）
        start_weekday = first_day.weekday()

        # 创建日期单元格
        current_date = first_day - datetime.timedelta(days=start_weekday)

        for week in range(6):  # 最多6周
            for weekday in range(7):
                if current_date.month == self.current_month.month:
                    # 当前月份的日期
                    cell_widget = self.create_date_cell(current_date)
                    self.calendar_grid.addWidget(cell_widget, week, weekday)
                else:
                    # 其他月份的日期（灰色显示）
                    cell_widget = self.create_date_cell(current_date, is_current_month=False)
                    self.calendar_grid.addWidget(cell_widget, week, weekday)

                current_date += datetime.timedelta(days=1)

        # 设置拉伸，让网格在可用空间内均匀分布
        for col in range(7):
            self.calendar_grid.setColumnStretch(col, 1)
        for row in range(6):
            self.calendar_grid.setRowStretch(row, 1)
        
        # 强制更新布局
        self.calendar_grid.update()
    
    def _clear_layout(self, layout):
        """递归清理布局"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            sub_layout = item.layout()
            spacer = item.spacerItem()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif sub_layout is not None:
                self._clear_layout(sub_layout)
            elif spacer is not None:
                # spacer 不需要额外处理
                pass
            del item

    def create_date_cell(self, date, is_current_month=True):
        """创建日期单元格"""
        cell = QWidget()
        # 使用合理的最小尺寸并允许自动拉伸
        cell.setMinimumSize(75, 70)
        cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cell.setCursor(Qt.CursorShape.PointingHandCursor)

        # 使用布局管理器
        main_layout = QVBoxLayout(cell)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(2)

        # 顶部布局（日期和任务数量）
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # 日期标签（左上角）
        date_label = QLabel(str(date.day))
        date_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        date_label.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {'#111827' if is_current_month else '#9CA3AF'};
            background: transparent;
            padding: 0px;
            border: none;
        """)
        top_layout.addWidget(date_label)
        top_layout.addStretch()

        # 任务数量标签（右上角）
        task_count = self.get_task_count(date)
        if task_count > 0:
            count_label = QLabel(str(task_count))
            count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            count_label.setFixedHeight(20)
            count_label.setMinimumWidth(20)
            count_label.setStyleSheet("""
                QLabel {
                    font-size: 9pt;
                    font-weight: bold;
                    color: #FFFFFF;
                    background-color: #DC2626;
                    border-radius: 10px;
                    padding: 0px 6px;
                }
            """)
            top_layout.addWidget(count_label)
            top_layout.setAlignment(count_label, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(top_layout)
        
        # 任务关键词标签
        keywords = self.get_task_keywords(date)
        if keywords:
            keyword_layout = QHBoxLayout()
            keyword_layout.setContentsMargins(0, 4, 0, 0)
            keyword_layout.setSpacing(4)
            for word in keywords:
                tag = QLabel(word)
                tag.setStyleSheet("""
                    QLabel {
                        font-size: 8pt;
                        color: #1F2937;
                        background-color: #E0F2FE;
                        border: 1px solid #BAE6FD;
                        border-radius: 6px;
                        padding: 1px 4px;
                    }
                """)
                tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
                keyword_layout.addWidget(tag)
            keyword_layout.addStretch()
            main_layout.addLayout(keyword_layout)
        
        main_layout.addStretch()

        # 设置单元格样式和颜色（去除圆角）
        task_count = self.get_task_count(date)
        color = self.get_cell_color(task_count)
        is_selected = self.selected_date and self.selected_date == date
        
        if is_selected:
            border_color = "#2563EB"
            border_width = "2px"
        else:
            border_color = "#E5E7EB"
            border_width = "1px"

        cell.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border: {border_width} solid {border_color};
                border-radius: 0px;
            }}
            QWidget:hover {{
                border-color: #2563EB;
                border-width: 2px;
                background-color: {'#F0F9FF' if task_count == 0 else color};
            }}
        """)

        # 去除阴影效果，避免视觉混乱
        cell.setGraphicsEffect(None)

        # 点击事件：左键选择日期，右键直接打开任务管理
        def handle_mouse_press(event, d=date):
            if event.button() == Qt.MouseButton.LeftButton:
                self.on_date_clicked(d)
            elif event.button() == Qt.MouseButton.RightButton:
                self.open_task_manager_dialog(d)
            event.accept()
        
        cell.mousePressEvent = handle_mouse_press

        return cell

    def get_task_count(self, date):
        """获取指定日期的任务数量"""
        date_str = date.strftime("%Y-%m-%d")
        tasks = self.task_data.get(date_str, [])
        return len(tasks)

    def get_cell_color(self, task_count):
        """根据任务数量获取单元格颜色"""
        if task_count == 0:
            return "#FFFFFF"  # 白色
        elif task_count <= 2:
            return "#FEF3C7"  # 浅黄
        elif task_count <= 4:
            return "#FCD34D"  # 黄色
        else:
            return "#F97316"  # 橙色

    def on_date_clicked(self, date):
        """日期点击事件"""
        # 如果再次点击同一天且任务区域已展开，则折叠
        if self.selected_date == date and self.task_area_visible:
            self.hide_task_area()
            self.selected_date = None
            self.task_selected.emit("")  # 发送空字符串表示取消选择
            self.update_calendar()
            return
        
        self.selected_date = date
        self.task_selected.emit(date.strftime("%Y-%m-%d"))
        self.update_calendar()
        self.show_task_area(date)

    def show_task_area(self, date):
        """显示任务区域"""
        self.selected_date_label.setText(f"📅 {date.strftime('%Y年%m月%d日')} 任务")
        self.update_task_list(date)
        self.task_detail_widget.setFixedHeight(260)
        self.task_detail_widget.setVisible(True)
        self.task_area_visible = True

    def hide_task_area(self):
        """折叠任务区域"""
        self.task_detail_widget.setVisible(False)
        self.task_detail_widget.setFixedHeight(0)
        self.task_list.clear()
        self.selected_date_label.clear()
        self.task_area_visible = False
    
    def get_task_keywords(self, date, max_keywords=3):
        """提取任务关键词以显示在日单元格"""
        date_str = date.strftime("%Y-%m-%d")
        tasks = self.task_data.get(date_str, [])
        keywords = []
        for task in tasks:
            if len(keywords) >= max_keywords:
                break
            if isinstance(task, dict):
                content = task.get("content", "")
            else:
                content = str(task)
            content = content.strip()
            if not content:
                continue
            # 使用前6个字符作为关键词，超过部分追加省略号
            keyword = content[:6]
            if len(content) > 6:
                keyword += "…"
            keywords.append(keyword)
        return keywords

    def update_task_list(self, date):
        """更新任务列表"""
        self.task_list.clear()
        date_str = date.strftime("%Y-%m-%d")
        tasks = self.task_data.get(date_str, [])

        if not tasks:
            # 显示空状态提示
            empty_item = QListWidgetItem("📝 暂无任务，右击日单元格即可添加")
            empty_item.setForeground(QColor("#9CA3AF"))
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)  # 不可选择
            self.task_list.addItem(empty_item)
            return

        for task in tasks:
            time_text = (task.get("time") or "").strip()
            display_time = time_text if time_text else "全天"
            priority_colors = {
                "high": "#EF4444",    # 红色
                "medium": "#F59E0B",  # 橙色
                "low": "#10B981"      # 绿色
            }

            priority_symbols = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }

            color = priority_colors.get(task.get("priority", "medium"), "#F59E0B")
            symbol = priority_symbols.get(task.get("priority", "medium"), "🟡")

            # 构建任务文本
            content = task['content']
            if task.get("completed", False):
                # 已完成任务：添加删除线效果
                item_text = f"{symbol} [{display_time}] ✓ {content}"
                # 使用灰色并添加删除线样式
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, task)
                item.setForeground(QColor("#9CA3AF"))
                # 设置字体样式（删除线效果通过样式表实现）
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
            else:
                item_text = f"{symbol} [{display_time}] {content}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, task)
                item.setForeground(QColor(color))
            
            self.task_list.addItem(item)

    def open_task_manager_dialog(self, date):
        """打开任务管理弹窗"""
        date_str = date.strftime("%Y-%m-%d")
        tasks = copy.deepcopy(self.task_data.get(date_str, []))
        dialog = TaskManagerDialog(date, tasks, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_tasks = dialog.get_tasks()
            if updated_tasks:
                # 确保任务信息完整
                self.task_data[date_str] = [self._normalize_task(task, date_str) for task in updated_tasks]
            elif date_str in self.task_data:
                self.task_data.pop(date_str, None)
            self.update_task_list(date)
            self.update_calendar()

    def prev_month(self):
        """上一个月"""
        if self.current_month.month == 1:
            self.current_month = self.current_month.replace(year=self.current_month.year - 1, month=12)
        else:
            self.current_month = self.current_month.replace(month=self.current_month.month - 1)
        self.update_calendar()

    def next_month(self):
        """下一个月"""
        if self.current_month.month == 12:
            self.current_month = self.current_month.replace(year=self.current_month.year + 1, month=1)
        else:
            self.current_month = self.current_month.replace(month=self.current_month.month + 1)
        self.update_calendar()

    def set_task_data(self, data):
        """设置任务数据"""
        self.task_data = {}
        for date_str, tasks in data.items():
            normalized = [self._normalize_task(task, date_str) for task in tasks]
            self.task_data[date_str] = normalized
        self.update_calendar()

    def get_task_data(self):
        """获取任务数据"""
        return self.task_data.copy()

    def _normalize_task(self, task, date_str):
        """确保任务包含必要字段"""
        normalized = task.copy()
        normalized.setdefault("date", date_str)
        normalized.setdefault("priority", "medium")
        normalized.setdefault("completed", False)
        normalized.setdefault("time", "全天")
        if not normalized.get("id"):
            normalized["id"] = f"task_{uuid.uuid4().hex}"
        return normalized

    def show_task_context_menu(self, position):
        """显示任务右键菜单"""
        item = self.task_list.itemAt(position)
        if not item:
            return

        task = item.data(Qt.ItemDataRole.UserRole)
        if not task:
            return

        menu = QMenu(self)

        # 标记完成/未完成
        toggle_action = QAction("✓ 标记完成" if not task.get("completed", False) else "○ 标记未完成", self)
        toggle_action.triggered.connect(lambda: self.toggle_task_completion(task))
        menu.addAction(toggle_action)

        # 编辑任务
        edit_action = QAction("✏️ 编辑任务", self)
        edit_action.triggered.connect(lambda: self.edit_task(task))
        menu.addAction(edit_action)

        menu.addSeparator()

        # 删除任务
        delete_action = QAction("🗑️ 删除任务", self)
        delete_action.triggered.connect(lambda: self.delete_task(task))
        menu.addAction(delete_action)

        menu.exec(self.task_list.mapToGlobal(position))

    def toggle_task_completion(self, task):
        """切换任务完成状态"""
        task["completed"] = not task.get("completed", False)
        if self.selected_date:
            self.update_task_list(self.selected_date)
            self.update_calendar()

    def edit_task(self, task):
        """编辑任务"""
        dialog = TaskEditDialog(task, self.selected_date, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_task = dialog.get_task_data()
            if updated_task:
                # 更新任务数据
                date_str = task["date"]
                tasks = self.task_data.get(date_str, [])
                for i, t in enumerate(tasks):
                    if t["id"] == task["id"]:
                        tasks[i] = updated_task
                        break
                self.task_data[date_str] = tasks
                if self.selected_date:
                    self.update_task_list(self.selected_date)
                    self.update_calendar()

    def delete_task(self, task):
        """删除任务"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除任务「{task['content']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            date_str = task["date"]
            tasks = self.task_data.get(date_str, [])
            tasks = [t for t in tasks if t["id"] != task["id"]]
            if tasks:
                self.task_data[date_str] = tasks
            else:
                self.task_data.pop(date_str, None)
            if self.selected_date:
                self.update_task_list(self.selected_date)
                self.update_calendar()

class TaskAddDialog(QDialog):
    """任务添加对话框"""

    def __init__(self, date, parent=None):
        super().__init__(parent)
        self.date = date
        self.setWindowTitle("添加任务")
        self.setFixedSize(480, 330)
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 日期显示
        date_label = QLabel(f"📅 {self.date.strftime('%Y年%m月%d日')}")
        date_label.setStyleSheet("""
            font-size: 14pt;
            font-weight: bold;
            color: #2563EB;
            padding: 8px 0px;
            border-bottom: 2px solid #E5E7EB;
        """)
        layout.addWidget(date_label)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(18)
        
        content_label = QLabel("任务内容：")
        content_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.content_edit = QLineEdit()
        self.content_edit.setPlaceholderText("请输入任务内容...")
        self.content_edit.setMinimumWidth(320)
        self.content_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #2563EB;
                background-color: #F9FAFB;
            }
        """)
        form_layout.addRow(content_label, self.content_edit)
        
        priority_label = QLabel("优先级：")
        priority_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["高", "中", "低"])
        self.priority_combo.setCurrentText("中")
        self.priority_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QComboBox:hover {
                border-color: #2563EB;
            }
            QComboBox:focus {
                border-color: #2563EB;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #6B7280;
                margin-right: 8px;
            }
        """)
        form_layout.addRow(priority_label, self.priority_combo)
        
        time_label = QLabel("执行时间：")
        time_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setStyleSheet("""
            QTimeEdit {
                padding: 8px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QTimeEdit:focus {
                border-color: #2563EB;
                background-color: #F9FAFB;
            }
        """)
        form_layout.addRow(time_label, self.time_edit)
        
        layout.addLayout(form_layout)
        layout.addSpacing(8)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        button_layout.addStretch()
        standard_btn_size = QSize(110, 40)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(standard_btn_size)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #374151;
                border: 1px solid #E5E7EB;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #D1D5DB;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedSize(standard_btn_size)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # 设置焦点
        self.content_edit.setFocus()

    def get_task_data(self):
        """获取任务数据"""
        content = self.content_edit.text().strip()
        if not content:
            return None

        priority_map = {"高": "high", "中": "medium", "低": "low"}
        priority = priority_map.get(self.priority_combo.currentText(), "medium")

        return {
            "id": f"task_{int(datetime.datetime.now().timestamp() * 1000)}",
            "content": content,
            "priority": priority,
            "completed": False,
            "date": self.date.strftime("%Y-%m-%d"),
            "time": self.time_edit.time().toString("HH:mm")
        }

class TaskEditDialog(QDialog):
    """任务编辑对话框"""

    def __init__(self, task, date, parent=None):
        super().__init__(parent)
        self.task = task
        self.date = date
        self.setWindowTitle("编辑任务")
        self.setFixedSize(440, 320)
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 日期显示
        date_label = QLabel(f"📅 {self.date.strftime('%Y年%m月%d日')}")
        date_label.setStyleSheet("""
            font-size: 12pt;
            font-weight: bold;
            color: #1F2937;
            padding: 4px 0px 8px 0px;
            border-bottom: 1px solid #E5E7EB;
        """)
        layout.addWidget(date_label)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)
        
        content_label = QLabel("任务内容：")
        content_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.content_edit = QLineEdit()
        self.content_edit.setText(self.task.get("content", ""))
        self.content_edit.setPlaceholderText("请输入任务内容...")
        self.content_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #2563EB;
                background-color: #F9FAFB;
            }
        """)
        form_layout.addRow(content_label, self.content_edit)

        priority_label = QLabel("优先级：")
        priority_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["高", "中", "低"])
        priority_reverse_map = {"high": "高", "medium": "中", "low": "低"}
        current_priority = priority_reverse_map.get(self.task.get("priority", "medium"), "中")
        self.priority_combo.setCurrentText(current_priority)
        self.priority_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QComboBox:hover {
                border-color: #2563EB;
            }
            QComboBox:focus {
                border-color: #2563EB;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #6B7280;
                margin-right: 8px;
            }
        """)
        form_layout.addRow(priority_label, self.priority_combo)

        # 完成状态
        self.completed_check = QCheckBox("已完成")
        self.completed_check.setChecked(self.task.get("completed", False))
        self.completed_check.setStyleSheet("""
            QCheckBox {
                font-size: 11pt;
                color: #374151;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #E5E7EB;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:hover {
                border-color: #2563EB;
            }
            QCheckBox::indicator:checked {
                background-color: #10B981;
                border-color: #10B981;
            }
            QCheckBox::indicator:checked::after {
                content: "✓";
                color: white;
                font-weight: bold;
            }
        """)
        status_label = QLabel("状态：")
        status_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        form_layout.addRow(status_label, self.completed_check)

        time_label = QLabel("执行时间：")
        time_label.setStyleSheet("font-size: 10pt; color: #374151; font-weight: bold;")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        time_str = self.task.get("time", "")
        if time_str:
            try:
                h, m = map(int, time_str.split(":"))
                self.time_edit.setTime(QTime(h, m))
            except Exception:
                self.time_edit.setTime(QTime.currentTime())
        else:
            self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setStyleSheet("""
            QTimeEdit {
                padding: 8px 12px;
                border: 2px solid #E5E7EB;
                border-radius: 6px;
                font-size: 11pt;
                background-color: #FFFFFF;
            }
            QTimeEdit:focus {
                border-color: #2563EB;
                background-color: #F9FAFB;
            }
        """)
        form_layout.addRow(time_label, self.time_edit)

        layout.addLayout(form_layout)
        layout.addSpacing(4)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        cancel_btn = create_styled_button("取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = create_styled_button("确定", "#10B981", "#059669")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # 设置焦点
        self.content_edit.setFocus()
        self.content_edit.selectAll()

    def get_task_data(self):
        """获取任务数据"""
        content = self.content_edit.text().strip()
        if not content:
            return None

        priority_map = {"高": "high", "中": "medium", "低": "low"}
        priority = priority_map.get(self.priority_combo.currentText(), "medium")

        # 复制原任务数据并更新
        updated_task = self.task.copy()
        updated_task.update({
            "content": content,
            "priority": priority,
            "completed": self.completed_check.isChecked(),
            "time": self.time_edit.time().toString("HH:mm")
        })

        return updated_task

# -------------------- 控制面板对话框 --------------------
class ControlPanelDialog(QDialog):
    """控制面板对话框"""
    def __init__(self, parent, data):
        super().__init__(parent)
        # 使用深拷贝确保嵌套字典也被正确复制，避免数据丢失
        self.data = copy.deepcopy(data)
        self.setWindowTitle("控制面板")
        self.setMinimumSize(900, 700)
        self.setup_ui()
    
    # ========== 辅助方法：消除重复代码 ==========
    def clear_pre_order_inputs(self):
        """清除预备订单输入框"""
        self.pre_order_edit.clear()
        self.pre_work_order_edit.clear()
        self.pre_remark_edit.clear()
    
    def clear_shipping_order_inputs(self):
        """清除发货订单输入框"""
        self.shipping_order_edit.clear()
        self.shipping_remark_edit.clear()
    
    def parse_order_data(self, order):
        """解析订单数据（支持新旧格式）"""
        if isinstance(order, dict):
            return {
                "order": order.get("order", ""),
                "work_order": order.get("work_order", ""),
                "remark": order.get("remark", ""),
                "status": order.get("status", ORDER_STATUS_PENDING)
            }
        else:
            # 旧格式（字符串）
            return {
                "order": str(order),
                "work_order": "",
                "remark": "",
                "status": ORDER_STATUS_PENDING
            }
    
    def get_order_number(self, order):
        """获取订单号（支持新旧格式）"""
        if isinstance(order, dict):
            return order.get("order", "")
        else:
            return str(order)
    
    def convert_display_date_to_original(self, display_date):
        """将显示日期转换为原始日期键"""
        return "TBD" if display_date == "待定" else display_date
    
    def convert_original_date_to_display(self, original_date):
        """将原始日期键转换为显示日期"""
        return "待定" if original_date == "TBD" else original_date
    
    def find_order_in_data(self, order_num, date_str=None):
        """在数据中查找订单，返回(日期键, 订单索引, 订单对象)"""
        all_pre_orders = self.data.get("pre_shipping_orders", {})
        
        # 如果指定了日期，只在对应日期中查找
        if date_str and date_str in all_pre_orders:
            orders = all_pre_orders[date_str]
            for i, order in enumerate(orders):
                if self.get_order_number(order) == order_num:
                    return date_str, i, order
        else:
            # 在所有日期中查找
            for date_key, orders in all_pre_orders.items():
                for i, order in enumerate(orders):
                    if self.get_order_number(order) == order_num:
                        return date_key, i, order
        
        return None, -1, None
    
    def save_and_accept(self):
        """保存数据并接受对话框"""
        try:
            # 重要：首先确保self.data中的订单数据完整
            # 订单数据在添加/编辑/删除时直接修改了self.data，必须确保这些数据被保留
            if "pre_shipping_orders" not in self.data:
                self.data["pre_shipping_orders"] = {}
            if "shipping_orders" not in self.data:
                self.data["shipping_orders"] = {}
            
            # 记录保存前的订单数量（用于调试）
            self_pre_count = sum(len(orders) for orders in self.data.get("pre_shipping_orders", {}).values())
            self_shipping_count = sum(len(orders) for orders in self.data.get("shipping_orders", {}).values())
            logging.info(f"Before get_data(): self.data contains {self_pre_count} pre_orders and {self_shipping_count} shipping_orders")
            
            # 通过get_data()收集所有UI中的设置数据（工作计划、系统设置等）
            # get_data()会更新self.data中的设置，但订单数据已经在self.data中
            updated_data = self.get_data()
            
            # 验证数据完整性：确保订单数据存在
            if "pre_shipping_orders" not in updated_data:
                updated_data["pre_shipping_orders"] = {}
            if "shipping_orders" not in updated_data:
                updated_data["shipping_orders"] = {}
            
            # 记录get_data()后的订单数量（用于调试）
            pre_count = sum(len(orders) for orders in updated_data.get("pre_shipping_orders", {}).values())
            shipping_count = sum(len(orders) for orders in updated_data.get("shipping_orders", {}).values())
            logging.info(f"After get_data(): updated_data contains {pre_count} pre_orders and {shipping_count} shipping_orders")
            
            # 关键修复：如果updated_data中的订单数量少于self.data中的，说明数据丢失
            # 这种情况下，直接使用self.data中的订单数据（这是最可靠的）
            if pre_count < self_pre_count or shipping_count < self_shipping_count:
                logging.warning(f"Data loss detected! self.data has {self_pre_count} pre_orders and {self_shipping_count} shipping_orders, "
                              f"but updated_data only has {pre_count} pre_orders and {shipping_count} shipping_orders")
                # 强制使用self.data中的订单数据，确保数据不丢失
                updated_data["pre_shipping_orders"] = copy.deepcopy(self.data.get("pre_shipping_orders", {}))
                updated_data["shipping_orders"] = copy.deepcopy(self.data.get("shipping_orders", {}))
                logging.info(f"Restored from self.data: pre_orders={sum(len(o) for o in updated_data['pre_shipping_orders'].values())}, "
                           f"shipping_orders={sum(len(o) for o in updated_data['shipping_orders'].values())}")
            
            # 最终验证：确保所有数据都存在
            final_pre_count = sum(len(orders) for orders in updated_data.get("pre_shipping_orders", {}).values())
            final_shipping_count = sum(len(orders) for orders in updated_data.get("shipping_orders", {}).values())
            logging.info(f"Final save: pre_orders={final_pre_count}, shipping_orders={final_shipping_count}")
            
            # 保存更新后的数据
            save_data(updated_data)
            
            # 更新self.data以保持一致性
            self.data = updated_data
            self.accept()
        except Exception as e:
            logging.error(f"Failed to save control panel data: {e}")
            import traceback
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "保存失败", f"保存数据时出错：{e}\n\n请检查数据完整性。")
    
    def get_pre_orders_selection_state(self):
        """获取预备订单选择状态：返回(总有效订单数, 已选订单数, 是否全部选中)"""
        row_count = self.pre_control_table.rowCount()
        total_valid = 0
        selected_count = 0
        
        for row in range(row_count):
            checkbox = self.pre_control_table.cellWidget(row, 0)
            order_item = self.pre_control_table.item(row, 2)
            
            if checkbox and isinstance(checkbox, QCheckBox):
                if order_item and order_item.text() != "暂无预备订单":
                    total_valid += 1
                    if checkbox.isChecked():
                        selected_count += 1
        
        all_selected = total_valid > 0 and selected_count == total_valid
        return total_valid, selected_count, all_selected
    
    def update_toggle_select_btn(self):
        """更新切换按钮的文本和状态"""
        if not hasattr(self, 'toggle_select_btn'):
            return
        
        _, _, all_selected = self.get_pre_orders_selection_state()
        
        if all_selected:
            # 全部选中，按钮显示为"取消全选"
            self.toggle_select_btn.setText("✗ 取消全选")
            self.toggle_select_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6B7280;
                    color: white;
                    border: none;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-size: 9pt;
                    min-width: 65px;
                    min-height: 26px;
                    max-height: 26px;
                }
                QPushButton:hover {
                    background-color: #4B5563;
                }
                QPushButton:pressed {
                    background-color: #4B5563;
                    padding: 6px 12px 4px 12px;
                }
            """)
        else:
            # 未全部选中，按钮显示为"全选"
            self.toggle_select_btn.setText("✓ 全选")
            self.toggle_select_btn.setStyleSheet("""
                QPushButton {
                    background-color: #10B981;
                    color: white;
                    border: none;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-size: 9pt;
                    min-width: 65px;
                    min-height: 26px;
                    max-height: 26px;
                }
                QPushButton:hover {
                    background-color: #059669;
                }
                QPushButton:pressed {
                    background-color: #059669;
                    padding: 6px 12px 4px 12px;
                }
            """)
    
    def toggle_select_all_pre_orders(self):
        """切换全选/取消全选"""
        _, _, all_selected = self.get_pre_orders_selection_state()
        row_count = self.pre_control_table.rowCount()
        
        if all_selected:
            # 当前全部选中，执行取消全选
            for row in range(row_count):
                checkbox = self.pre_control_table.cellWidget(row, 0)
                if checkbox and isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(False)
        else:
            # 当前未全部选中，执行全选
            for row in range(row_count):
                checkbox = self.pre_control_table.cellWidget(row, 0)
                if checkbox and isinstance(checkbox, QCheckBox):
                    order_item = self.pre_control_table.item(row, 2)
                    if order_item and order_item.text() != "暂无预备订单":
                        checkbox.setChecked(True)
        
        # 更新按钮状态
        self.update_toggle_select_btn()
    
    def select_all_pre_orders(self):
        """全选所有预备订单（保留此方法以兼容）"""
        row_count = self.pre_control_table.rowCount()
        for row in range(row_count):
            checkbox = self.pre_control_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                order_item = self.pre_control_table.item(row, 2)
                if order_item and order_item.text() != "暂无预备订单":
                    checkbox.setChecked(True)
        self.update_toggle_select_btn()
    
    def select_none_pre_orders(self):
        """全不选所有预备订单（保留此方法以兼容）"""
        row_count = self.pre_control_table.rowCount()
        for row in range(row_count):
            checkbox = self.pre_control_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                checkbox.setChecked(False)
        self.update_toggle_select_btn()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tabs = QTabWidget()
        
        # 工作计划选项卡
        work_tab = self.create_work_plan_tab()
        tabs.addTab(work_tab, "📝 工作计划")
        
        # 订单管理选项卡
        order_tab = self.create_order_management_tab()
        tabs.addTab(order_tab, "📦 订单管理")
        
        # 系统设置选项卡
        settings_tab = self.create_settings_tab()
        tabs.addTab(settings_tab, "⚙️ 系统设置")
        
        layout.addWidget(tabs)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = create_styled_button("💾 保存", "#10B981", "#059669")
        save_btn.clicked.connect(self.save_and_accept)
        button_layout.addWidget(save_btn)
        
        cancel_btn = create_styled_button("❌ 取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_work_plan_tab(self):
        """创建工作计划选项卡（月视图）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        try:
            # 创建月视图组件
            self.monthly_view = MonthlyViewWidget()
            # 从数据中加载任务数据
            task_data = self.data.get("daily_tasks", {})
            self.monthly_view.set_task_data(task_data)

            layout.addWidget(self.monthly_view)
        except Exception as e:
            # 如果月视图失败，回退到原始实现
            print(f"月视图加载失败，使用原始界面: {e}")
            import traceback
            traceback.print_exc()

            # 写入错误日志
            try:
                with open("monthly_view_error.log", "w", encoding="utf-8") as f:
                    f.write(f"月视图加载失败: {e}\n")
                    f.write(traceback.format_exc())
            except:
                pass

            layout.setContentsMargins(20, 20, 20, 20)

            form_layout = QFormLayout()
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

            self.work_entries = {}
            for i in range(7):
                entry = QLineEdit()
                entry.setText(self.data.get("work_plan", {}).get(str(i), ""))
                entry.setPlaceholderText(f"请输入{weekday_names[i]}的工作内容")
                form_layout.addRow(f"{weekday_names[i]}：", entry)
                self.work_entries[i] = entry

            layout.addLayout(form_layout)
            layout.addStretch()

        return widget
    
    def create_order_management_tab(self):
        """创建订单管理选项卡"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 发货订单管理
        shipping_group = QGroupBox("🚚 发货订单管理")
        shipping_layout = QVBoxLayout(shipping_group)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("发货日期："))
        self.shipping_date = QDateEdit()
        self.shipping_date.setCalendarPopup(True)
        self.shipping_date.setDate(QDate.currentDate())
        self.shipping_date.setDisplayFormat("yyyy-MM-dd")
        self.shipping_date.dateChanged.connect(self.refresh_shipping_control_table)
        input_layout.addWidget(self.shipping_date)
        
        input_layout.addWidget(QLabel("订单号："))
        self.shipping_order_edit = QLineEdit()
        self.shipping_order_edit.setPlaceholderText("请输入订单号")
        input_layout.addWidget(self.shipping_order_edit)
        
        input_layout.addWidget(QLabel("备注："))
        self.shipping_remark_edit = QLineEdit()
        self.shipping_remark_edit.setPlaceholderText("可选")
        input_layout.addWidget(self.shipping_remark_edit)
        
        shipping_layout.addLayout(input_layout)
        
        # 表格
        self.shipping_control_table = QTableWidget()
        self.shipping_control_table.setColumnCount(3)
        self.shipping_control_table.setHorizontalHeaderLabels(["序号", "订单号", "备注"])
        self.shipping_control_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.shipping_control_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.shipping_control_table.horizontalHeader().setStretchLastSection(True)
        self.shipping_control_table.setMaximumHeight(180)  # (200 * 0.9)
        self.shipping_control_table.itemSelectionChanged.connect(self.load_shipping_to_edit)
        shipping_layout.addWidget(self.shipping_control_table)
        
        # 按钮（发货订单只保留修改和删除）
        btn_layout = QHBoxLayout()
        
        edit_ship_btn = create_styled_button("✏️ 修改", "#F59E0B", "#D97706")
        edit_ship_btn.clicked.connect(self.edit_shipping_order)
        btn_layout.addWidget(edit_ship_btn)
        
        del_ship_btn = create_styled_button("🗑️ 删除", "#EF4444", "#DC2626")
        del_ship_btn.clicked.connect(self.delete_shipping_order)
        btn_layout.addWidget(del_ship_btn)
        
        btn_layout.addStretch()
        shipping_layout.addLayout(btn_layout)
        
        main_layout.addWidget(shipping_group)
        
        # 预备订单管理
        pre_group = QGroupBox("⌛ 预备订单管理")
        pre_layout = QVBoxLayout(pre_group)
        
        # 输入区域
        pre_input_layout = QHBoxLayout()
        
        pre_input_layout.addWidget(QLabel("发货日期："))
        self.pre_date = QDateEdit()
        self.pre_date.setCalendarPopup(True)
        self.pre_date.setDate(QDate.currentDate())
        self.pre_date.setDisplayFormat("yyyy-MM-dd")
        pre_input_layout.addWidget(self.pre_date)
        
        self.tbd_check = QCheckBox("待定日期")
        pre_input_layout.addWidget(self.tbd_check)
        
        pre_input_layout.addWidget(QLabel("订单号："))
        self.pre_order_edit = QLineEdit()
        self.pre_order_edit.setPlaceholderText("请输入订单号")
        pre_input_layout.addWidget(self.pre_order_edit)
        
        pre_input_layout.addWidget(QLabel("工单号："))
        self.pre_work_order_edit = QLineEdit()
        self.pre_work_order_edit.setPlaceholderText("请输入工单号（可选）")
        pre_input_layout.addWidget(self.pre_work_order_edit)
        
        pre_input_layout.addWidget(QLabel("备注："))
        self.pre_remark_edit = QLineEdit()
        self.pre_remark_edit.setPlaceholderText("可选")
        pre_input_layout.addWidget(self.pre_remark_edit)
        
        pre_layout.addLayout(pre_input_layout)
        
        # 表格
        self.pre_control_table = QTableWidget()
        self.pre_control_table.setColumnCount(6)
        self.pre_control_table.setHorizontalHeaderLabels(["选择", "发货日期", "订单号", "工单号", "备注", "状态"])
        self.pre_control_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pre_control_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pre_control_table.horizontalHeader().setStretchLastSection(True)
        self.pre_control_table.setMinimumHeight(300)  # 增加高度以显示更多订单
        self.pre_control_table.cellDoubleClicked.connect(self.toggle_pre_control_status)
        self.pre_control_table.itemSelectionChanged.connect(self.load_pre_to_edit)
        pre_layout.addWidget(self.pre_control_table)
        
        # 按钮
        pre_btn_layout = QHBoxLayout()
        add_pre_btn = create_styled_button("➕ 添加", "#10B981", "#059669")
        add_pre_btn.clicked.connect(self.add_pre_order)
        pre_btn_layout.addWidget(add_pre_btn)
        
        edit_pre_btn = create_styled_button("✏️ 修改", "#F59E0B", "#D97706")
        edit_pre_btn.clicked.connect(self.edit_pre_order)
        pre_btn_layout.addWidget(edit_pre_btn)
        
        del_pre_btn = create_styled_button("🗑️ 删除", "#EF4444", "#DC2626")
        del_pre_btn.clicked.connect(self.delete_pre_order)
        pre_btn_layout.addWidget(del_pre_btn)
        
        print_pre_btn = create_styled_button("🖨️ 打印标签", "#8B5CF6", "#7C3AED")
        print_pre_btn.clicked.connect(self.print_pre_order_label)
        pre_btn_layout.addWidget(print_pre_btn)
        
        # 全选/取消全选切换按钮
        self.toggle_select_btn = create_styled_button("✓ 全选", "#10B981", "#059669")
        self.toggle_select_btn.clicked.connect(self.toggle_select_all_pre_orders)
        pre_btn_layout.addWidget(self.toggle_select_btn)
        
        pre_btn_layout.addStretch()
        pre_layout.addLayout(pre_btn_layout)
        
        main_layout.addWidget(pre_group)
        
        # 初始刷新
        self.refresh_shipping_control_table()
        self.refresh_pre_control_table()
        
        # 初始化按钮状态
        self.update_toggle_select_btn()
        
        return widget
    
    def create_settings_tab(self):
        """创建系统设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 提醒间隔设置
        interval_group = QGroupBox("⏰ 提醒间隔设置")
        interval_layout = QFormLayout(interval_group)
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["30分钟", "1小时", "2小时", "4小时"])
        
        # 设置当前值
        current_interval = self.data.get("reminder_interval", 120)
        interval_map_reverse = {30: "30分钟", 60: "1小时", 120: "2小时", 240: "4小时"}
        self.interval_combo.setCurrentText(interval_map_reverse.get(current_interval, "2小时"))
        
        interval_layout.addRow("提醒间隔：", self.interval_combo)
        
        layout.addWidget(interval_group)
        
        # 开关设置
        switch_group = QGroupBox("🔔 功能开关")
        switch_layout = QVBoxLayout(switch_group)
        
        self.reminder_check = QCheckBox("启用定时提醒")
        self.reminder_check.setChecked(self.data.get("reminder_enabled", True))
        switch_layout.addWidget(self.reminder_check)
        
        self.startup_check = QCheckBox("开机自动启动")
        self.startup_check.setChecked(self.data.get("startup_enabled", False))
        switch_layout.addWidget(self.startup_check)
        
        layout.addWidget(switch_group)
        
        # Excel导入设置
        excel_group = QGroupBox("📊 Excel导入设置")
        excel_layout = QVBoxLayout(excel_group)
        
        excel_path_layout = QHBoxLayout()
        excel_path_layout.addWidget(QLabel("Excel文件夹："))
        self.excel_dir_edit = QLineEdit()
        self.excel_dir_edit.setText(self.data.get("excel_dir", ""))
        self.excel_dir_edit.setReadOnly(True)
        excel_path_layout.addWidget(self.excel_dir_edit)
        
        browse_btn = QPushButton("📁 浏览")
        browse_btn.clicked.connect(self.browse_excel_dir)
        excel_path_layout.addWidget(browse_btn)
        
        excel_layout.addLayout(excel_path_layout)
        
        import_btn = create_styled_button("🔄 立即导入Excel", "#F59E0B", "#D97706")
        import_btn.clicked.connect(self.import_excel)
        excel_layout.addWidget(import_btn)
        
        tip_label = QLabel("💡 格式：日期 | 订单号 | 类型（发货/预备）")
        tip_label.setStyleSheet("color: #6B7280; font-size: 9pt;")
        excel_layout.addWidget(tip_label)
        
        layout.addWidget(excel_group)
        layout.addStretch()
        
        return widget
    
    def browse_excel_dir(self):
        """浏览Excel文件夹"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择Excel文件夹",
                                                     self.data.get("excel_dir", HOME))
        if dir_path:
            self.excel_dir_edit.setText(dir_path)
            self.data["excel_dir"] = dir_path
    
    def import_excel(self):
        """导入Excel"""
        try:
            if not EXCEL_AVAILABLE:
                QMessageBox.warning(self, "警告", "请先安装openpyxl库:\npip install openpyxl")
                return
            
            count = import_orders_from_excel(self.data)
            if count > 0:
                save_data(self.data)
                self.refresh_shipping_control_table()
                self.refresh_pre_control_table()
                QMessageBox.information(self, "导入成功", f"共导入 {count} 个订单！")
            else:
                QMessageBox.information(self, "提示", "未找到新订单")
        except Exception as e:
            logging.error(f"Failed to import excel: {e}")
            QMessageBox.critical(self, "错误", f"导入失败：{e}")
    
    # 订单管理方法
    
    def refresh_shipping_control_table(self):
        """刷新发货订单表格"""
        try:
            date_str = self.shipping_date.date().toString("yyyy-MM-dd")
            orders = self.data.get("shipping_orders", {}).get(date_str, [])
            
            self.shipping_control_table.setRowCount(len(orders) if orders else 1)
            
            if orders:
                for i, order in enumerate(orders):
                    order_num = order.get("order", "") if isinstance(order, dict) else str(order)
                    remark = order.get("remark", "") if isinstance(order, dict) else ""
                    
                    self.shipping_control_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                    self.shipping_control_table.setItem(i, 1, QTableWidgetItem(order_num))
                    self.shipping_control_table.setItem(i, 2, QTableWidgetItem(remark))
            else:
                self.shipping_control_table.setItem(0, 0, QTableWidgetItem("-"))
                self.shipping_control_table.setItem(0, 1, QTableWidgetItem("当前日期无订单"))
                self.shipping_control_table.setItem(0, 2, QTableWidgetItem(""))
        except Exception as e:
            logging.error(f"Failed to refresh shipping control table: {e}")
    
    def refresh_pre_control_table(self):
        """刷新预备订单表格 - 显示所有预备订单"""
        try:
            all_pre_orders = self.data.get("pre_shipping_orders", {})
            all_orders = []
            
            # 收集所有预备订单
            for date_str, orders in all_pre_orders.items():
                for order in orders:
                    order_data = self.parse_order_data(order)
                    status_key = order_data["status"]
                    status = ORDER_STATUS_DISPLAY.get(status_key, "⏳ 未完成")
                    
                    display_date = self.convert_original_date_to_display(date_str)
                    all_orders.append({
                        "date": display_date,
                        "order": order_data["order"],
                        "work_order": order_data["work_order"],
                        "remark": order_data["remark"],
                        "status": status,
                        "original_date": date_str
                    })
            
            # 按日期排序
            all_orders.sort(key=lambda x: (x["original_date"] == "TBD", x["original_date"]))
            
            self.pre_control_table.setRowCount(len(all_orders) if all_orders else 1)
            
            if all_orders:
                for i, order_data in enumerate(all_orders):
                    # 第一列：复选框
                    checkbox = QCheckBox()
                    checkbox.setChecked(False)
                    # 连接复选框状态改变信号，以更新按钮状态
                    checkbox.stateChanged.connect(self.update_toggle_select_btn)
                    self.pre_control_table.setCellWidget(i, 0, checkbox)
                    # 第二列：发货日期
                    self.pre_control_table.setItem(i, 1, QTableWidgetItem(order_data["date"]))
                    # 第三列：订单号
                    self.pre_control_table.setItem(i, 2, QTableWidgetItem(order_data["order"]))
                    # 第四列：工单号
                    self.pre_control_table.setItem(i, 3, QTableWidgetItem(order_data["work_order"]))
                    # 第五列：备注
                    self.pre_control_table.setItem(i, 4, QTableWidgetItem(order_data["remark"]))
                    # 第六列：状态
                    self.pre_control_table.setItem(i, 5, QTableWidgetItem(order_data["status"]))
            else:
                self.pre_control_table.setItem(0, 0, QTableWidgetItem(""))
                self.pre_control_table.setItem(0, 1, QTableWidgetItem("-"))
                self.pre_control_table.setItem(0, 2, QTableWidgetItem("暂无预备订单"))
                self.pre_control_table.setItem(0, 3, QTableWidgetItem(""))
                self.pre_control_table.setItem(0, 4, QTableWidgetItem(""))
                self.pre_control_table.setItem(0, 5, QTableWidgetItem(""))
            
            # 刷新后更新按钮状态
            self.update_toggle_select_btn()
        except Exception as e:
            logging.error(f"Failed to refresh pre control table: {e}")
    
    def load_shipping_to_edit(self):
        """加载选中的发货订单到编辑框"""
        try:
            selected_items = self.shipping_control_table.selectedItems()
            if selected_items and len(selected_items) >= 2:
                row = selected_items[0].row()
                order_num = self.shipping_control_table.item(row, 1).text()
                remark = self.shipping_control_table.item(row, 2).text()
                
                if order_num and order_num != "当前日期无订单":
                    self.shipping_order_edit.setText(order_num)
                    self.shipping_remark_edit.setText(remark)
        except Exception as e:
            logging.error(f"Failed to load shipping to edit: {e}")
    
    def load_pre_to_edit(self):
        """加载选中的预备订单到编辑框"""
        try:
            selected_items = self.pre_control_table.selectedItems()
            if selected_items and len(selected_items) >= 2:
                row = selected_items[0].row()
                date_str = self.pre_control_table.item(row, 1).text()  # 日期列索引为1
                order_num = self.pre_control_table.item(row, 2).text()  # 订单号列索引为2
                work_order = self.pre_control_table.item(row, 3).text()  # 工单号列索引为3
                remark = self.pre_control_table.item(row, 4).text()  # 备注列索引为4
                
                if order_num and order_num != "暂无预备订单":
                    if date_str == "待定":
                        self.tbd_check.setChecked(True)
                    else:
                        self.tbd_check.setChecked(False)
                        self.pre_date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
                    
                    self.pre_order_edit.setText(order_num)
                    self.pre_work_order_edit.setText(work_order)
                    self.pre_remark_edit.setText(remark)
        except Exception as e:
            logging.error(f"Failed to load pre to edit: {e}")
    
    def add_shipping_order(self):
        """添加发货订单"""
        try:
            date_str = self.shipping_date.date().toString("yyyy-MM-dd")
            order_num = self.shipping_order_edit.text().strip()
            remark = self.shipping_remark_edit.text().strip()
            
            if not order_num:
                QMessageBox.warning(self, "提示", "请输入订单号")
                return
            
            shipping_orders = self.data.setdefault("shipping_orders", {}).setdefault(date_str, [])
            
            # 检查重复
            if any(self.get_order_number(o) == order_num for o in shipping_orders):
                QMessageBox.warning(self, "重复订单", "该订单号已存在！")
                return
            
            shipping_orders.append({"order": order_num, "remark": remark})

            # 保存数据
            save_data(self.data)

            # 更新主窗口显示
            if self.parent():
                self.parent().update_order_tables()

            self.refresh_shipping_control_table()
            
            self.clear_shipping_order_inputs()
            
            QMessageBox.information(self, "成功", "发货订单已添加！")
        except Exception as e:
            logging.error(f"Failed to add shipping order: {e}")
            QMessageBox.critical(self, "错误", f"添加失败：{e}")
    
    def edit_shipping_order(self):
        """编辑发货订单"""
        try:
            selected_items = self.shipping_control_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择要修改的订单")
                return
            
            row = selected_items[0].row()
            date_str = self.shipping_date.date().toString("yyyy-MM-dd")
            order_num = self.shipping_order_edit.text().strip()
            remark = self.shipping_remark_edit.text().strip()
            
            if not order_num:
                QMessageBox.warning(self, "提示", "订单号不能为空")
                return
            
            orders = self.data.get("shipping_orders", {}).get(date_str, [])
            if 0 <= row < len(orders):
                orders[row] = {"order": order_num, "remark": remark}

                # 保存数据
                save_data(self.data)

                # 更新主窗口显示
                if self.parent():
                    self.parent().update_order_tables()

                self.refresh_shipping_control_table()
                self.clear_shipping_order_inputs()
                QMessageBox.information(self, "成功", "订单已修改！")
        except Exception as e:
            logging.error(f"Failed to edit shipping order: {e}")
            QMessageBox.critical(self, "错误", f"修改失败：{e}")
    
    def delete_shipping_order(self):
        """删除发货订单"""
        try:
            selected_items = self.shipping_control_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择要删除的订单")
                return
            
            reply = QMessageBox.question(self, "确认", "确定要删除选中的订单吗？",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            row = selected_items[0].row()
            date_str = self.shipping_date.date().toString("yyyy-MM-dd")
            orders = self.data.get("shipping_orders", {}).get(date_str, [])
            
            if 0 <= row < len(orders):
                orders.pop(row)
                if not orders:
                    del self.data["shipping_orders"][date_str]

                # 保存数据
                save_data(self.data)

                # 更新主窗口显示
                if self.parent():
                    self.parent().update_order_tables()

                self.refresh_shipping_control_table()
                self.clear_shipping_order_inputs()
                QMessageBox.information(self, "成功", "订单已删除！")
        except Exception as e:
            logging.error(f"Failed to delete shipping order: {e}")
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
    
    def add_pre_order(self):
        """添加预备订单"""
        try:
            if self.tbd_check.isChecked():
                date_str = "TBD"
            else:
                date_str = self.pre_date.date().toString("yyyy-MM-dd")
            
            order_num = self.pre_order_edit.text().strip()
            work_order = self.pre_work_order_edit.text().strip()
            remark = self.pre_remark_edit.text().strip()
            
            if not order_num:
                QMessageBox.warning(self, "提示", "请输入订单号")
                return
            
            pre_orders = self.data.setdefault("pre_shipping_orders", {}).setdefault(date_str, [])
            
            # 检查重复
            if any(self.get_order_number(o) == order_num for o in pre_orders):
                QMessageBox.warning(self, "重复订单", "该订单号已存在！")
                return
            
            pre_orders.append({
                "order": order_num,
                "work_order": work_order,
                "remark": remark,
                "status": ORDER_STATUS_PENDING
            })

            # 保存数据
            save_data(self.data)

            # 更新主窗口显示
            if self.parent():
                self.parent().update_order_tables()

            self.refresh_pre_control_table()
            
            self.clear_pre_order_inputs()
            
            QMessageBox.information(self, "成功", "预备订单已添加！")
        except Exception as e:
            logging.error(f"Failed to add pre order: {e}")
            QMessageBox.critical(self, "错误", f"添加失败：{e}")
    
    def edit_pre_order(self):
        """编辑预备订单"""
        try:
            selected_items = self.pre_control_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择要修改的订单")
                return
            
            row = selected_items[0].row()
            
            # 获取表格中显示的订单信息
            old_order_num = self.pre_control_table.item(row, 2).text()  # 订单号列索引为2
            display_date = self.pre_control_table.item(row, 1).text()  # 日期列索引为1
            
            if not old_order_num or old_order_num == "暂无预备订单":
                QMessageBox.warning(self, "提示", "请选择有效的订单")
                return
            
            # 根据显示日期找到原始日期键
            original_date = self.convert_display_date_to_original(display_date)
            
            # 获取新的订单信息
            new_order_num = self.pre_order_edit.text().strip()
            new_work_order = self.pre_work_order_edit.text().strip()
            new_remark = self.pre_remark_edit.text().strip()
            
            if not new_order_num:
                QMessageBox.warning(self, "提示", "订单号不能为空")
                return
            
            # 检查新订单号是否与其他订单重复
            all_pre_orders = self.data.get("pre_shipping_orders", {})
            for date_str, orders in all_pre_orders.items():
                for order in orders:
                    existing_order_num = self.get_order_number(order)
                    if existing_order_num == new_order_num and existing_order_num != old_order_num:
                        QMessageBox.warning(self, "重复订单", "该订单号已存在！")
                        return
            
            # 在所有预备订单中找到对应的订单并更新
            date_key, order_index, old_order = self.find_order_in_data(old_order_num)
            if date_key is not None and order_index >= 0:
                # 获取旧订单的状态
                old_order_data = self.parse_order_data(old_order)
                old_status = old_order_data.get("status", ORDER_STATUS_PENDING)
                
                # 更新订单
                all_pre_orders[date_key][order_index] = {
                    "order": new_order_num,
                    "work_order": new_work_order,
                    "remark": new_remark,
                    "status": old_status
                }

                # 保存数据
                save_data(self.data)

                # 更新主窗口显示
                if self.parent():
                    self.parent().update_order_tables()

                self.refresh_pre_control_table()
                self.clear_pre_order_inputs()
                QMessageBox.information(self, "成功", "订单已修改！")
        except Exception as e:
            logging.error(f"Failed to edit pre order: {e}")
            QMessageBox.critical(self, "错误", f"修改失败：{e}")
    
    def delete_pre_order(self):
        """删除预备订单（支持批量删除勾选的订单）"""
        try:
            # 获取所有勾选的订单
            selected_rows = []
            row_count = self.pre_control_table.rowCount()
            
            for row in range(row_count):
                checkbox = self.pre_control_table.cellWidget(row, 0)
                if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                    order_item = self.pre_control_table.item(row, 2)  # 订单号列索引为2
                    if order_item and order_item.text() and order_item.text() != "暂无预备订单":
                        selected_rows.append(row)
            
            if not selected_rows:
                # 如果没有勾选的，尝试使用选中的行
                selected_items = self.pre_control_table.selectedItems()
                if selected_items:
                    selected_rows = [selected_items[0].row()]
                else:
                    QMessageBox.warning(self, "提示", "请先勾选或选择要删除的订单")
                return
            
            # 确认删除
            order_count = len(selected_rows)
            confirm_msg = f"确定要删除选中的 {order_count} 个订单吗？"
            reply = QMessageBox.question(self, "确认删除", confirm_msg,
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # 收集要删除的订单信息
            orders_to_delete = []
            for row in selected_rows:
                order_item = self.pre_control_table.item(row, 2)
                date_item = self.pre_control_table.item(row, 1)
                if order_item and date_item:
                    order_num = order_item.text()
                    display_date = date_item.text()
                    if order_num and order_num != "暂无预备订单":
                        original_date = self.convert_display_date_to_original(display_date)
                        orders_to_delete.append((order_num, original_date))
            
            if not orders_to_delete:
                QMessageBox.warning(self, "提示", "没有有效的订单可以删除")
                return
            
            # 在所有预备订单中找到对应的订单并删除
            all_pre_orders = self.data.get("pre_shipping_orders", {})
            deleted_count = 0
            
            for order_num, original_date in orders_to_delete:
                # 查找订单
                date_key, order_index, order = self.find_order_in_data(order_num, original_date)
                if date_key is not None and order_index >= 0:
                    # 删除订单
                    orders = all_pre_orders[date_key]
                    orders.pop(order_index)
                    deleted_count += 1

                    # 如果该日期的订单列表为空，删除该日期
                    if not orders:
                        del all_pre_orders[date_key]
            
            if deleted_count > 0:
                # 保存数据
                save_data(self.data)

                # 更新主窗口显示
                if self.parent():
                    self.parent().update_order_tables()

                self.refresh_pre_control_table()
                self.clear_pre_order_inputs()
                QMessageBox.information(self, "成功", f"已删除 {deleted_count} 个订单！")
            else:
                QMessageBox.warning(self, "提示", "未找到要删除的订单")
                
        except Exception as e:
            logging.error(f"Failed to delete pre order: {e}")
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
    
    def generate_qrcode(self, text, size=200):
        """生成二维码图片"""
        if not QRCODE_AVAILABLE:
            return None
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(text)
            qr.make(fit=True)
            
            # 创建二维码图片
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # 转换为QPixmap
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.read())
            return pixmap
        except Exception as e:
            logging.error(f"Failed to generate QR code: {e}")
            return None
    
    def render_pre_order_label(self, painter, order_num, shipping_date, remark, work_order="", custom_texts=None):
        """绘制预备订单标签内容（60mm x 40mm标签）"""
        try:
            # 获取打印页面尺寸（使用QPainter的视口区域，更可靠）
            viewport = painter.viewport()
            page_width = viewport.width()
            page_height = viewport.height()
            
            # 标签尺寸：60mm x 40mm，转换为像素（假设300DPI）
            # 60mm ≈ 708像素，40mm ≈ 472像素
            # 但为了适应不同打印机，使用相对比例
            label_width = int(page_width * 0.9)  # 标签宽度（留边距）
            label_height = int(page_height * 0.9)  # 标签高度（留边距）
            margin = int(label_width * 0.05)  # 左右边距
            gap = int(label_width * 0.02)  # 文字与二维码之间的间距
            
            # 左侧文字起始位置
            text_start_x = margin
            text_start_y = int(label_height * 0.1)  # 顶部边距
            
            # 设置字体（根据标签尺寸调整）
            title_font = QFont("Arial", 14, QFont.Weight.Bold)
            content_font = QFont("Arial", 9)
            remark_font = QFont("Arial", 9)
            
            if not work_order:
                # 无二维码时，放大并居中显示全部文字内容
                title_font_center = QFont("Arial", 18, QFont.Weight.Bold)
                info_font_center = QFont("Arial", 13)
                remark_font_center = QFont("Arial", 11)
                
                lines = [
                    (title_font_center, "发货订单标签"),
                    (info_font_center, f"订单号：{order_num}"),
                    (info_font_center, f"发货日期：{shipping_date}"),
                ]
                if remark:
                    lines.append((remark_font_center, f"备注：{remark}"))
                
                spacing = max(int(label_height * 0.06), 16)
                text_rect_width = label_width - 2 * margin
                available_height = label_height - 2 * text_start_y
                
                metrics = []
                total_height = 0
                for font, text in lines:
                    fm = QFontMetrics(font)
                    line_height = int(fm.height() * 1.6)
                    metrics.append((font, text, line_height))
                    total_height += line_height
                
                if metrics:
                    total_height += spacing * (len(metrics) - 1)
                    current_y = text_start_y + max(0, (available_height - total_height) // 2)
                    
                    for font, text, line_height in metrics:
                        painter.setFont(font)
                        painter.drawText(
                            text_start_x,
                            int(current_y),
                            text_rect_width,
                            line_height,
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                            text,
                        )
                        current_y += line_height + spacing
                return
            
            # 右侧二维码位置（靠右对齐以避免遮挡文字）
            qr_size = min(int(label_height * 0.8), int(label_width * 0.3))  # 二维码大小
            qr_size = int(qr_size * 1.06)
            qr_area_width = qr_size
            
            char_width = QFontMetrics(remark_font).horizontalAdvance("中")
            char_shift = char_width * 4
            base_qr_start_x = label_width - margin - qr_size
            qr_start_x = min(base_qr_start_x + char_shift, label_width - margin)
            qr_start_x = max(qr_start_x, text_start_x + int(label_width * 0.6) + gap)
            qr_start_y = text_start_y
            
            # 左侧文字区域宽度
            text_area_width = qr_start_x - gap - text_start_x
            min_text_width = int(label_width * 0.6)
            if text_area_width < min_text_width:
                qr_start_x = text_start_x + min_text_width + gap
                text_area_width = min_text_width
            
            # 计算行高和间距
            line_height = int(label_height / 6)  # 根据标签高度分配
            current_y = text_start_y
            
            title_text = "发货订单标签"
            order_line = f"订单号：{order_num}"
            date_line = f"发货日期：{shipping_date}"
            remark_line = f"备注：{remark}" if remark else ""

            if custom_texts:
                title_text = custom_texts.get("title", title_text)
                order_line = custom_texts.get("order", order_line)
                date_line = custom_texts.get("date", date_line)
                if "remark" in custom_texts:
                    remark_line = custom_texts["remark"]

            # 绘制标题（左侧）
            painter.setFont(title_font)
            painter.drawText(text_start_x, current_y, text_area_width, line_height,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, title_text)
            current_y += int(line_height * 1.2)
            
            # 绘制订单号（左侧）
            painter.setFont(content_font)
            painter.drawText(text_start_x, current_y, text_area_width, line_height,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, order_line)
            current_y += int(line_height * 1.1)
            
            # 绘制发货日期（左侧）
            painter.setFont(content_font)
            painter.drawText(text_start_x, current_y, text_area_width, line_height,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, date_line)
            current_y += int(line_height * 1.1)
            
            # 绘制备注（如果有，左侧）
            if remark_line:
                painter.setFont(remark_font)
                painter.drawText(text_start_x, current_y, text_area_width, line_height,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, remark_line)
                current_y += int(line_height * 1.1)
            
            # 绘制二维码（右侧）- 如果有工单号
            if work_order:
                if QRCODE_AVAILABLE:
                    qr_pixmap = self.generate_qrcode(work_order, qr_size)
                    if qr_pixmap and not qr_pixmap.isNull():
                        # 计算二维码垂直居中位置
                        qr_y = qr_start_y + (label_height - qr_size) // 2
                        painter.drawPixmap(qr_start_x, qr_y, qr_size, qr_size, qr_pixmap)
                    else:
                        # 如果二维码生成失败，显示文字提示
                        painter.setFont(remark_font)
                        painter.drawText(qr_start_x, qr_start_y, qr_area_width, label_height,
                                       Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                                       "工单号：\n" + work_order)
                else:
                    # 如果没有安装qrcode库，显示文字
                    painter.setFont(remark_font)
                    painter.drawText(qr_start_x, qr_start_y, qr_area_width, label_height,
                                   Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                                   "工单号：\n" + work_order)
                
        except Exception as e:
            logging.error(f"Failed to render label: {e}")
            raise
    
    def get_printer_settings(self):
        """获取保存的打印设置，如果没有则返回默认设置"""
        print_settings = self.data.get("print_settings", {})
        
        # 创建打印机对象
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        
        # 加载页面大小设置
        page_size_id = print_settings.get("page_size", QPageSize.PageSizeId.A4)
        page_size = QPageSize(page_size_id)
        printer.setPageSize(page_size)
        
        # 加载页面方向设置
        orientation_str = print_settings.get("orientation", "Portrait")
        if orientation_str == "Landscape":
            orientation = QPageLayout.Orientation.Landscape
        else:
            orientation = QPageLayout.Orientation.Portrait
        printer.setPageOrientation(orientation)
        
        # 加载打印机名称（如果已设置）
        printer_name = print_settings.get("printer_name")
        if printer_name:
            printer.setPrinterName(printer_name)
        
        return printer
    
    def save_printer_settings(self, printer):
        """保存打印设置"""
        print_settings = {
                "page_size": printer.pageLayout().pageSize().id(),
                "orientation": "Landscape" if printer.pageLayout().orientation() == QPageLayout.Orientation.Landscape else "Portrait",
                "printer_name": printer.printerName()
        }
        self.data["print_settings"] = print_settings
    
    def print_pre_order_label(self):
        """打印预备订单标签（带预览，支持多选）"""
        try:
            # 重要：在打印操作前，先保存当前self.data的订单数据，防止丢失
            backup_pre_orders = copy.deepcopy(self.data.get("pre_shipping_orders", {}))
            backup_shipping_orders = copy.deepcopy(self.data.get("shipping_orders", {}))
            logging.debug(f"Backup before print: {sum(len(o) for o in backup_pre_orders.values())} pre_orders, "
                         f"{sum(len(o) for o in backup_shipping_orders.values())} shipping_orders")
            
            # 获取所有勾选的订单
            selected_orders = []
            row_count = self.pre_control_table.rowCount()
            
            for row in range(row_count):
                checkbox = self.pre_control_table.cellWidget(row, 0)
                if checkbox and isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                    # 获取订单信息
                    display_date_item = self.pre_control_table.item(row, 1)
                    order_num_item = self.pre_control_table.item(row, 2)
                    work_order_item = self.pre_control_table.item(row, 3)
                    remark_item = self.pre_control_table.item(row, 4)
                    
                    if display_date_item and order_num_item:
                        display_date = display_date_item.text()
                        order_num = order_num_item.text()
                        work_order = work_order_item.text() if work_order_item else ""
                        remark = remark_item.text() if remark_item else ""
                        
                        if order_num and order_num != "暂无预备订单":
                            shipping_date = display_date if display_date != "待定" else "待定日期"
                            selected_orders.append({
                                "order_num": order_num,
                                "work_order": work_order,
                                "shipping_date": shipping_date,
                                "remark": remark
                            })
            
            if not selected_orders:
                QMessageBox.warning(self, "提示", "请先勾选要打印的订单")
                return
            
            # 加载保存的打印设置
            printer = self.get_printer_settings()
            
            # 显示可编辑的打印预览对话框
            preview_dialog = EditablePrintPreviewDialog(self, selected_orders, printer)
            preview_dialog.exec()
            
            # 重要：打印操作后，检查并恢复订单数据，防止丢失
            current_pre_count = sum(len(orders) for orders in self.data.get("pre_shipping_orders", {}).values())
            backup_pre_count = sum(len(orders) for orders in backup_pre_orders.values())
            current_shipping_count = sum(len(orders) for orders in self.data.get("shipping_orders", {}).values())
            backup_shipping_count = sum(len(orders) for orders in backup_shipping_orders.values())
            
            if current_pre_count < backup_pre_count or current_shipping_count < backup_shipping_count:
                logging.warning(f"Data loss detected after print! Restoring from backup. "
                              f"Before: {backup_pre_count} pre, {backup_shipping_count} ship. "
                              f"After: {current_pre_count} pre, {current_shipping_count} ship")
                self.data["pre_shipping_orders"] = backup_pre_orders
                self.data["shipping_orders"] = backup_shipping_orders
                logging.info(f"Restored: {sum(len(o) for o in self.data['pre_shipping_orders'].values())} pre_orders, "
                           f"{sum(len(o) for o in self.data['shipping_orders'].values())} shipping_orders")
                
        except Exception as e:
            logging.error(f"Failed to print pre order label: {e}")
            QMessageBox.critical(self, "错误", f"打印失败：{e}")
    
    def toggle_pre_control_status(self, row, col):
        """控制面板中双击切换预备订单状态"""
        try:
            # 获取表格中显示的订单信息
            order_num = self.pre_control_table.item(row, 2).text()  # 订单号列索引改为2
            display_date = self.pre_control_table.item(row, 1).text()  # 日期列索引改为1
            
            if not order_num or order_num == "暂无预备订单":
                return
            
            # 根据显示日期找到原始日期键
            original_date = self.convert_display_date_to_original(display_date)
            
            # 在所有预备订单中找到对应的订单
            all_pre_orders = self.data.get("pre_shipping_orders", {})
            target_order = None
            target_date = None
            target_index = -1
            
            for date_str, orders in all_pre_orders.items():
                for i, order in enumerate(orders):
                    if isinstance(order, dict):
                        if order.get("order", "") == order_num:
                            target_order = order
                            target_date = date_str
                            target_index = i
                            break
                    else:
                        if str(order) == order_num:
                            target_order = {"order": str(order), "status": ORDER_STATUS_PENDING}
                            target_date = date_str
                            target_index = i
                            break
                if target_order:
                    break
            
            if not target_order:
                QMessageBox.warning(self, "错误", "未找到对应的订单数据")
                return
            
            # 显示状态切换对话框
            dialog = OrderStatusDialog(self, order_num, target_date, target_order)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_status, new_date = dialog.get_result()
                
                # 更新订单状态
                target_order["status"] = new_status
                
                # 检查是否需要移动订单到不同日期
                if new_date != target_date:
                    # 从当前日期移除订单
                    all_pre_orders[target_date].pop(target_index)
                    if not all_pre_orders[target_date]:
                        del all_pre_orders[target_date]
                    
                    # 添加到新日期
                    all_pre_orders.setdefault(new_date, []).append(target_order)
                    
                    # 显示更新信息
                    if new_date == "TBD":
                        QMessageBox.information(self, "订单更新",
                            f"订单 '{order_num}' 已移动到待定日期\n状态：{ORDER_STATUS_DISPLAY.get(new_status, '未知')}")
                    else:
                        QMessageBox.information(self, "订单更新",
                            f"订单 '{order_num}' 已移动到 {new_date}\n状态：{ORDER_STATUS_DISPLAY.get(new_status, '未知')}")
                else:
                    # 只更新状态，不移动日期
                    all_pre_orders[target_date][target_index] = target_order
                    status_text = ORDER_STATUS_DISPLAY.get(new_status, "未知")
                    QMessageBox.information(self, "状态更新",
                        f"订单 '{order_num}' 状态已更新为：\n{status_text}")
                
                # 保存数据
                save_data(self.data)

                # 更新主窗口显示
                if self.parent():
                    self.parent().update_order_tables()
                
                # 刷新表格
                self.refresh_pre_control_table()
                    
        except Exception as e:
            logging.error(f"Failed to toggle pre control status: {e}")
            QMessageBox.warning(self, "错误", f"切换状态失败：{e}")
    
    def get_data(self):
        """获取数据"""
        # 保存每日任务数据（月视图）
        if hasattr(self, 'monthly_view'):
            self.data["daily_tasks"] = self.monthly_view.get_task_data()
        # 保存工作计划（原始界面）
        elif hasattr(self, 'work_entries'):
            for i, entry in self.work_entries.items():
                if "work_plan" not in self.data:
                    self.data["work_plan"] = {}
                self.data["work_plan"][str(i)] = entry.text().strip()
        
        # 保存系统设置
        if hasattr(self, 'interval_combo'):
            interval_map = {"30分钟": 30, "1小时": 60, "2小时": 120, "4小时": 240}
            self.data["reminder_interval"] = interval_map.get(self.interval_combo.currentText(), 120)
        if hasattr(self, 'reminder_check'):
            self.data["reminder_enabled"] = self.reminder_check.isChecked()
        if hasattr(self, 'startup_check'):
            self.data["startup_enabled"] = self.startup_check.isChecked()
        
        # 保存Excel导入目录
        if hasattr(self, 'excel_dir_edit'):
            self.data["excel_dir"] = self.excel_dir_edit.text().strip()
        
        # 重要：确保保留所有订单数据（包括在控制面板中修改的订单）
        # self.data已经包含了所有订单数据（因为添加/编辑/删除订单时直接修改了self.data）
        # 确保pre_shipping_orders和shipping_orders存在
        if "pre_shipping_orders" not in self.data:
            self.data["pre_shipping_orders"] = {}
        if "shipping_orders" not in self.data:
            self.data["shipping_orders"] = {}
        
        # 记录当前订单数量（用于调试）
        pre_count = sum(len(orders) for orders in self.data.get("pre_shipping_orders", {}).values())
        shipping_count = sum(len(orders) for orders in self.data.get("shipping_orders", {}).values())
        logging.debug(f"get_data(): self.data contains {pre_count} pre_orders and {shipping_count} shipping_orders")
        
        # 返回深拷贝，确保包含所有数据，避免外部修改影响内部数据
        result = copy.deepcopy(self.data)
        
        # 验证深拷贝是否包含所有订单数据
        result_pre_count = sum(len(orders) for orders in result.get("pre_shipping_orders", {}).values())
        result_shipping_count = sum(len(orders) for orders in result.get("shipping_orders", {}).values())
        if result_pre_count != pre_count or result_shipping_count != shipping_count:
            logging.error(f"Data loss in deepcopy! Original: {pre_count} pre, {shipping_count} ship. "
                         f"Copy: {result_pre_count} pre, {result_shipping_count} ship")
            # 如果深拷贝丢失数据，直接使用self.data的引用（不推荐，但作为最后手段）
            result["pre_shipping_orders"] = self.data.get("pre_shipping_orders", {})
            result["shipping_orders"] = self.data.get("shipping_orders", {})
        
        return result

class TaskManagerDialog(QDialog):
    """任务管理弹窗"""
    def __init__(self, date, tasks, parent=None):
        super().__init__(parent)
        self.date = date
        self.date_str = date.strftime("%Y-%m-%d")
        self.tasks = copy.deepcopy(tasks)
        self.setWindowTitle(f"管理任务 - {self.date_str}")
        self.setFixedSize(460, 420)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        date_label = QLabel(f"📅 {self.date.strftime('%Y年%m月%d日')}")
        date_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #1F2937;")
        layout.addWidget(date_label)

        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E40AF;
            }
        """)
        self.task_list.itemDoubleClicked.connect(lambda _: self.edit_task())
        layout.addWidget(self.task_list, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        add_btn = create_styled_button("➕ 添加", "#10B981", "#059669")
        add_btn.clicked.connect(self.add_task)
        btn_layout.addWidget(add_btn)

        edit_btn = create_styled_button("✏️ 编辑", "#3B82F6", "#2563EB")
        edit_btn.clicked.connect(self.edit_task)
        btn_layout.addWidget(edit_btn)

        delete_btn = create_styled_button("🗑️ 删除", "#F87171", "#DC2626")
        delete_btn.clicked.connect(self.delete_task)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        cancel_btn = create_styled_button("取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        action_layout.addWidget(cancel_btn)

        ok_btn = create_styled_button("完成", "#10B981", "#059669")
        ok_btn.clicked.connect(self.accept)
        action_layout.addWidget(ok_btn)

        layout.addLayout(action_layout)

        self.refresh_task_list()

    def refresh_task_list(self):
        self.task_list.clear()
        if not self.tasks:
            placeholder = QListWidgetItem("📝 暂无任务，点击“添加”开始记录")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QColor("#9CA3AF"))
            self.task_list.addItem(placeholder)
            return

        priority_symbols = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for task in self.tasks:
            symbol = priority_symbols.get(task.get("priority", "medium"), "🟡")
            time_text = (task.get("time") or "").strip() or "全天"
            content = task.get("content", "未命名任务")
            completed = task.get("completed", False)
            icon = "✅" if completed else "⬜"
            item_text = f"{icon} {symbol} [{time_text}] {content}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, task)
            if completed:
                item.setForeground(QColor("#9CA3AF"))
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
            self.task_list.addItem(item)

    def add_task(self):
        dialog = TaskAddDialog(self.date, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task_data = dialog.get_task_data()
            if task_data:
                task_data["date"] = self.date_str
                self.tasks.append(task_data)
                self.refresh_task_list()

    def edit_task(self):
        item = self.task_list.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.information(self, "提示", "请先选择要编辑的任务")
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        dialog = TaskEditDialog(task, self.date, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_task = dialog.get_task_data()
            if updated_task:
                updated_task["date"] = self.date_str
                for i, t in enumerate(self.tasks):
                    if t.get("id") == updated_task.get("id"):
                        self.tasks[i] = updated_task
                        break
                self.refresh_task_list()

    def delete_task(self):
        item = self.task_list.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.information(self, "提示", "请先选择要删除的任务")
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除任务「{task.get('content', '未命名任务')}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.tasks = [t for t in self.tasks if t.get("id") != task.get("id")]
            self.refresh_task_list()

    def get_tasks(self):
        return copy.deepcopy(self.tasks)

# -------------------- 其他对话框 (简化版) --------------------
class LifeSettingsDialog(QDialog):
    """生命设置对话框"""
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = data.copy()
        self.setWindowTitle("生命倒计时设置")
        self.setFixedSize(350, 200)
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QFormLayout(self)

        # 生日设置
        life_settings = self.data.get("life_settings", {})
        self.birthday_edit = QDateEdit()
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDisplayFormat("yyyy-MM-dd")

        # 设置生日值
        birthday_str = life_settings.get("birthday", "")
        if birthday_str:
            try:
                birthday_date = datetime.date.fromisoformat(birthday_str)
                self.birthday_edit.setDate(QDate(birthday_date.year, birthday_date.month, birthday_date.day))
            except (ValueError, AttributeError):
                # 如果生日格式错误，设置为空
                self.birthday_edit.setDate(QDate.currentDate().addYears(-25))
        else:
            # 默认设置为25岁前
            self.birthday_edit.setDate(QDate.currentDate().addYears(-25))

        layout.addRow("🎂 生日：", self.birthday_edit)

        # 理想寿命
        self.ideal_age_spin = QSpinBox()
        self.ideal_age_spin.setRange(0, MAX_AGE)
        self.ideal_age_spin.setValue(life_settings.get("ideal_age", 80))
        layout.addRow("🎯 理想寿命：", self.ideal_age_spin)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = create_styled_button("✅ 确定", "#10B981", "#059669")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        cancel_btn = create_styled_button("❌ 取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addRow(button_layout)
    
    def get_data(self):
        """获取数据"""
        # 获取生日
        birthday_qdate = self.birthday_edit.date()
        birthday = datetime.date(birthday_qdate.year(), birthday_qdate.month(), birthday_qdate.day())
        ia = self.ideal_age_spin.value()

        # 计算当前年龄
        today = datetime.date.today()
        ca = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))

        # 验证
        if ca < 0:
            QMessageBox.warning(self, "提醒", "生日不能设置为未来日期！")
            return self.data
        if ca >= ia:
            QMessageBox.warning(self, "提醒", f"根据生日计算当前年龄为{ca}岁，不能大于或等于理想寿命{ia}岁！")
            return self.data

        self.data.setdefault("life_settings", {})
        self.data["life_settings"]["birthday"] = birthday.isoformat()
        self.data["life_settings"]["ideal_age"] = ia
        # 移除旧的current_age字段（如果存在）
        if "current_age" in self.data["life_settings"]:
            del self.data["life_settings"]["current_age"]
        # 重置每日递减基线
        self.data["life_settings"]["remain_base_days"] = max(ia - ca, 0) * 365
        self.data["life_settings"]["remain_base_date"] = datetime.date.today().isoformat()
        return self.data

class CustomReminderDialog(QDialog):
    """自定义提醒对话框"""
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = data.copy()
        self.setWindowTitle("自定义提醒设置")
        self.setMinimumSize(600, 600)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 提醒列表
        self.reminder_table = QTableWidget()
        self.reminder_table.setColumnCount(4)
        self.reminder_table.setHorizontalHeaderLabels(["日期类型", "时间", "提醒内容", "状态"])
        self.reminder_table.horizontalHeader().setStretchLastSection(True)
        self.reminder_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reminder_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.reminder_table.itemSelectionChanged.connect(self.load_reminder_to_edit)
        layout.addWidget(self.reminder_table)
        
        # 编辑区域
        edit_group = QGroupBox("✏️ 编辑提醒")
        edit_layout = QFormLayout(edit_group)
        
        # 时间选择
        time_layout = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(9, 0))
        time_layout.addWidget(self.time_edit)
        time_layout.addStretch()
        edit_layout.addRow("提醒时间：", time_layout)
        
        # 日期类型选择
        date_type_layout = QHBoxLayout()
        self.date_type_group = QButtonGroup()
        self.daily_radio = QRadioButton("每日重复")
        self.daily_radio.setChecked(True)
        self.specific_radio = QRadioButton("特定日期")
        self.date_type_group.addButton(self.daily_radio, 0)
        self.date_type_group.addButton(self.specific_radio, 1)
        date_type_layout.addWidget(self.daily_radio)
        date_type_layout.addWidget(self.specific_radio)
        date_type_layout.addStretch()
        edit_layout.addRow("日期类型：", date_type_layout)
        
        # 特定日期选择
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setEnabled(False)
        self.specific_radio.toggled.connect(lambda checked: self.date_edit.setEnabled(checked))
        edit_layout.addRow("特定日期：", self.date_edit)
        
        # 提醒内容
        self.content_edit = QLineEdit()
        self.content_edit.setPlaceholderText("输入提醒内容...")
        edit_layout.addRow("提醒内容：", self.content_edit)
        
        # 启用开关
        self.enabled_check = QCheckBox("启用此提醒")
        self.enabled_check.setChecked(True)
        edit_layout.addRow("", self.enabled_check)
        
        layout.addWidget(edit_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        add_btn = create_styled_button("➕ 添加", "#10B981", "#059669")
        add_btn.clicked.connect(self.add_reminder)
        btn_layout.addWidget(add_btn)
        
        del_btn = create_styled_button("🗑️ 删除", "#EF4444", "#DC2626")
        del_btn.clicked.connect(self.delete_reminder)
        btn_layout.addWidget(del_btn)
        
        test_btn = create_styled_button("🧪 测试", "#F59E0B", "#D97706")
        test_btn.clicked.connect(self.test_reminder)
        btn_layout.addWidget(test_btn)
        
        btn_layout.addStretch()
        
        save_btn = create_styled_button("💾 保存", "#2563EB", "#1D4ED8")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = create_styled_button("❌ 取消", "#6B7280", "#4B5563")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载提醒列表
        self.refresh_reminder_table()
    
    def refresh_reminder_table(self):
        """刷新提醒列表"""
        try:
            custom_reminders = self.data.get("custom_reminders", [])
            self.reminder_table.setRowCount(len(custom_reminders))
            
            for i, reminder in enumerate(custom_reminders):
                time_str = reminder.get("time", "")
                content = reminder.get("content", "")
                enabled = reminder.get("enabled", True)
                date_type = reminder.get("date_type", "daily")
                specific_date = reminder.get("specific_date", "")
                
                # 日期类型显示
                if date_type == "daily":
                    date_display = "每日重复"
                else:
                    date_display = f"特定日期: {specific_date}"
                
                # 状态显示
                status = "✅ 启用" if enabled else "❌ 禁用"
                
                self.reminder_table.setItem(i, 0, QTableWidgetItem(date_display))
                self.reminder_table.setItem(i, 1, QTableWidgetItem(time_str))
                self.reminder_table.setItem(i, 2, QTableWidgetItem(content))
                self.reminder_table.setItem(i, 3, QTableWidgetItem(status))
        except Exception as e:
            logging.error(f"Failed to refresh reminder table: {e}")
    
    def load_reminder_to_edit(self):
        """加载选中的提醒到编辑框"""
        try:
            selected_items = self.reminder_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            custom_reminders = self.data.get("custom_reminders", [])
            
            if 0 <= row < len(custom_reminders):
                reminder = custom_reminders[row]
                
                # 加载时间
                time_str = reminder.get("time", "09:00")
                self.time_edit.setTime(QTime.fromString(time_str, "HH:mm"))
                
                # 加载日期类型
                date_type = reminder.get("date_type", "daily")
                if date_type == "daily":
                    self.daily_radio.setChecked(True)
                else:
                    self.specific_radio.setChecked(True)
                    specific_date = reminder.get("specific_date", "")
                    if specific_date:
                        try:
                            date_obj = datetime.date.fromisoformat(specific_date)
                            self.date_edit.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
                        except:
                            pass
                
                # 加载内容和状态
                self.content_edit.setText(reminder.get("content", ""))
                self.enabled_check.setChecked(reminder.get("enabled", True))
        except Exception as e:
            logging.error(f"Failed to load reminder to edit: {e}")
    
    def add_reminder(self):
        """添加提醒"""
        try:
            time_str = self.time_edit.time().toString("HH:mm")
            content = self.content_edit.text().strip()
            enabled = self.enabled_check.isChecked()
            date_type = "daily" if self.daily_radio.isChecked() else "specific"
            specific_date = ""
            
            if not content:
                QMessageBox.warning(self, "提示", "请输入提醒内容")
                return
            
            if date_type == "specific":
                qdate = self.date_edit.date()
                specific_date = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"
            
            reminder = {
                "time": time_str,
                "content": content,
                "enabled": enabled,
                "date_type": date_type,
                "specific_date": specific_date
            }
            
            self.data.setdefault("custom_reminders", []).append(reminder)
            self.refresh_reminder_table()
            
            # 清空输入
            self.time_edit.setTime(QTime(9, 0))
            self.content_edit.clear()
            self.enabled_check.setChecked(True)
            self.daily_radio.setChecked(True)
            
            QMessageBox.information(self, "成功", f"提醒 '{content}' 已添加！")
        except Exception as e:
            logging.error(f"Failed to add reminder: {e}")
            QMessageBox.critical(self, "错误", f"添加失败：{e}")
    
    def delete_reminder(self):
        """删除提醒"""
        try:
            selected_items = self.reminder_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "提示", "请先选择要删除的提醒")
                return
            
            row = selected_items[0].row()
            custom_reminders = self.data.get("custom_reminders", [])
            
            if 0 <= row < len(custom_reminders):
                reminder = custom_reminders[row]
                content = reminder.get("content", "")
                
                reply = QMessageBox.question(self, "确认", f"确定要删除提醒 '{content}' 吗？",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return
                
                del custom_reminders[row]
                self.refresh_reminder_table()
                
                # 清空输入
                self.time_edit.setTime(QTime(9, 0))
                self.content_edit.clear()
                self.enabled_check.setChecked(True)
                self.daily_radio.setChecked(True)
                
                QMessageBox.information(self, "成功", f"提醒 '{content}' 已删除！")
        except Exception as e:
            logging.error(f"Failed to delete reminder: {e}")
            QMessageBox.critical(self, "错误", f"删除失败：{e}")
    
    def test_reminder(self):
        """测试提醒"""
        try:
            content = self.content_edit.text().strip()
            if not content:
                QMessageBox.warning(self, "提示", "请先输入提醒内容")
                return
            
            time_str = self.time_edit.time().toString("HH:mm")
            
            # 使用气泡通知显示测试提醒
            bubble = BubbleNotification(
                title="自定义提醒测试",
                message=f"⏰ 时间：{time_str}\n📝 内容：{content}",
                duration=6000  # 6秒后自动关闭
            )
            bubble.show_notification()
            
        except Exception as e:
            logging.error(f"Failed to test reminder: {e}")
            QMessageBox.critical(self, "错误", f"测试失败：{e}")
    
    def get_data(self):
        """获取数据"""
        return self.data

class DraggableLabel(QLineEdit):
    """可拖动的标签（实际上是可以编辑的文本框）"""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setReadOnly(False)
        self.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: 2px dashed #3B82F6;
                border-radius: 4px;
                padding: 4px;
                color: #000000;
            }
            QLineEdit:focus {
                border: 2px solid #2563EB;
                background-color: rgba(59, 130, 246, 0.1);
            }
        """)
        self._drag_start_pos = None
        self._is_dragging = False
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._is_dragging = False
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._drag_start_pos is not None:
            current_pos = event.position().toPoint()
            delta = current_pos - self._drag_start_pos
            if abs(delta.x()) > 5 or abs(delta.y()) > 5:
                self._is_dragging = True
                # 移动标签位置
                new_pos = self.pos() + delta
                self.move(new_pos)
                self._drag_start_pos = current_pos
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        if not self._is_dragging:
            # 如果只是点击，允许编辑
            self.setFocus()
        self._is_dragging = False
        super().mouseReleaseEvent(event)

class EditablePrintPreviewDialog(QDialog):
    """可编辑的打印预览对话框"""
    def __init__(self, parent, orders_data, printer):
        super().__init__(parent)
        self.control_panel = parent  # ControlPanelDialog引用
        # 获取真正的MainWindow实例（用于调用render_pre_order_label）
        self.main_window = parent.parent() if hasattr(parent, 'parent') and parent.parent() else None
        self.orders_data = orders_data
        self.printer = printer
        self.current_order_index = 0
        self.text_elements = {}  # 存储文本元素及其位置
        self.edited_orders = {}  # 存储已编辑的订单数据
        
        self.setWindowTitle(f"可编辑打印预览 - 管路发货标签 ({len(orders_data)}个订单)")
        self.setMinimumSize(800, 600)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 页面导航
        self.page_label = QLabel(f"第 {self.current_order_index + 1} / {len(self.orders_data)} 个订单")
        self.page_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        toolbar.addWidget(self.page_label)
        
        toolbar.addStretch()
        
        prev_btn = create_styled_button("◀ 上一个", "#6B7280", "#4B5563")
        prev_btn.clicked.connect(self.prev_order)
        toolbar.addWidget(prev_btn)
        
        next_btn = create_styled_button("下一个 ▶", "#6B7280", "#4B5563")
        next_btn.clicked.connect(self.next_order)
        toolbar.addWidget(next_btn)
        
        toolbar.addStretch()
        
        # 重置按钮
        reset_btn = create_styled_button("🔄 重置位置", "#F59E0B", "#D97706")
        reset_btn.clicked.connect(self.reset_positions)
        toolbar.addWidget(reset_btn)
        
        # 打印按钮
        print_btn = create_styled_button("🖨️ 打印", "#10B981", "#059669")
        print_btn.clicked.connect(self.print_order)
        toolbar.addWidget(print_btn)
        
        # 关闭按钮
        close_btn = create_styled_button("关闭", "#6B7280", "#4B5563")
        close_btn.clicked.connect(self.accept)
        toolbar.addWidget(close_btn)
        
        layout.addLayout(toolbar)
        
        # 预览区域（模拟A4纸张）
        preview_frame = QFrame()
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #F3F4F6;
                border: 2px solid #D1D5DB;
                border-radius: 8px;
            }
        """)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建可滚动的预览区域
        scroll = QScrollArea()
        scroll.setWidget(preview_frame)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(500)
        
        # 预览画布（实际可编辑区域）- 60mm x 40mm标签比例
        # 60:40 = 3:2，所以宽度600，高度400
        self.preview_canvas = QWidget(preview_frame)
        self.preview_canvas.setMinimumSize(600, 400)
        self.preview_canvas.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #9CA3AF;
            }
        """)
        preview_layout.addWidget(self.preview_canvas)
        
        layout.addWidget(scroll)
        
        # 说明文字
        info_label = QLabel("💡 提示：点击文本可以编辑，拖动文本可以移动位置")
        info_label.setStyleSheet("color: #6B7280; font-size: 10pt; padding: 5px;")
        layout.addWidget(info_label)
        
        # 加载当前订单
        self.load_current_order()
    
    def load_current_order(self):
        """加载当前订单的预览"""
        # 清除现有元素
        for element in self.text_elements.values():
            element.setParent(None)
            element.deleteLater()
        self.text_elements.clear()
        
        if self.current_order_index >= len(self.orders_data):
            return
        
        # 优先使用已编辑的数据，否则使用原始数据
        order = self.edited_orders.get(self.current_order_index, 
                                       self.orders_data[self.current_order_index].copy())
        order_num = order.get("order_num", "")
        work_order = order.get("work_order", "")
        shipping_date = order.get("shipping_date", "")
        remark = order.get("remark", "")
        custom_texts = order.get("custom_texts", {})
        
        # 获取画布尺寸（60mm x 40mm比例：600 x 400）
        canvas_width = 600
        canvas_height = 400
        
        # 计算左右分区
        # 左侧文字区域：约占60%，右侧二维码区域：约占35%
        text_area_width = int(canvas_width * 0.60)
        qr_area_width = int(canvas_width * 0.35)
        margin = int(canvas_width * 0.05)  # 左右边距
        
        # 左侧文字起始位置
        text_start_x = margin
        text_start_y = int(canvas_height * 0.1)  # 顶部边距
        
        # 右侧二维码位置
        qr_start_x = margin + text_area_width + int(canvas_width * 0.05)
        qr_start_y = text_start_y
        qr_size = min(qr_area_width, int(canvas_height * 0.8))  # 二维码大小
        
        # 计算行高和间距
        line_height = int(canvas_height / 6)
        current_y = text_start_y
        
        # 标题（左侧）
        title_label = DraggableLabel(custom_texts.get("title", "管路发货专用"), self.preview_canvas)
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setGeometry(QRect(text_start_x, current_y, text_area_width, int(line_height * 1.2)))
        title_label.show()
        self.text_elements["title"] = title_label
        current_y += int(line_height * 1.2)
        
        # 订单号（左侧）
        order_label = DraggableLabel(custom_texts.get("order", f"订单号：{order_num}"), self.preview_canvas)
        order_label.setFont(QFont("Arial", 9))  # 使用和备注相同的字号
        order_label.setGeometry(QRect(text_start_x, current_y, text_area_width, int(line_height * 1.1)))
        order_label.show()
        self.text_elements["order"] = order_label
        current_y += int(line_height * 1.1)
        
        # 发货日期（左侧）
        date_label = DraggableLabel(custom_texts.get("date", f"发货日期：{shipping_date}"), self.preview_canvas)
        date_label.setFont(QFont("Arial", 9))  # 使用和备注相同的字号
        date_label.setGeometry(QRect(text_start_x, current_y, text_area_width, int(line_height * 1.1)))
        date_label.show()
        self.text_elements["date"] = date_label
        current_y += int(line_height * 1.1)
        
        # 备注（如果有，左侧）
        remark_text_default = f"备注：{remark}" if remark else "备注："
        remark_text = custom_texts.get("remark", remark_text_default)
        remark_label = DraggableLabel(remark_text, self.preview_canvas)
        remark_label.setFont(QFont("Arial", 9))
        remark_label.setGeometry(QRect(text_start_x, current_y, text_area_width, int(line_height * 1.1)))
        remark_label.show()
        self.text_elements["remark"] = remark_label
        
        # 二维码（右侧）- 如果有工单号
        if work_order:
            if QRCODE_AVAILABLE:
                # 生成二维码（使用control_panel的方法）
                qr_pixmap = self.control_panel.generate_qrcode(work_order, qr_size)
                if qr_pixmap and not qr_pixmap.isNull():
                    # 创建标签显示二维码
                    qr_label = QLabel(self.preview_canvas)
                    qr_label.setPixmap(qr_pixmap)
                    qr_y = qr_start_y + (canvas_height - qr_size) // 2
                    qr_label.setGeometry(QRect(qr_start_x, qr_y, qr_size, qr_size))
                    qr_label.setScaledContents(True)
                    qr_label.show()
                    self.text_elements["qrcode"] = qr_label
                else:
                    # 如果二维码生成失败，显示文字
                    qr_text_label = QLabel(f"工单号：\n{work_order}", self.preview_canvas)
                    qr_text_label.setFont(QFont("Arial", 9))
                    qr_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    qr_text_label.setGeometry(QRect(qr_start_x, qr_start_y, qr_area_width, canvas_height - qr_start_y))
                    qr_text_label.setWordWrap(True)
                    qr_text_label.show()
                    self.text_elements["qrcode"] = qr_text_label
            else:
                # 如果没有安装qrcode库，显示文字
                qr_text_label = QLabel(f"工单号：\n{work_order}", self.preview_canvas)
                qr_text_label.setFont(QFont("Arial", 9))
                qr_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                qr_text_label.setGeometry(QRect(qr_start_x, qr_start_y, qr_area_width, canvas_height - qr_start_y))
                qr_text_label.setWordWrap(True)
                qr_text_label.show()
                self.text_elements["qrcode"] = qr_text_label
        
        # 更新页面标签
        self.page_label.setText(f"第 {self.current_order_index + 1} / {len(self.orders_data)} 个订单")
    
    def prev_order(self):
        """上一个订单"""
        if self.current_order_index > 0:
            # 保存当前订单的编辑内容
            self.get_current_order_data()
            self.current_order_index -= 1
            self.load_current_order()
    
    def next_order(self):
        """下一个订单"""
        if self.current_order_index < len(self.orders_data) - 1:
            # 保存当前订单的编辑内容
            self.get_current_order_data()
            self.current_order_index += 1
            self.load_current_order()
    
    def reset_positions(self):
        """重置所有文本元素位置"""
        self.load_current_order()
    
    def get_current_order_data(self):
        """获取当前订单的编辑后数据"""
        order = self.orders_data[self.current_order_index].copy()
        
        custom_texts = {}

        # 从文本元素中提取数据
        if "order" in self.text_elements:
            order_text = self.text_elements["order"].text()
            custom_texts["order"] = order_text
            if "：" in order_text:
                order["order_num"] = order_text.split("：", 1)[1]
        
        if "work_order" in self.text_elements:
            work_text = self.text_elements["work_order"].text()
            if "：" in work_text:
                order["work_order"] = work_text.split("：", 1)[1]
        
        if "date" in self.text_elements:
            date_text = self.text_elements["date"].text()
            custom_texts["date"] = date_text
            if "：" in date_text:
                order["shipping_date"] = date_text.split("：", 1)[1]
        
        if "remark" in self.text_elements:
            remark_text = self.text_elements["remark"].text()
            custom_texts["remark"] = remark_text
            if "：" in remark_text:
                order["remark"] = remark_text.split("：", 1)[1]

        if "title" in self.text_elements:
            custom_texts["title"] = self.text_elements["title"].text()
        
        # 过滤空白自定义文本
        custom_texts_clean = {k: v for k, v in custom_texts.items() if v is not None}
        if custom_texts_clean:
            order["custom_texts"] = custom_texts_clean
        elif "custom_texts" in order:
            order.pop("custom_texts", None)
        
        # 保存已编辑的订单数据
        self.edited_orders[self.current_order_index] = order
        
        return order
    
    def print_order(self):
        """打印所有订单（使用编辑后的数据）"""
        try:
            # 保存当前订单的编辑内容
            self.get_current_order_data()
            
            # 创建打印绘制函数
            def print_page(printer):
                painter = QPainter()
                if not painter.begin(printer):
                    QMessageBox.critical(self, "错误", "无法开始打印")
                    return
                try:
                    # 使用所有订单（已编辑的优先，否则使用原始数据）
                    for i, original_order in enumerate(self.orders_data):
                        if i > 0:
                            printer.newPage()
                        
                        # 获取订单数据（优先使用已编辑的）
                        order_data = self.edited_orders.get(i, original_order)
                        
                        # 绘制标签（使用control_panel的方法）
                        self.control_panel.render_pre_order_label(
                            painter,
                            order_data["order_num"],
                            order_data["shipping_date"],
                            order_data.get("remark", ""),
                            order_data.get("work_order", ""),
                            order_data.get("custom_texts")
                        )
                finally:
                    painter.end()
            
            # 显示打印对话框
            print_dialog = QPrintDialog(self.printer, self)
            if print_dialog.exec() == QDialog.DialogCode.Accepted:
                print_page(self.printer)
                QMessageBox.information(self, "成功", f"已发送 {len(self.orders_data)} 个订单的打印任务！")
            
        except Exception as e:
            logging.error(f"Failed to print: {e}")
            QMessageBox.critical(self, "错误", f"打印失败：{e}")

class StorageSettingsDialog(QDialog):
    """存储设置对话框"""
    def __init__(self, parent, data):
        super().__init__(parent)
        self.data = data.copy()
        self.parent_window = parent
        self.setWindowTitle("数据存储设置")
        self.setMinimumSize(500, 400)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 当前存储信息
        info_group = QGroupBox("📊 当前存储信息")
        info_layout = QVBoxLayout(info_group)
        
        # 存储路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("存储位置："))
        self.path_label = QLabel(SAVE_DIR)
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #2563EB; font-weight: bold;")
        path_layout.addWidget(self.path_label, 1)
        info_layout.addLayout(path_layout)
        
        # 存储统计
        stats_layout = QHBoxLayout()
        
        # 数据大小
        size_info = self.get_storage_size()
        size_label = QLabel(f"📦 数据大小: {size_info}")
        size_label.setStyleSheet("font-weight: bold; color: #059669;")
        stats_layout.addWidget(size_label)
        
        # 文件数量
        file_count = self.get_file_count()
        count_label = QLabel(f"📄 文件数量: {file_count}")
        count_label.setStyleSheet("font-weight: bold; color: #8B5CF6;")
        stats_layout.addWidget(count_label)
        
        info_layout.addLayout(stats_layout)
        layout.addWidget(info_group)
        
        # 数据管理
        manage_group = QGroupBox("🛠️ 数据管理")
        manage_layout = QHBoxLayout(manage_group)
        
        # 备份按钮
        backup_btn = create_styled_button("📦 备份数据", "#2563EB", "#1D4ED8")
        backup_btn.clicked.connect(self.backup_data)
        manage_layout.addWidget(backup_btn)
        
        # 恢复按钮
        restore_btn = create_styled_button("📥 恢复数据", "#F59E0B", "#D97706")
        restore_btn.clicked.connect(self.restore_data)
        manage_layout.addWidget(restore_btn)
        
        # 打开文件夹按钮
        open_btn = create_styled_button("📂 打开存储文件夹", "#8B5CF6", "#7C3AED")
        open_btn.clicked.connect(self.open_storage_folder)
        manage_layout.addWidget(open_btn)
        
        manage_layout.addStretch()
        layout.addWidget(manage_group)
        
        # 更改存储位置
        change_group = QGroupBox("⚙️ 更改存储位置")
        change_layout = QVBoxLayout(change_group)
        
        change_layout.addWidget(QLabel("选择新的数据存储位置："))
        
        path_input_layout = QHBoxLayout()
        self.new_path_edit = QLineEdit()
        self.new_path_edit.setReadOnly(True)
        self.new_path_edit.setText(SAVE_DIR)
        path_input_layout.addWidget(self.new_path_edit, 1)
        
        browse_btn = create_styled_button("📁 浏览", "#2563EB", "#1D4ED8")
        browse_btn.clicked.connect(self.browse_path)
        path_input_layout.addWidget(browse_btn)
        
        change_layout.addLayout(path_input_layout)
        
        # 警告信息
        warning_label = QLabel("⚠️ 更改存储位置后，程序会迁移现有数据到新位置")
        warning_label.setStyleSheet("color: #D97706; padding: 8px; background-color: #FFF3CD; border-radius: 4px;")
        warning_label.setWordWrap(True)
        change_layout.addWidget(warning_label)
        
        # 应用更改按钮和关闭按钮横向排列
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 应用更改按钮
        apply_btn = create_styled_button("✅ 应用更改", "#10B981", "#059669")
        apply_btn.clicked.connect(self.change_storage_path)
        button_layout.addWidget(apply_btn)
        
        # 关闭按钮
        close_btn = create_styled_button("关闭", "#6B7280", "#4B5563")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        change_layout.addLayout(button_layout)
        layout.addWidget(change_group)
        
        layout.addStretch()
    
    def get_storage_size(self):
        """获取存储大小"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(SAVE_DIR):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                    except:
                        pass
            
            # 转换为可读格式
            if total_size < 1024:
                return f"{total_size} B"
            elif total_size < 1024 * 1024:
                return f"{total_size / 1024:.2f} KB"
            else:
                return f"{total_size / (1024 * 1024):.2f} MB"
        except:
            return "未知"
    
    def get_file_count(self):
        """获取文件数量"""
        try:
            count = 0
            for root, dirs, files in os.walk(SAVE_DIR):
                count += len(files)
            return str(count)
        except:
            return "0"
    
    def browse_path(self):
        """浏览路径"""
        try:
            path = QFileDialog.getExistingDirectory(self, "选择数据存储位置", SAVE_DIR)
            if path:
                self.new_path_edit.setText(path)
        except Exception as e:
            logging.error(f"Failed to browse path: {e}")
    
    def backup_data(self):
        """备份数据"""
        try:
            backup_path = QFileDialog.getExistingDirectory(self, "选择备份保存位置", 
                                                          os.path.expanduser("~"))
            if not backup_path:
                return
            
            import zipfile
            import shutil
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_path, f"daily_reminder_backup_{timestamp}.zip")
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(SAVE_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, SAVE_DIR)
                        zipf.write(file_path, arcname)
            
            QMessageBox.information(self, "备份成功", f"数据已备份到：\n{backup_file}")
            
        except Exception as e:
            logging.error(f"Failed to backup data: {e}")
            QMessageBox.critical(self, "错误", f"备份失败：{e}")
    
    def restore_data(self):
        """恢复数据"""
        try:
            backup_file, _ = QFileDialog.getOpenFileName(
                self, "选择备份文件",
                os.path.expanduser("~"),
                "ZIP文件 (*.zip)"
            )
            
            if not backup_file:
                return
            
            reply = QMessageBox.question(
                self, "确认恢复",
                f"确定从备份恢复数据吗？\n\n{backup_file}\n\n"
                "⚠️ 警告：当前数据将被覆盖！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            import zipfile
            import shutil
            
            # 先备份当前数据
            self.backup_data()
            
            # 解压备份
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(SAVE_DIR)
            
            QMessageBox.information(self, "恢复成功", "数据恢复成功！\n程序需要重启以应用更改。")
            self.accept()
            
        except Exception as e:
            logging.error(f"Failed to restore data: {e}")
            QMessageBox.critical(self, "错误", f"恢复失败：{e}")
    
    def open_storage_folder(self):
        """打开存储文件夹"""
        try:
            if sys.platform == "win32":
                os.startfile(SAVE_DIR)
            elif sys.platform == "darwin":
                os.system(f'open "{SAVE_DIR}"')
            else:
                os.system(f'xdg-open "{SAVE_DIR}"')
        except Exception as e:
            logging.error(f"Failed to open storage folder: {e}")
            QMessageBox.warning(self, "错误", f"无法打开文件夹：{e}")
    
    def change_storage_path(self):
        """更改存储路径"""
        try:
            new_path = self.new_path_edit.text().strip()
            old_path = SAVE_DIR
            
            if not new_path:
                QMessageBox.warning(self, "提示", "请选择有效的存储路径")
                return
            
            if new_path == old_path:
                QMessageBox.information(self, "提示", "新路径与当前路径相同")
                return
            
            reply = QMessageBox.question(
                self, "确认更改",
                f"确定要将数据存储位置从：\n\n{old_path}\n\n更改到：\n\n{new_path}\n\n"
                f"程序会自动迁移现有数据，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            import shutil
            
            # 创建新目录
            os.makedirs(new_path, exist_ok=True)
            
            # 迁移数据
            migrated_count = 0
            for item in os.listdir(old_path):
                src = os.path.join(old_path, item)
                dst = os.path.join(new_path, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    migrated_count += 1
                elif os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    migrated_count += 1
            
            # 保存新路径配置
            if set_storage_path(new_path):
                QMessageBox.information(
                    self, "迁移完成",
                    f"数据迁移成功！\n\n"
                    f"已迁移 {migrated_count} 个文件/目录\n"
                    f"新存储位置：{new_path}\n\n"
                    f"程序需要重启以应用更改"
                )
                self.accept()
            else:
                QMessageBox.critical(self, "错误", "保存新路径配置失败")
            
        except Exception as e:
            logging.error(f"Failed to change storage path: {e}")
            QMessageBox.critical(self, "错误", f"更改存储路径失败：{e}")

# -------------------- 主程序入口 --------------------
def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("每日工作提醒")
    app.setOrganizationName("坤坤")
    app.setApplicationVersion("3.0.0")
    
    # 设置全局字体
    font = QFont("Microsoft YaHei UI", 9)  # 字体缩小
    app.setFont(font)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
