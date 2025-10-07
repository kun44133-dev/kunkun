# daily_reminder_beautiful.py
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import datetime
import json
import os
import sys
import threading
import glob
import logging
from tkinter import font

# 可选依赖项处理
try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pystray
    from pystray import MenuItem as item
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

try:
    from tkcalendar import DateEntry
    CALENDAR_AVAILABLE = True
except ImportError:
    DateEntry = None
    CALENDAR_AVAILABLE = False

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

try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False

# -------------------- 全局配置 --------------------
HOME = os.path.expanduser("~")
SAVE_DIR = os.path.join(HOME, "DailyReminderData")
os.makedirs(SAVE_DIR, exist_ok=True)

DATA_FILE = os.path.join(SAVE_DIR, "data.json")
ACT_FILE = os.path.join(SAVE_DIR, "activation.json")
LOG_FILE = os.path.join(SAVE_DIR, "app.log")

TRIAL_DAYS = 7
ACTIVATION_KEY = "YKJ-2025-KEY"
MAX_AGE = 100

# 简洁字体配置
FONTS = {
    "default": ("Microsoft YaHei UI", 9),       # 默认字体 - 更小更简洁
    "title": ("Microsoft YaHei UI", 14, "bold"), # 标题字体 - 减小尺寸
    "subtitle": ("Microsoft YaHei UI", 12, "bold"), # 副标题字体
    "section": ("Microsoft YaHei UI", 10, "bold"),  # 章节标题字体 - 减小尺寸
    "content": ("Microsoft YaHei UI", 9),       # 内容字体 - 减小尺寸
    "work_content": ("Microsoft YaHei UI", 11), # 工作内容字体 - 比content字体大20%
    "button": ("Microsoft YaHei UI", 9, "bold"), # 按钮字体 - 减小尺寸
    "table_header": ("Microsoft YaHei UI", 9, "bold"), # 表格标题字体
    "table_content": ("Microsoft YaHei UI", 9), # 表格内容字体
    "small": ("Microsoft YaHei UI", 8),         # 小字体 - 更小
    "large": ("Microsoft YaHei UI", 11)         # 大字体 - 减小尺寸
}

# 简洁清爽配色方案
COLORS = {
    "primary": "#2563EB",           # 更现代的蓝色
    "primary_dark": "#1D4ED8",      # 深蓝色
    "secondary": "#F59E0B",         # 温暖的橙色
    "success": "#10B981",           # 清新的绿色
    "warning": "#F59E0B",           # 橙色警告
    "error": "#EF4444",             # 红色错误
    "bg_main": "#F8FAFC",           # 更清爽的背景色
    "bg_card": "#FFFFFF",           # 纯白卡片
    "text_primary": "#1F2937",      # 深灰色文字
    "text_secondary": "#6B7280",    # 中灰色文字
    "accent": "#8B5CF6",            # 紫色强调色
    "gradient_start": "#F1F5F9",    # 淡蓝灰色渐变开始
    "gradient_end": "#E2E8F0"       # 淡蓝灰色渐变结束
}

# 默认数据
default_data = {
    "work_plan": {str(i): f"周{i+1}：待填写工作内容" for i in range(7)},
    "shipping_orders": {},
    "pre_shipping_orders": {},
    "reminder_enabled": True,
    "reminder_interval": 120,
    "startup_enabled": False,
    "excel_dir": os.path.join(SAVE_DIR, "orders_import"),
    "life_settings": {"current_age": 25, "ideal_age": 80},
    "festival_reminders": {"01-01": "元旦", "02-14": "情人节", "05-01": "劳动节", "10-01": "国庆节"},
    "clock_settings": {
        "clock_in_enabled": False,
        "clock_out_enabled": False,
        "clock_in_time": "09:00",
        "clock_out_time": "18:00",
        "clock_in_message": "上班时间到了，记得打卡哦！",
        "clock_out_message": "下班时间到了，记得打卡哦！"
    },
    "custom_reminders": []
}

os.makedirs(default_data["excel_dir"], exist_ok=True)

# 全局变量
app = None

# 设置日志
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# -------------------- 数据管理 --------------------
def load_data():
    """加载数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, value in default_data.items():
                    if key not in data:
                        data[key] = value
                return data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error loading data: {e}")
            return default_data.copy()
        except Exception as e:
            logging.error(f"Failed to load data: {e}")
            return default_data.copy()
    else:
        return default_data.copy()

def save_data(d):
    """保存数据"""
    try:
        if os.path.exists(DATA_FILE):
            backup_file = DATA_FILE + ".backup"
            import shutil
            shutil.copy(DATA_FILE, backup_file)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)
    except PermissionError:
        logging.error(f"Permission denied saving data to {DATA_FILE}")
        messagebox.showerror("Error", f"No permission to save data to {DATA_FILE}")
    except json.JSONEncodeError as e:
        logging.error(f"JSON encode error saving data: {e}")
        messagebox.showerror("Error", "Data format error, cannot save")
    except Exception as e:
        logging.error(f"Failed to save data: {e}")
        messagebox.showerror("Error", f"Failed to save data: {e}")

# -------------------- 激活管理 --------------------
def load_activation():
    """加载激活信息"""
    if os.path.exists(ACT_FILE):
        try:
            with open(ACT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error loading activation: {e}")
            return {}
        except Exception as e:
            logging.error(f"Failed to load activation: {e}")
            return {}
    return {}

def save_activation(act_data):
    """保存激活信息"""
    try:
        with open(ACT_FILE, "w", encoding="utf-8") as f:
            json.dump(act_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Failed to save activation: {e}")

def check_trial(parent=None):
    """检查试用状态"""
    act_data = load_activation()
    if act_data.get("activated"):
        return True
    
    start = act_data.get("trial_start")
    if not start:
        act_data["trial_start"] = datetime.date.today().isoformat()
        save_activation(act_data)
        return True
    
    try:
        start_date = datetime.date.fromisoformat(start)
    except ValueError:
        act_data["trial_start"] = datetime.date.today().isoformat()
        save_activation(act_data)
        return True
    
    days_used = (datetime.date.today() - start_date).days
    if days_used < TRIAL_DAYS:
        return True
    else:
        if parent:
            messagebox.showwarning("Trial Ended", "Trial period has ended, please enter activation code!", parent=parent)
        return False

def activate_program():
    """激活程序"""
    code = simpledialog.askstring("Activation", "Enter activation code:")
    if code is None:
        return
    if code.strip() == ACTIVATION_KEY:
        act_data = load_activation()
        act_data["activated"] = True
        save_activation(act_data)
        messagebox.showinfo("Activation Successful", "Program activated successfully!")
        if app:
            app.update_reminder_text()
    else:
        messagebox.showerror("Activation Failed", "Invalid activation code!")

# -------------------- 启动设置 --------------------
def set_startup(enable: bool):
    """设置自动启动"""
    if sys.platform != "win32":
        return
    try:
        import winreg
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

# -------------------- UI工具函数 --------------------
def create_modern_button(parent, text, command=None, bg_color=None, width=None, font_size=9, button_type="primary"):
    """创建统一现代化按钮"""
    # 按钮类型颜色定义
    button_colors = {
        "primary": COLORS["primary"],
        "success": COLORS["success"], 
        "warning": COLORS["warning"],
        "error": COLORS["error"],
        "secondary": COLORS["secondary"],
        "accent": COLORS["accent"]
    }
    
    # 按钮类型悬停颜色
    hover_colors = {
        "primary": COLORS["primary_dark"],
        "success": "#059669",  # 深绿色
        "warning": "#D97706",  # 深橙色
        "error": "#DC2626",    # 深红色
        "secondary": "#D97706", # 深橙色
        "accent": "#7C3AED"     # 深紫色
    }
    
    if bg_color is None:
        bg_color = button_colors.get(button_type, COLORS["primary"])
    
    # 统一按钮样式
    btn = tk.Button(parent, text=text, command=command,
                    bg=bg_color, fg="white",
                    activebackground=hover_colors.get(button_type, COLORS["primary_dark"]),
                    relief="flat", borderwidth=0,
                    font=FONTS["button"],
                    cursor="hand2", 
                    padx=20, pady=8,  # 增加内边距
                    bd=0,  # 无边框
                    highlightthickness=0)  # 无高亮边框
    
    if width:
        btn.config(width=width)
    
    # 悬停效果
    def on_enter(e):
        btn.config(bg=hover_colors.get(button_type, COLORS["primary_dark"]))
    def on_leave(e):
        btn.config(bg=bg_color)
    
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn

def create_card_frame(parent, title=None):
    """创建简洁卡片框架"""
    card = tk.Frame(parent, bg=COLORS["bg_card"], relief="flat", bd=0)
    if title:
        title_frame = tk.Frame(card, bg=COLORS["gradient_start"], height=30)
        title_frame.pack(fill="x", padx=0, pady=(0,0))
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=title, font=FONTS["section"],
                 bg=COLORS["gradient_start"], fg=COLORS["text_primary"]).pack(pady=6)
    return card

def center_window(win, width, height):
    """将窗口居中到鼠标所在的屏幕"""
    try:
        logging.info(f"Centering window with size {width}x{height}")
        win.update_idletasks()  # Ensure window geometry is updated
        
        # 获取屏幕尺寸和鼠标位置
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        mouse_x = win.winfo_pointerx()
        mouse_y = win.winfo_pointery()
        
        # 检测鼠标所在的屏幕（用于多显示器设置）
        # 如果没有多显示器信息则回退到主屏幕
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # 通过查找包含鼠标的显示器来调整多显示器设置
        if SCREENINFO_AVAILABLE and sys.platform == 'win32':
            monitors = get_monitors()
            for monitor in monitors:
                if (monitor.x <= mouse_x < monitor.x + monitor.width and
                    monitor.y <= mouse_y < monitor.y + monitor.height):
                    x = monitor.x + (monitor.width - width) // 2
                    y = monitor.y + (monitor.height - height) // 2
                    break
        
        # 应用几何设置并确保窗口可见
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.deiconify()  # Ensure window is not minimized
        win.lift()  # Bring window to front
        logging.info(f"Window centered at position ({x}, {y})")
    except Exception as e:
        logging.error(f"Failed to center window: {e}")
        # 回退到基本居中
        win.geometry(f"{width}x{height}+100+100")

# -------------------- 工具函数 --------------------
def today_str():
    """获取今天的字符串"""
    return datetime.date.today().isoformat()

def compute_life_ui(data):
    """计算生命进度UI，剩余天数每日递减。"""
    try:
        life_settings = data.get("life_settings", {})
        current_age_years = int(life_settings.get("current_age", 36))
        ideal_age_years = int(life_settings.get("ideal_age", 70))

        if ideal_age_years <= 0:
            ideal_age_years = 80

        # 如果缺失则初始化每日递减基线
        today = datetime.date.today()
        base_days_key = "remain_base_days"
        base_date_key = "remain_base_date"

        if base_days_key not in life_settings or base_date_key not in life_settings:
            life_settings[base_days_key] = max(ideal_age_years - current_age_years, 0) * 365
            life_settings[base_date_key] = today.isoformat()
            save_data(data)

        # 安全解析基准日期
        try:
            base_date = datetime.date.fromisoformat(life_settings.get(base_date_key, today.isoformat()))
        except ValueError:
            base_date = today

        base_remaining_days = int(life_settings.get(base_days_key, 0))
        delta_days = (today - base_date).days
        remaining_days = max(base_remaining_days - max(delta_days, 0), 0)

        # 基于当前年龄的生命阶段（仅显示）
        if current_age_years < 12:
            stage_icon = "👶"
            stage_text = "幼年"
        elif current_age_years < 30:
            stage_icon = "🧑"
            stage_text = "青年"
        elif current_age_years < 50:
            stage_icon = "👨"
            stage_text = "中年"
        else:
            stage_icon = "👴"
            stage_text = "老年"

        # 使用基于天数的进度以允许平滑的每日变化
        ideal_total_days = max(ideal_age_years, 1) * 365
        elapsed_days = max(ideal_total_days - remaining_days, 0)
        value = min(max(elapsed_days / ideal_total_days, 0.0), 1.0)

        return value, stage_icon, stage_text, f"余生 {remaining_days:,} 天"
    except Exception as e:
        logging.error(f"Failed to compute life UI: {e}")
        return 0.3, "🧑", "青年", "余生 20,075 天"

# -------------------- Excel导入 --------------------
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
                
                if order not in data[key][date_iso]:
                    data[key][date_iso].append(order)
                    count += 1
            
            wb.close()
        except Exception as e:
            logging.error(f"Failed to read Excel file {f}: {e}")
    return count

# -------------------- Life Progress Canvas --------------------
class BeautifulLifeCanvas(tk.Canvas):
    """Beautified life progress canvas"""
    def __init__(self, parent, width=700, height=70, **kwargs):
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                         bg=COLORS["bg_card"], **kwargs)
        self._value = 0.0
        self._stage_icon = "🧑"
        self._stage_text = "青年"
        self._days_text = "余生 20,075 天"
        self._width = width
        self._height = height
        self._radius = 15
        self.bind("<Configure>", self.on_resize)

    def set_values(self, value, stage_icon, stage_text, days_text):
        """Set values"""
        self._value = max(0.0, min(1.0, value))
        self._stage_icon = stage_icon
        self._stage_text = stage_text
        self._days_text = days_text
        self.after_idle(self.redraw)

    def on_resize(self, event):
        """Handle canvas resize"""
        self._width = event.width
        self._height = event.height
        self.redraw()

    def redraw(self):
        """Redraw canvas"""
        try:
            self.delete("all")
            w = max(self.winfo_width(), self._width)
            h = max(self.winfo_height(), self._height)
            
            w = max(w, 400)
            h = max(h, 60)
            
            logging.info("Drawing life progress bar")
            
            # Background progress bar
            self.create_rounded_rect(100, 12, w-130, h-12,
                                     radius=self._radius, fill="#F5F5F5", outline="#E0E0E0", width=2)
            logging.info("Background progress bar drawn")
            
            # Fill progress (gradient effect)
            fill_w = int((w-230) * self._value)
            if fill_w > 8:
                for i in range(0, fill_w, 2):
                    t = i / max(1, fill_w-1)
                    if t < 0.5:
                        r, g, b = int(100 + 155*t*2), 255, 100
                    else:
                        r, g, b = 255, int(255 - 155*(t-0.5)*2), 100
                    
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    x_pos = 100 + i
                    if x_pos < w-130:
                        self.create_line(x_pos, 15, x_pos, h-15, fill=color, width=2)
            logging.info("Progress fill drawn")
            
            # 进度百分比文本
            percent_text = f"{int(self._value*100)}%"
            self.create_text(w/2+1, h/2+1, text=percent_text, font=FONTS["large"], fill="#CCCCCC")
            self.create_text(w/2, h/2, text=percent_text, font=FONTS["large"], fill=COLORS["text_primary"])
            logging.info("Progress percentage drawn")
            
            # 生命阶段图标和文本（固定在进度条左侧）- 简化设计
            self.create_rounded_rect(15, 15, 85, h-15, radius=6,
                                    fill="white", outline=COLORS["primary"], width=1)
            self.create_text(32, h/2, text=self._stage_icon, font=FONTS["large"])
            self.create_text(58, h/2, text=self._stage_text, font=FONTS["large"], fill=COLORS["text_primary"])
            logging.info(f"Life stage drawn: {self._stage_icon} {self._stage_text}")
            
            # 剩余天数（固定在画布最右侧，无背景）
            text_font = font.Font(family="Microsoft YaHei UI", size=12)
            text_width = text_font.measure(self._days_text)
            days_text_x = w - 15 - text_width
            if days_text_x > 100:
                self.create_text(days_text_x, h/2, text=self._days_text, font=FONTS["large"],
                                 fill=COLORS["text_primary"], anchor="w")
                logging.info(f"Remaining days drawn: {self._days_text} at x={days_text_x}")
        except Exception as e:
            logging.error(f"Failed to draw life canvas: {e}")

    def create_rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        """创建圆角矩形"""
        points = [x1+radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

# -------------------- 主应用程序类 --------------------
class DailyReminderApp:
    """每日提醒应用程序"""
    def __init__(self):
        self.data = load_data()
        self.reminder_after_id = None
        self.tray_icon_obj = None
        self.tray_thread = None
        self.root = None
        
        self.work_entries = {}
        self.so_date = None
        self.so_entry = None
        self.so_listbox = None
        self.pre_date = None
        self.pre_entry = None
        self.pre_listbox = None
        self.excel_dir_var = None
        self.interval_options = []
        self.interval_combo = None
        self.custom_interval_entry = None
        self.reminder_chk_var = None
        self.startup_chk_var = None
        self.tree_shipping = None
        self.tree_pre = None
        self.life_expanded = True
        self.life_canvas_frame = None
        self.resize_timer = None
        self.clock_in_timer = None
        self.clock_out_timer = None
        self.custom_reminder_timers = {}  # 存储自定义提醒的定时器
        
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        self.root = tk.Tk()
        self.root.title("每日工作提醒 - 专业版")
        self.root.configure(bg=COLORS["bg_main"])
        
        window_w, window_h = 580, 720
        # 立即设置初始几何尺寸
        self.root.geometry(f"{window_w}x{window_h}")
        # 强制窗口更新
        self.root.update_idletasks()
        # 延迟居中直到UI完全初始化
        self.root.after(100, lambda: center_window(self.root, window_w, window_h))
        
        self.create_life_section()
        self.create_reminder_section()
        self.create_bottom_buttons()
        self.create_menu()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Configure>", self.on_window_resize)
        # 绑定窗口大小变化事件
        self.root.bind("<Button-1>", self.on_window_resize)
        self.root.bind("<B1-Motion>", self.on_window_resize)

    def on_window_resize(self, event):
        """Handle window resize with debouncing"""
        if event.widget == self.root:
            self.life_canvas.redraw()
            # 使用防抖机制，避免频繁调整
            if self.resize_timer:
                self.root.after_cancel(self.resize_timer)
            self.resize_timer = self.root.after(50, self.adjust_table_columns)
            # 确保底部按钮区域保持固定尺寸
            self.root.after(100, self.fix_bottom_buttons)

    def create_life_section(self):
        """Create life progress section with expand/collapse functionality"""
        life_card = tk.Frame(self.root, bg=COLORS["bg_card"], relief="flat", bd=0)
        life_card.pack(fill="x", padx=12, pady=(8,4))
        
        # 可点击的标题栏
        title_frame = tk.Frame(life_card, bg=COLORS["gradient_start"], height=30)
        title_frame.pack(fill="x", padx=1, pady=(1,0))
        title_frame.pack_propagate(False)
        
        # 标题和展开/收起按钮
        title_content = tk.Frame(title_frame, bg=COLORS["gradient_start"])
        title_content.pack(fill="x", padx=8, pady=6)
        
        # 左侧占位符，用于平衡布局
        left_spacer = tk.Frame(title_content, bg=COLORS["gradient_start"], width=20)
        left_spacer.pack(side="left")
        
        # 居中的标题
        self.life_title_label = tk.Label(title_content, text="⏰ 纯牛马生命值", 
                                        font=FONTS["section"],
                                        bg=COLORS["gradient_start"], fg=COLORS["text_primary"],
                                        cursor="hand2")
        self.life_title_label.pack(side="left", expand=True)
        
        # 右侧的展开/收起按钮
        self.life_toggle_btn = tk.Label(title_content, text="▼", 
                                       font=("Arial", 10, "bold"),
                                       bg=COLORS["gradient_start"], fg=COLORS["text_primary"],
                                       cursor="hand2")
        self.life_toggle_btn.pack(side="right")
        
        # 生命进度画布区域
        self.life_canvas_frame = tk.Frame(life_card, bg=COLORS["bg_card"])
        self.life_canvas_frame.pack(fill="x", padx=12, pady=8)
        
        self.life_canvas = BeautifulLifeCanvas(self.life_canvas_frame, width=750, height=70)
        self.life_canvas.pack(fill="x")
        
        # 绑定点击事件
        self.life_title_label.bind("<Button-1>", self.toggle_life_section)
        self.life_toggle_btn.bind("<Button-1>", self.toggle_life_section)
        title_frame.bind("<Button-1>", self.toggle_life_section)

    def toggle_life_section(self, event=None):
        """Toggle life progress section expand/collapse"""
        try:
            self.life_expanded = not self.life_expanded
            
            if self.life_expanded:
                # 展开
                self.life_canvas_frame.pack(fill="x", padx=15, pady=10)
                self.life_toggle_btn.config(text="▼")
            else:
                # 收起
                self.life_canvas_frame.pack_forget()
                self.life_toggle_btn.config(text="▶")
                
        except Exception as e:
            logging.error(f"Failed to toggle life section: {e}")

    def adjust_table_columns(self):
        """Adjust table column widths based on window size"""
        try:
            # 延迟执行，确保窗口大小变化完成后再调整
            self.root.after_idle(self._do_adjust_table_columns)
        except Exception as e:
            logging.error(f"Failed to schedule table column adjustment: {e}")
    
    def _do_adjust_table_columns(self):
        """Actually adjust table column widths and heights"""
        try:
            # 获取主窗口尺寸
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            
            if window_width < 200 or window_height < 200:  # 窗口太小，跳过调整
                return
                
            # 计算表格可用宽度（减去边距和滚动条）
            available_width = window_width - 90  # 减去左右边距和滚动条宽度
            
            # 使用固定高度，确保底部按钮有足够空间
            shipping_height = 6  # 发货订单表格固定6行
            pre_height = 8       # 预备发货订单表格固定8行
            
            if hasattr(self, 'tree_shipping') and self.tree_shipping:
                # 发货订单表格：序号列60px，备注列150px，订单号列使用剩余空间
                idx_width = 60
                remark_width = 150
                order_width = max(200, available_width - idx_width - remark_width)  # 减去滚动条宽度
                self.tree_shipping.column("idx", width=idx_width)
                self.tree_shipping.column("order", width=order_width)
                self.tree_shipping.column("remark", width=remark_width)
                # 设置动态高度
                self.tree_shipping.config(height=shipping_height)
            
            if hasattr(self, 'tree_pre') and self.tree_pre:
                # 预备发货订单表格：日期列120px，状态列80px，订单号列使用剩余空间
                date_width = 120
                status_width = 80
                order_width = max(200, available_width - date_width - status_width)  # 减去滚动条宽度
                self.tree_pre.column("date", width=date_width)
                self.tree_pre.column("status", width=status_width)
                self.tree_pre.column("order", width=order_width)
                # 设置动态高度
                self.tree_pre.config(height=pre_height)
                    
        except Exception as e:
            logging.error(f"Failed to adjust table columns: {e}")

    def fix_bottom_buttons(self):
        """Ensure bottom buttons maintain fixed position and centered layout"""
        try:
            # 确保底部按钮框架始终在底部
            if hasattr(self, 'bottom_frame') and self.bottom_frame:
                self.bottom_frame.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)
                # 确保按钮容器居中
                for child in self.bottom_frame.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.place(relx=0.5, rely=0.5, anchor="center")
        except Exception as e:
            logging.error(f"Failed to fix bottom buttons: {e}")

    def create_reminder_section(self):
        """Create main reminder content section with festival reminder"""
        reminder_card = create_card_frame(self.root, "📋 今日工作提醒")
        reminder_card.pack(fill="both", expand=True, padx=12, pady=(4, 60))  # 底部留出60px给按钮
        # 确保容器有足够的高度
        reminder_card.update_idletasks()
        
        # 主文本区域
        self.reminder_text = tk.Text(reminder_card, font=FONTS["content"], wrap="word",
                                     bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                                     padx=16, pady=12, height=5, relief="flat", borderwidth=0,
                                     selectbackground=COLORS["gradient_end"])
        self.reminder_text.pack(fill="x", padx=12, pady=(12,4))
        self.reminder_text.config(state=tk.DISABLED)
        
        # 发货订单表格区域
        shipping_frame = tk.Frame(reminder_card, bg=COLORS["bg_card"], height=160)
        shipping_frame.pack(fill="x", padx=12, pady=(0,4))
        shipping_frame.pack_propagate(False)
        tk.Label(shipping_frame, text="🚚 今日发货订单", font=FONTS["section"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(anchor="w", pady=(0,5))
        
        # 创建发货订单表格和滚动条
        shipping_tree_frame = tk.Frame(shipping_frame, bg=COLORS["bg_card"], height=120, relief="flat", bd=0)
        shipping_tree_frame.pack(fill="x")
        shipping_tree_frame.pack_propagate(False)
        
        # 创建表格容器，添加内部边框效果
        table_container = tk.Frame(shipping_tree_frame, bg="white", relief="flat", bd=0)
        table_container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 创建表格和滚动条
        self.tree_shipping = ttk.Treeview(table_container, columns=("idx", "order", "remark"), show="headings", height=6)
        self.tree_shipping.heading("idx", text="序号")
        self.tree_shipping.heading("order", text="订单号")
        self.tree_shipping.heading("remark", text="备注")
        self.tree_shipping.column("idx", width=60, anchor="center", minwidth=50)
        self.tree_shipping.column("order", anchor="w", minwidth=200)
        self.tree_shipping.column("remark", anchor="w", minwidth=150)
        
        # 强制设置列分隔符
        self.tree_shipping.configure(show="headings")
        self.tree_shipping.configure(selectmode="browse")
        
        # 垂直滚动条
        shipping_v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_shipping.yview)
        self.tree_shipping.configure(yscrollcommand=shipping_v_scrollbar.set)
        
        # 布局
        self.tree_shipping.pack(side="left", fill="both", expand=True)
        shipping_v_scrollbar.pack(side="right", fill="y")
        
        # 绑定事件来绘制网格线
        self.tree_shipping.bind("<Configure>", lambda e: self.draw_shipping_grid())
        self.tree_shipping.bind("<Button-1>", lambda e: self.draw_shipping_grid())
        self.tree_shipping.bind("<Motion>", lambda e: self.draw_shipping_grid())
        
        
        # 预备发货订单表格区域
        pre_frame = tk.Frame(reminder_card, bg=COLORS["bg_card"], height=160)
        pre_frame.pack(fill="x", padx=12, pady=(0,4))
        pre_frame.pack_propagate(False)
        tk.Label(pre_frame, text="⌛ 预备发货订单", font=FONTS["section"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(anchor="w", pady=(0,5))
        
        # 创建预备发货订单表格和滚动条
        pre_tree_frame = tk.Frame(pre_frame, bg=COLORS["bg_card"], height=120, relief="flat", bd=0)
        pre_tree_frame.pack(fill="x")
        pre_tree_frame.pack_propagate(False)
        
        # 创建表格容器，添加内部边框效果
        pre_table_container = tk.Frame(pre_tree_frame, bg="white", relief="flat", bd=0)
        pre_table_container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 创建表格和滚动条
        self.tree_pre = ttk.Treeview(pre_table_container, columns=("date", "order", "status"), show="headings", height=8)
        self.tree_pre.heading("date", text="发货日期")
        self.tree_pre.heading("order", text="订单号")
        self.tree_pre.heading("status", text="状态")
        self.tree_pre.column("date", width=120, anchor="center", minwidth=100)
        self.tree_pre.column("order", anchor="w", minwidth=200)
        self.tree_pre.column("status", width=80, anchor="center", minwidth=60)
        
        # 强制设置列分隔符
        self.tree_pre.configure(show="headings")
        self.tree_pre.configure(selectmode="browse")
        
        # 垂直滚动条
        pre_v_scrollbar = ttk.Scrollbar(pre_table_container, orient="vertical", command=self.tree_pre.yview)
        self.tree_pre.configure(yscrollcommand=pre_v_scrollbar.set)
        
        # 布局
        self.tree_pre.pack(side="left", fill="both", expand=True)
        pre_v_scrollbar.pack(side="right", fill="y")
        
        # 绑定事件来绘制网格线
        self.tree_pre.bind("<Configure>", lambda e: self.draw_pre_grid())
        self.tree_pre.bind("<Button-1>", lambda e: self.draw_pre_grid())
        self.tree_pre.bind("<Motion>", lambda e: self.draw_pre_grid())
        
        
        self.tree_pre.bind("<Double-1>", self.on_main_pre_double_click)

        self.setup_text_tags()
        
        # 设置表格样式
        self._setup_table_style(self.tree_shipping)
        self._setup_table_style(self.tree_pre)
        
        # ttk.Treeview 不支持直接设置 foreground 和 background
        # 颜色通过样式设置
        
        # 立即刷新表格数据
        self.root.after(100, lambda: self.refresh_order_tables(['main_shipping', 'main_pre']))
        self.root.after(500, lambda: self.refresh_order_tables(['main_shipping', 'main_pre']))
        
        # 强制刷新表格显示
        self.root.after(200, self.force_refresh_table_display)
        
        # 测试数据插入
        self.root.after(300, self.test_table_data)
        
        # 初始化表格列宽和高度
        self.root.after(100, self.adjust_table_columns)
        
        # 立即刷新表格数据 - 模拟控制面板的行为
        # 确保表格创建后立即填充数据
        self.root.after(100, self.refresh_main_tables)
        self.root.after(300, self.refresh_main_tables)
        self.root.after(500, self.refresh_main_tables)

    def _setup_table_style(self, tree_widget):
        """设置表格样式 - 确保文字可见并显示内部网格线"""
        try:
            # 创建样式对象
            style = ttk.Style()
            # 尝试使用不同的主题来显示网格线
            try:
                style.theme_use('vista')  # Vista主题通常有更好的网格线支持
            except:
                try:
                    style.theme_use('winnative')  # Windows原生主题
                except:
                    style.theme_use('clam')  # 回退到clam主题
            
            # 设置简洁样式
            style.configure("Treeview",
                          font=("Microsoft YaHei UI", 9),
                          background="white",
                          foreground="#1F2937",
                          fieldbackground="white",
                          relief="flat",
                          borderwidth=0,
                          show="tree headings")
            
            style.configure("Treeview.Heading",
                          font=("Microsoft YaHei UI", 9, "bold"),
                          background="#F8FAFC",
                          foreground="#374151",
                          relief="flat",
                          borderwidth=0)
            
            # 设置单元格样式 - 简洁设计
            style.configure("Treeview.Cell",
                          relief="flat",
                          borderwidth=0,
                          background="white",
                          foreground="#1F2937",
                          focuscolor="none")
            
            # 设置行样式 - 简洁设计
            style.configure("Treeview.Row",
                          relief="flat",
                          borderwidth=0,
                          background="white")
            
            # 设置列样式 - 简洁设计
            style.configure("Treeview.Column",
                          relief="flat",
                          borderwidth=0)
            
            # 设置选中状态 - 使用更柔和的颜色
            style.map("Treeview",
                     background=[('selected', '#EFF6FF')],
                     foreground=[('selected', '#1E40AF')])
            
            # 设置单元格映射
            style.map("Treeview.Cell",
                     background=[('selected', '#EFF6FF')],
                     foreground=[('selected', '#1E40AF')])
            
            # 强制刷新样式
            style.update()
            
            # 为表格控件设置边框和网格线
            tree_widget.configure(relief="solid", borderwidth=1, show="headings")
            
            # 强制刷新表格显示
            tree_widget.update_idletasks()
            tree_widget.update()
            
            logging.info(f"Table style with internal grid applied successfully to {tree_widget}")
            
        except Exception as e:
            logging.error(f"Failed to setup table style: {e}")
            # 如果样式设置失败，至少确保表格能正常工作
            try:
                tree_widget.configure(relief="solid", borderwidth=1, show="headings")
                logging.info("Applied default Treeview style with borders as fallback")
            except Exception as e2:
                logging.error(f"Failed to apply fallback style: {e2}")

    def draw_shipping_grid(self):
        """绘制发货订单表格的网格线"""
        try:
            # 获取表格尺寸
            width = self.tree_shipping.winfo_width()
            height = self.tree_shipping.winfo_height()
            
            if width <= 1 or height <= 1:
                return
            
            # 获取列宽
            try:
                col1_width = self.tree_shipping.column("idx", "width")
                col2_width = self.tree_shipping.column("order", "width")
                col3_width = self.tree_shipping.column("remark", "width")
            except:
                # 如果获取列宽失败，使用默认值
                col1_width = 60
                col2_width = 200
                col3_width = 150
            
            # 计算列分隔线位置
            x1 = col1_width
            x2 = col1_width + col2_width
            
            # 获取行高
            try:
                item_height = height // 7  # 6行数据 + 1行标题
            except:
                item_height = 20
            
            # 在表格容器上绘制网格线
            table_container = self.tree_shipping.master
            if hasattr(table_container, 'grid_lines'):
                for line in table_container.grid_lines:
                    table_container.delete(line)
            else:
                table_container.grid_lines = []
            
            # 绘制垂直线 - 使用更淡的颜色和细线
            if x1 > 0 and x1 < width:
                line1 = table_container.create_line(x1, 0, x1, height, fill="#E5E7EB", width=1)
                table_container.grid_lines.append(line1)
            if x2 > 0 and x2 < width:
                line2 = table_container.create_line(x2, 0, x2, height, fill="#E5E7EB", width=1)
                table_container.grid_lines.append(line2)
            
            # 绘制水平线 - 使用更淡的颜色和细线
            for i in range(1, 7):  # 6行数据
                y = i * item_height
                if y < height:
                    line = table_container.create_line(0, y, width, y, fill="#E5E7EB", width=1)
                    table_container.grid_lines.append(line)
            
        except Exception as e:
            logging.error(f"Failed to draw shipping grid: {e}")
    
    def draw_pre_grid(self):
        """绘制预备订单表格的网格线"""
        try:
            # 获取表格尺寸
            width = self.tree_pre.winfo_width()
            height = self.tree_pre.winfo_height()
            
            if width <= 1 or height <= 1:
                return
            
            # 获取列宽
            try:
                col1_width = self.tree_pre.column("date", "width")
                col2_width = self.tree_pre.column("order", "width")
                col3_width = self.tree_pre.column("status", "width")
            except:
                # 如果获取列宽失败，使用默认值
                col1_width = 120
                col2_width = 200
                col3_width = 80
            
            # 计算列分隔线位置
            x1 = col1_width
            x2 = col1_width + col2_width
            
            # 获取行高
            try:
                item_height = height // 9  # 8行数据 + 1行标题
            except:
                item_height = 20
            
            # 在表格容器上绘制网格线
            table_container = self.tree_pre.master
            if hasattr(table_container, 'grid_lines'):
                for line in table_container.grid_lines:
                    table_container.delete(line)
            else:
                table_container.grid_lines = []
            
            # 绘制垂直线 - 使用更淡的颜色和细线
            if x1 > 0 and x1 < width:
                line1 = table_container.create_line(x1, 0, x1, height, fill="#E5E7EB", width=1)
                table_container.grid_lines.append(line1)
            if x2 > 0 and x2 < width:
                line2 = table_container.create_line(x2, 0, x2, height, fill="#E5E7EB", width=1)
                table_container.grid_lines.append(line2)
            
            # 绘制水平线 - 使用更淡的颜色和细线
            for i in range(1, 9):  # 8行数据
                y = i * item_height
                if y < height:
                    line = table_container.create_line(0, y, width, y, fill="#E5E7EB", width=1)
                    table_container.grid_lines.append(line)
            
        except Exception as e:
            logging.error(f"Failed to draw pre grid: {e}")

    def force_refresh_table_display(self):
        """强制刷新表格显示，确保文字可见"""
        try:
            # 刷新主窗口表格
            if hasattr(self, 'tree_shipping') and self.tree_shipping:
                self.tree_shipping.update_idletasks()
                self.tree_shipping.update()
                logging.info("Main shipping table display refreshed")
            
            if hasattr(self, 'tree_pre') and self.tree_pre:
                self.tree_pre.update_idletasks()
                self.tree_pre.update()
                logging.info("Main pre-shipping table display refreshed")
            
            # 刷新控制面板表格
            if hasattr(self, 'control_shipping_tree') and self.control_shipping_tree:
                self.control_shipping_tree.update_idletasks()
                self.control_shipping_tree.update()
                logging.info("Control shipping table display refreshed")
            
            if hasattr(self, 'control_pre_tree') and self.control_pre_tree:
                self.control_pre_tree.update_idletasks()
                self.control_pre_tree.update()
                logging.info("Control pre-shipping table display refreshed")
            
            # 绘制网格线
            self.draw_shipping_grid()
            self.draw_pre_grid()
            
            # 强制刷新整个窗口
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            logging.error(f"Failed to force refresh table display: {e}")

    def test_table_data(self):
        """测试表格数据插入，确保文字可见"""
        try:
            # 测试主窗口发货订单表格
            if hasattr(self, 'tree_shipping') and self.tree_shipping:
                # 清空现有数据
                for item in list(self.tree_shipping.get_children("")):
                    self.tree_shipping.delete(item)
                
                # 插入测试数据
                self.tree_shipping.insert("", "end", iid="test1", values=(1, "测试订单001", "测试备注1"))
                self.tree_shipping.insert("", "end", iid="test2", values=(2, "测试订单002", "测试备注2"))
                self.tree_shipping.update_idletasks()
                logging.info("Test data inserted into main shipping table")
            
            # 测试主窗口预备订单表格
            if hasattr(self, 'tree_pre') and self.tree_pre:
                # 清空现有数据
                for item in list(self.tree_pre.get_children("")):
                    self.tree_pre.delete(item)
                
                # 插入测试数据
                self.tree_pre.insert("", "end", iid="test_pre1", values=("2025-09-21", "测试预备订单001", "未完成"))
                self.tree_pre.insert("", "end", iid="test_pre2", values=("2025-09-22", "测试预备订单002", "完成"))
                self.tree_pre.update_idletasks()
                logging.info("Test data inserted into main pre-shipping table")
            
            # 强制刷新显示
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            logging.error(f"Failed to insert test data: {e}")

    def setup_text_tags(self):
        """Set text tags styles"""
        self.reminder_text.tag_config("date_title", font=FONTS["title"], foreground=COLORS["primary"])
        self.reminder_text.tag_config("separator", foreground=COLORS["text_secondary"])
        self.reminder_text.tag_config("section_title", font=FONTS["subtitle"], foreground=COLORS["accent"])
        self.reminder_text.tag_config("work_content", font=FONTS["work_content"], foreground=COLORS["text_primary"])
        self.reminder_text.tag_config("order_item", font=FONTS["content"], foreground=COLORS["text_primary"])
        self.reminder_text.tag_config("no_orders", font=FONTS["content"], foreground=COLORS["text_secondary"])
        self.reminder_text.tag_config("pre_orders", font=FONTS["content"], foreground=COLORS["warning"])

    def ensure_data_loaded(self):
        """确保数据被正确加载并显示在表格中"""
        try:
            # 重新加载数据
            self.data = load_data()
            
            # 强制刷新界面
            self.update_reminder_text()
            
            # 确保表格可见
            if self.tree_shipping:
                self.tree_shipping.update_idletasks()
            if self.tree_pre:
                self.tree_pre.update_idletasks()
                
        except Exception as e:
            logging.error(f"Failed to ensure data loaded: {e}")

    def refresh_order_tables(self, target_tables=None):
        """统一的订单表格刷新方法
        
        Args:
            target_tables: 要刷新的表格列表，None表示刷新所有表格
                          可选值: ['main_shipping', 'main_pre', 'control_shipping', 'control_pre']
        """
        try:
            # 重新加载数据
            self.data = load_data()
            today = today_str()
            
            # 获取发货订单数据
            shipping_orders = self.data.get("shipping_orders", {}).get(today, [])
            
            # 获取预备订单数据
            pre_orders = self.data.get("pre_shipping_orders", {})
            future_pre = []
            for d in sorted(pre_orders.keys()):
                if d >= today:
                    lst = pre_orders.get(d, [])
                    if lst:
                        future_pre.extend([(d, item) for item in lst])
            
            # 刷新主窗口表格
            if target_tables is None or 'main_shipping' in target_tables:
                self._refresh_shipping_table(self.tree_shipping, shipping_orders, "main")
            
            if target_tables is None or 'main_pre' in target_tables:
                self._refresh_pre_table(self.tree_pre, future_pre, "main")
            
            # 刷新控制面板表格
            if target_tables is None or 'control_shipping' in target_tables:
                if hasattr(self, 'control_shipping_tree') and self.control_shipping_tree:
                    self._refresh_shipping_table(self.control_shipping_tree, shipping_orders, "control")
            
            if target_tables is None or 'control_pre' in target_tables:
                if hasattr(self, 'control_pre_tree') and self.control_pre_tree:
                    self._refresh_pre_table(self.control_pre_tree, future_pre, "control")
            
            logging.info(f"Order tables refreshed: {len(shipping_orders)} shipping, {len(future_pre)} pre-orders")
            
        except Exception as e:
            logging.error(f"Failed to refresh order tables: {e}")
    
    def _refresh_shipping_table(self, tree_widget, shipping_orders, table_type):
        """刷新发货订单表格"""
        if not tree_widget:
            return
            
        try:
            # 清空现有数据
            for item in list(tree_widget.get_children("")):
                tree_widget.delete(item)
            
            # 填充数据
            if shipping_orders:
                for i, order in enumerate(shipping_orders, 1):
                    if isinstance(order, dict):
                        val = order.get("order", "")
                        remark = order.get("remark", "")
                    else:
                        val = str(order)
                        remark = ""
                    tree_widget.insert("", "end", iid=f"shipping_{i}", values=(i, val, remark))
                    logging.info(f"Inserted shipping order {i}: {val} with remark: {remark} into {table_type} table")
            else:
                tree_widget.insert("", "end", iid="empty_shipping", values=("-", "今日无发货订单", ""))
                logging.info(f"Inserted empty row into {table_type} shipping table")
            
            # 强制刷新显示
            tree_widget.update_idletasks()
            tree_widget.update()
            
            # 验证数据
            children = tree_widget.get_children()
            logging.info(f"{table_type} shipping table refreshed: {len(children)} rows, {len(shipping_orders)} orders")
            
        except Exception as e:
            logging.error(f"Failed to refresh {table_type} shipping table: {e}")
    
    def _refresh_pre_table(self, tree_widget, future_pre, table_type):
        """刷新预备订单表格"""
        if not tree_widget:
            return
            
        try:
            # 清空现有数据
            for item in list(tree_widget.get_children("")):
                tree_widget.delete(item)
            
            # 填充数据
            if future_pre:
                # 按日期分组，确保每个日期的订单索引从1开始
                date_orders = {}
                for date, item in future_pre:
                    if date not in date_orders:
                        date_orders[date] = []
                    date_orders[date].append(item)
                
                # 为每个日期的订单生成正确的iid
                for date, orders in date_orders.items():
                    for i, item in enumerate(orders, 1):
                        if isinstance(item, dict):
                            order_val = item.get("order", "")
                            status = "完成" if item.get("done", False) else "未完成"
                        else:
                            order_val = str(item)
                            status = "未完成"
                        # 使用日期和该日期内的索引生成唯一iid
                        iid = f"pre_{date}_{i}"
                        tree_widget.insert("", "end", iid=iid, values=(date, order_val, status))
                        logging.info(f"Inserted pre-order {i}: {date} - {order_val} - {status} into {table_type} table with iid: {iid}")
            else:
                tree_widget.insert("", "end", iid="empty_pre", values=("-", "暂无预备订单", ""))
                logging.info(f"Inserted empty row into {table_type} pre-shipping table")
            
            # 强制刷新显示
            tree_widget.update_idletasks()
            tree_widget.update()
            
            # 验证数据
            children = tree_widget.get_children()
            logging.info(f"{table_type} pre-shipping table refreshed: {len(children)} rows, {len(future_pre)} orders")
            
        except Exception as e:
            logging.error(f"Failed to refresh {table_type} pre-shipping table: {e}")

    def force_immediate_table_refresh(self):
        """立即强制刷新表格显示，确保订单列表正确显示"""
        self.refresh_order_tables(['main_shipping', 'main_pre'])

    def force_show_tables(self):
        """强制显示表格，确保表格可见"""
        try:
            if hasattr(self, 'tree_shipping') and self.tree_shipping:
                # 强制刷新发货订单表格
                self.tree_shipping.update_idletasks()
                # 获取第一个子项并滚动到它
                children = self.tree_shipping.get_children()
                if children:
                    self.tree_shipping.see(children[0])
                logging.info("Forced shipping table to show")
            
            if hasattr(self, 'tree_pre') and self.tree_pre:
                # 强制刷新预备订单表格
                self.tree_pre.update_idletasks()
                # 获取第一个子项并滚动到它
                children = self.tree_pre.get_children()
                if children:
                    self.tree_pre.see(children[0])
                logging.info("Forced pre-shipping table to show")
            
            # 强制刷新整个窗口
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            logging.error(f"Failed to force show tables: {e}")

    def force_refresh_tables(self):
        """强制刷新表格显示，确保订单列表正确显示"""
        try:
            # 确保表格存在
            if not hasattr(self, 'tree_shipping') or not self.tree_shipping:
                logging.warning("Shipping table not initialized yet")
                return
            if not hasattr(self, 'tree_pre') or not self.tree_pre:
                logging.warning("Pre-shipping table not initialized yet")
                return
            
            # 重新加载数据
            self.data = load_data()
            
            # 更新提醒文本和表格
            self.update_reminder_text()
            
            # 强制刷新表格显示
            self.tree_shipping.update_idletasks()
            self.tree_pre.update_idletasks()
            
            # 调整表格列宽
            self.adjust_table_columns()
            
            logging.info("Tables force refreshed successfully")
            
        except Exception as e:
            logging.error(f"Failed to force refresh tables: {e}")

    def refresh_main_tables(self):
        """刷新主窗口表格数据 - 模拟控制面板的refresh_order_listbox行为"""
        try:
            # 确保表格存在
            if not hasattr(self, 'tree_shipping') or not self.tree_shipping:
                logging.warning("Shipping table not initialized yet")
                return
            if not hasattr(self, 'tree_pre') or not self.tree_pre:
                logging.warning("Pre-shipping table not initialized yet")
                return
            
            # 重新加载数据
            self.data = load_data()
            
            # 刷新发货订单表格
            today = today_str()
            shipping_orders = self.data.get("shipping_orders", {}).get(today, [])
            
            # 清空现有数据
            for item in list(self.tree_shipping.get_children("")):
                self.tree_shipping.delete(item)
            
            # 填充发货订单数据
            if shipping_orders:
                for i, order in enumerate(shipping_orders, 1):
                    if isinstance(order, dict):
                        val = order.get("order", "")
                        remark = order.get("remark", "")
                    else:
                        val = str(order)
                        remark = ""
                    self.tree_shipping.insert("", "end", iid=str(i), values=(i, val, remark))
            else:
                self.tree_shipping.insert("", "end", iid="empty", values=("-", "今日无发货订单", ""))
            
            # 刷新预备订单表格
            pre_orders = self.data.get("pre_shipping_orders", {})
            future_pre = []
            for d in sorted(pre_orders.keys()):
                if d >= today:
                    lst = pre_orders.get(d, [])
                    if lst:
                        future_pre.extend([(d, item) for item in lst])
            
            # 清空现有数据
            for item in list(self.tree_pre.get_children("")):
                self.tree_pre.delete(item)
            
            # 填充预备订单数据
            if future_pre:
                for i, (date, item) in enumerate(future_pre, 1):
                    if isinstance(item, dict):
                        order_val = item.get("order", "")
                        status = "完成" if item.get("done", False) else "未完成"
                    else:
                        order_val = str(item)
                        status = "未完成"
                    iid = f"{date}|{i}"
                    self.tree_pre.insert("", "end", iid=iid, values=(date, order_val, status))
            else:
                self.tree_pre.insert("", "end", iid="empty", values=("-", "暂无预备订单", ""))
            
            # 强制刷新表格显示
            self.tree_shipping.update_idletasks()
            self.tree_pre.update_idletasks()
            
            # 调整表格列宽
            self.adjust_table_columns()
            
            logging.info(f"Main tables refreshed: {len(shipping_orders)} shipping orders, {len(future_pre)} pre-orders")
            
        except Exception as e:
            logging.error(f"Failed to refresh main tables: {e}")

    def create_bottom_buttons(self):
        """Create bottom buttons with fixed position and centered layout"""
        # 创建固定位置的底部按钮区域
        self.bottom_frame = tk.Frame(self.root, bg=COLORS["bg_main"], height=50)
        self.bottom_frame.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)
        
        # 创建按钮容器用于居中
        button_container = tk.Frame(self.bottom_frame, bg=COLORS["bg_main"])
        button_container.place(relx=0.5, rely=0.5, anchor="center")
        
        # 立即提醒按钮 - 恢复原始尺寸
        self.immediate_btn = create_modern_button(button_container, "🔔 立即提醒",
                                             self.immediate_reminder, COLORS["accent"])
        self.immediate_btn.pack(side="left", padx=(0, 15))
        
        # 控制面板按钮 - 恢复原始尺寸
        self.control_btn = create_modern_button(button_container, "⚙️ 控制面板",
                                           self.open_control_panel)
        self.control_btn.pack(side="left")

    def create_menu(self):
        """Create menu bar"""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="⚙️ 其它设置", menu=settings_menu)
        settings_menu.add_command(label="🎛️ 控制面板", command=self.open_control_panel)
        settings_menu.add_separator()
        settings_menu.add_command(label="⏰ 生命倒计时设置", command=self.open_life_dialog)
        settings_menu.add_command(label="🕐 上下班打卡提醒", command=self.open_clock_settings)
        settings_menu.add_command(label="🔔 自定义提醒设置", command=self.open_custom_reminder_settings)
        settings_menu.add_command(label="🎊 节日管理", command=self.open_festival_manager)
        
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="❓ 帮助", menu=help_menu)
        help_menu.add_command(label="ℹ️ 关于程序", command=self.show_about)
        help_menu.add_command(label="🔑 激活程序", command=activate_program)

    def immediate_reminder(self):
        """Trigger an immediate reminder"""
        try:
            count = import_orders_from_excel(self.data)
            if count > 0:
                save_data(self.data)
                logging.info(f"Imported {count} new orders from Excel")
            
            self.update_reminder_text()
            self.show_reminder()
            
            logging.info("Immediate reminder triggered")
        except Exception as e:
            logging.error(f"Failed to trigger immediate reminder: {e}")
            messagebox.showerror("错误", f"立即提醒失败：{e}")

    def update_reminder_text(self):
        """Update reminder text content"""
        try:
            if not check_trial(self.root):
                self.reminder_text.config(state=tk.NORMAL)
                self.reminder_text.delete("1.0", tk.END)
                self.reminder_text.insert(tk.END, "⚠️ 试用已结束，请激活程序以继续使用完整功能！")
                self.reminder_text.config(state=tk.DISABLED)
                return

            self.update_festival_reminder()
            
            val, stage_icon, stage_text, days_text = compute_life_ui(self.data)
            self.life_canvas.set_values(val, stage_icon, stage_text, days_text)
            
            today = today_str()
            wd = datetime.date.today().weekday()
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            
            work_msg = self.data.get("work_plan", {}).get(str(wd), "今日无特定工作安排")
            shipping = self.data.get("shipping_orders", {}).get(today, [])
            
            future_pre = []
            pre_orders = self.data.get("pre_shipping_orders", {})
            for d in sorted(pre_orders.keys()):
                if d >= today:
                    lst = pre_orders.get(d, [])
                    if lst:
                        try:
                            date_obj = datetime.date.fromisoformat(d)
                            formatted_date = date_obj.strftime("%m月%d日")
                        except ValueError:
                            formatted_date = d
                        # 兼容字符串与字典
                        display_items = []
                        for it in lst:
                            if isinstance(it, dict):
                                display_items.append(str(it.get("order", "")))
                            else:
                                display_items.append(str(it))
                        future_pre.append(f"📦 {formatted_date}: {', '.join(display_items)}")
            
            pre_display = "\n".join(future_pre) if future_pre else "✅ 暂无预备订单"

            self.reminder_text.config(state=tk.NORMAL)
            self.reminder_text.delete("1.0", tk.END)
            
            # 获取节日信息
            festival_text = self.get_festival_text()
            date_display = f"📅 {today} 星期{weekday_names[wd]}"
            if festival_text:
                date_display += f" | {festival_text}"
            self.reminder_text.insert(tk.END, f"{date_display}\n", ("date_title",))
            self.reminder_text.insert(tk.END, "="*50 + "\n", ("separator",))
            
            self.reminder_text.insert(tk.END, "💼 今日工作安排\n", ("section_title",))
            self.reminder_text.insert(tk.END, f"{work_msg}\n", ("work_content",))
            
            self.reminder_text.config(state=tk.DISABLED)
            
            # 表格刷新现在由专门的 refresh_order_tables 方法处理
            
        except Exception as e:
            logging.error(f"Failed to update reminder text: {e}")

    def on_main_pre_double_click(self, event):
        """主界面预备订单表格双击切换状态"""
        try:
            if not self.tree_pre:
                return
            sel = self.tree_pre.selection()
            if not sel:
                return
            iid = sel[0]
            if iid == "empty" or iid == "empty_pre":
                return
            
            logging.info(f"Main pre double-clicked iid: {iid}")
            
            # 解析 iid 获取日期和索引信息
            # 格式: "pre_2025-09-21_1" 或 "test_pre1" 或 "1" (旧格式)
            if iid.startswith("pre_"):
                try:
                    # 从 iid 中提取日期和索引
                    parts = iid.split("_")
                    if len(parts) >= 3:
                        d = parts[1]  # 日期部分
                        idx = int(parts[2]) - 1  # 索引部分
                        logging.info(f"Main pre parsed from iid: date={d}, idx={idx}")
                    else:
                        # 如果是测试数据，使用当前日期
                        d = today_str()
                        idx = 0
                        logging.info(f"Main pre test data fallback: date={d}, idx={idx}")
                except (ValueError, IndexError) as e:
                    logging.error(f"Failed to parse main pre iid {iid}: {e}")
                    # 如果解析失败，尝试其他方法
                    children = list(self.tree_pre.get_children(""))
                    idx = children.index(iid)
                    d = self._get_date_from_table_row(self.tree_pre, iid)
                    logging.info(f"Main pre fallback parsing: date={d}, idx={idx}")
            elif iid.isdigit():
                # 兼容旧格式 "1", "2", "3" 等
                children = list(self.tree_pre.get_children(""))
                idx = children.index(iid)
                d = self._get_date_from_table_row(self.tree_pre, iid)
                logging.info(f"Main pre old format iid: date={d}, idx={idx}")
            elif "|" in iid:
                # 格式：date|index (旧格式)
                d, idx_str = iid.split("|", 1)
                try:
                    idx = int(idx_str) - 1
                    logging.info(f"Main pre pipe format: date={d}, idx={idx}")
                except ValueError:
                    return
            else:
                # 其他格式，尝试从表格行获取信息
                children = list(self.tree_pre.get_children(""))
                idx = children.index(iid)
                d = self._get_date_from_table_row(self.tree_pre, iid)
                logging.info(f"Main pre other format iid: date={d}, idx={idx}")
            
            arr = self.data.setdefault("pre_shipping_orders", {}).setdefault(d, [])
            if 0 <= idx < len(arr):
                item = arr[idx]
                if isinstance(item, dict):
                    # 切换完成状态
                    old_status = item.get("done", False)
                    item["done"] = not old_status
                    new_status = "完成" if item["done"] else "未完成"
                    logging.info(f"Toggled main pre-order status: {item.get('order', '')} -> {new_status}")
                else:
                    # 将字符串升级为带状态的对象
                    arr[idx] = {"order": str(item), "done": True}
                    logging.info(f"Upgraded main pre-order to dict: {item} -> 完成")
                
                save_data(self.data)
                
                # 刷新所有相关表格
                self.refresh_order_tables(['main_pre', 'control_pre'])
                self.update_reminder_text()
                
                # 显示状态变更提示
                order_name = item.get("order", "") if isinstance(item, dict) else str(item)
                status_text = "完成" if (isinstance(item, dict) and item.get("done", False)) else "未完成"
                messagebox.showinfo("状态更新", f"订单 '{order_name}' 状态已更新为: {status_text}")
            else:
                logging.warning(f"Index {idx} out of range for date {d}")
                
        except Exception as e:
            logging.error(f"Failed to toggle main pre-shipping status: {e}")
            messagebox.showerror("错误", f"切换状态失败：{e}")

    def get_festival_text(self):
        """Get festival text for display"""
        try:
            festival_msgs = []
            now = datetime.date.today()
            
            for k, name in self.data.get("festival_reminders", {}).items():
                try:
                    mm, dd = map(int, k.split('-'))
                    fdate = datetime.date(now.year, mm, dd)
                except ValueError:
                    continue
                
                delta = (fdate - now).days
                if 0 <= delta <= 3:
                    if delta == 0:
                        festival_msgs.append(f"🎊 今天是{name}！")
                    elif delta == 1:
                        festival_msgs.append(f"🎈 明天是{name}")
                    else:
                        festival_msgs.append(f"🎁 {name}还有{delta}天")
            
            return "  |  ".join(festival_msgs) if festival_msgs else ""
        except Exception as e:
            logging.error(f"Failed to get festival text: {e}")
            return ""

    def update_festival_reminder(self):
        """Update festival reminder (kept for compatibility)"""
        # 节日信息现在直接集成在日期显示中，此方法保留但不执行任何操作
        pass

    def schedule_reminder(self):
        """Schedule timed reminder"""
        try:
            if self.reminder_after_id is not None:
                self.root.after_cancel(self.reminder_after_id)
                self.reminder_after_id = None
            
            if self.data.get("reminder_enabled", True) and check_trial(self.root):
                count = import_orders_from_excel(self.data)
                if count > 0:
                    save_data(self.data)
                    self.update_reminder_text()
                
                self.show_reminder()
                
                interval_min = int(self.data.get("reminder_interval", 120))
                self.reminder_after_id = self.root.after(interval_min * 60 * 1000, self.schedule_reminder)
        except Exception as e:
            logging.error(f"Failed to schedule reminder: {e}")

    def show_reminder(self):
        """Show reminder popup"""
        try:
            if not check_trial(self.root):
                return
            
            today = today_str()
            wd = datetime.date.today().weekday()
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            work_msg = self.data.get("work_plan", {}).get(str(wd), "")
            shipping = self.data.get("shipping_orders", {}).get(today, [])
            
            future_pre = []
            pre_orders = self.data.get("pre_shipping_orders", {})
            for d in sorted(pre_orders.keys()):
                if d >= today:
                    lst = pre_orders.get(d, [])
                    if lst:
                        display_items = []
                        for it in lst:
                            if isinstance(it, dict):
                                order_text = it.get("order", "")
                                remark = it.get("remark", "")
                                if remark:
                                    display_items.append(f"{order_text} ({remark})")
                                else:
                                    display_items.append(order_text)
                            else:
                                display_items.append(str(it))
                        future_pre.append(f"{d}: {', '.join(display_items)}")
            pre_display = "\n".join(future_pre) if future_pre else "无"
            
            msg = f"📅 {today} 星期{weekday_names[wd]}\n"
            msg += f"💼 {work_msg}\n\n🚚 发货订单:\n"
            if shipping:
                shipping_items = []
                for order in shipping:
                    if isinstance(order, dict):
                        order_text = order.get("order", "")
                        remark = order.get("remark", "")
                        if remark:
                            shipping_items.append(f"• {order_text} ({remark})")
                        else:
                            shipping_items.append(f"• {order_text}")
                    else:
                        shipping_items.append(f"• {order}")
                msg += "\n".join(shipping_items)
            else:
                msg += "✨ 今日无订单"
            msg += "\n\n⌛ 预备发货:\n" + pre_display
            
            self.root.after(0, lambda: messagebox.showinfo("📌 工作提醒", msg))
        except Exception as e:
            logging.error(f"Failed to show reminder: {e}")

    def open_control_panel(self):
        """Open control panel"""
        try:
            cp = tk.Toplevel(self.root)
            cp.title("⚙️ 控制面板")
            cp.configure(bg=COLORS["bg_main"])
            center_window(cp, 900, 800)

            title_frame = tk.Frame(cp, bg=COLORS["primary"], height=50)
            title_frame.pack(fill="x")
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text="⚙️ 系统控制面板", font=FONTS["title"],
                     bg=COLORS["primary"], fg="white").pack(pady=12)

            canvas = tk.Canvas(cp, bg=COLORS["bg_main"])
            vsb = tk.Scrollbar(cp, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            
            frame = tk.Frame(canvas, bg=COLORS["bg_main"])
            canvas.create_window((0,0), window=frame, anchor="nw")
            frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

            self.create_work_plan_section(frame)
            self.create_order_management_section(frame, cp)
            self.create_system_settings_section(frame, cp)
            
        except Exception as e:
            logging.error(f"Failed to open control panel: {e}")
            messagebox.showerror("Error", f"Failed to open control panel: {e}")

    def create_work_plan_section(self, parent):
        """Create work plan edit area"""
        work_card = create_card_frame(parent, "📝 每周工作计划")
        work_card.pack(fill="x", padx=20, pady=15)
        
        self.work_entries = {}
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        for i in range(7):
            row_frame = tk.Frame(work_card, bg=COLORS["bg_card"])
            row_frame.pack(fill="x", padx=15, pady=5)
            
            label = tk.Label(row_frame, text=f"{weekday_names[i]}：",
                             font=FONTS["section"], width=8,
                             bg=COLORS["bg_card"], fg=COLORS["text_primary"])
            label.pack(side="left", padx=(0,10))
            
            ent = tk.Entry(row_frame, width=70, font=FONTS["content"],
                           bg="white", fg=COLORS["text_primary"], relief="solid", bd=1)
            ent.insert(0, self.data["work_plan"].get(str(i), ""))
            ent.pack(side="left", fill="x", expand=True)
            self.work_entries[i] = ent

    def create_order_management_section(self, parent, cp_window):
        """Create order management area"""
        shipping_card = create_card_frame(parent, "🚚 发货订单管理")
        shipping_card.pack(fill="x", padx=20, pady=15)
        
        so_input_frame = tk.Frame(shipping_card, bg=COLORS["bg_card"])
        so_input_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(so_input_frame, text="发货日期：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        
        if CALENDAR_AVAILABLE:
            self.so_date = DateEntry(so_input_frame, width=16, date_pattern="yyyy-mm-dd",
                                     font=FONTS["content"])
        else:
            self.so_date = tk.Entry(so_input_frame, width=18, font=FONTS["content"])
            self.so_date.insert(0, today_str())
        self.so_date.pack(side="left", padx=(5,15))
        
        tk.Label(so_input_frame, text="订单号：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        
        self.so_entry = tk.Entry(so_input_frame, width=30, font=FONTS["content"])
        self.so_entry.pack(side="left", padx=5)
        
        tk.Label(so_input_frame, text="备注：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left", padx=(10,0))
        
        self.so_remark_entry = tk.Entry(so_input_frame, width=20, font=FONTS["content"])
        self.so_remark_entry.pack(side="left", padx=5)
        
        # 发货订单表格
        self.control_shipping_tree = ttk.Treeview(shipping_card, columns=("idx", "order", "remark"), show="headings", height=6)
        self.control_shipping_tree.heading("idx", text="序号")
        self.control_shipping_tree.heading("order", text="订单号")
        self.control_shipping_tree.heading("remark", text="备注")
        self.control_shipping_tree.column("idx", width=60, anchor="center")
        self.control_shipping_tree.column("order", width=500, anchor="w")
        self.control_shipping_tree.column("remark", width=200, anchor="w")
        self._setup_table_style(self.control_shipping_tree)
        self.control_shipping_tree.pack(padx=15, pady=10, fill="x")
        
        so_btn_frame = tk.Frame(shipping_card, bg=COLORS["bg_card"])
        so_btn_frame.pack(fill="x", padx=15, pady=(0,15))
        
        create_modern_button(so_btn_frame, "➕ 添加发货订单",
                             lambda: self.add_order(True, self.so_date, self.so_entry, self.control_shipping_tree, self.so_remark_entry),
                             COLORS["success"]).pack(side="left", padx=5)
        create_modern_button(so_btn_frame, "🗑️ 删除选中",
                             lambda: self.del_order(True, self.so_date, self.control_shipping_tree),
                             COLORS["error"]).pack(side="left", padx=5)

        pre_card = create_card_frame(parent, "⌛ 预备发货订单管理")
        pre_card.pack(fill="x", padx=20, pady=15)
        
        pre_input_frame = tk.Frame(pre_card, bg=COLORS["bg_card"])
        pre_input_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(pre_input_frame, text="发货日期：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        
        if CALENDAR_AVAILABLE:
            self.pre_date = DateEntry(pre_input_frame, width=16, date_pattern="yyyy-mm-dd",
                                      font=FONTS["content"])
        else:
            self.pre_date = tk.Entry(pre_input_frame, width=18, font=FONTS["content"])
            self.pre_date.insert(0, today_str())
        self.pre_date.pack(side="left", padx=(5,15))
        
        tk.Label(pre_input_frame, text="订单号：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        
        self.pre_entry = tk.Entry(pre_input_frame, width=40, font=FONTS["content"])
        self.pre_entry.pack(side="left", padx=5)
        
        # 预备发货订单表格（含状态）
        self.control_pre_tree = ttk.Treeview(pre_card, columns=("idx", "order", "status"), show="headings", height=6)
        self.control_pre_tree.heading("idx", text="序号")
        self.control_pre_tree.heading("order", text="订单号")
        self.control_pre_tree.heading("status", text="状态")
        self.control_pre_tree.column("idx", width=60, anchor="center")
        self.control_pre_tree.column("order", width=560, anchor="w")
        self.control_pre_tree.column("status", width=120, anchor="center")
        self._setup_table_style(self.control_pre_tree)
        self.control_pre_tree.pack(padx=15, pady=10, fill="x")
        # 双击切换状态
        self.control_pre_tree.bind("<Double-1>", self.on_pre_order_double_click)
        
        pre_btn_frame = tk.Frame(pre_card, bg=COLORS["bg_card"])
        pre_btn_frame.pack(fill="x", padx=15, pady=(0,15))
        
        create_modern_button(pre_btn_frame, "➕ 添加预备订单",
                             lambda: self.add_order(False, self.pre_date, self.pre_entry, self.control_pre_tree),
                             COLORS["warning"]).pack(side="left", padx=5)
        create_modern_button(pre_btn_frame, "🗑️ 删除选中",
                             lambda: self.del_order(False, self.pre_date, self.control_pre_tree),
                             COLORS["error"]).pack(side="left", padx=5)
        
        # 刷新控制面板表格
        self.refresh_order_tables(['control_shipping', 'control_pre'])
        
        # 强制刷新表格显示
        self.root.after(100, self.force_refresh_table_display)
        
        if CALENDAR_AVAILABLE:
            self.so_date.bind("<<DateEntrySelected>>",
                              lambda e: self.refresh_order_tables(['control_shipping']))
            self.pre_date.bind("<<DateEntrySelected>>",
                               lambda e: self.refresh_order_tables(['control_pre']))

    def create_system_settings_section(self, parent, cp_window):
        """Create system settings area"""
        system_card = create_card_frame(parent, "⚙️ 系统设置")
        system_card.pack(fill="x", padx=20, pady=15)
        
        excel_frame = tk.Frame(system_card, bg=COLORS["bg_card"])
        excel_frame.pack(fill="x", padx=15, pady=15)
        
        tk.Label(excel_frame, text="📊 Excel文件夹：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(anchor="w")
        
        excel_path_frame = tk.Frame(excel_frame, bg=COLORS["bg_card"])
        excel_path_frame.pack(fill="x", pady=(5,10))
        
        self.excel_dir_var = tk.StringVar(value=self.data.get("excel_dir", ""))
        tk.Entry(excel_path_frame, textvariable=self.excel_dir_var, width=60,
                 font=FONTS["content"]).pack(side="left", fill="x", expand=True)
        
        create_modern_button(excel_path_frame, "📁 浏览", self.choose_excel_dir).pack(side="right", padx=(10,0))
        
        tk.Label(excel_frame, text="💡 格式：日期 | 订单号 | 类型（发货/预备）",
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                 font=FONTS["default"]).pack(anchor="w")
        
        create_modern_button(excel_frame, "🔄 立即导入Excel", self.manual_import_excel,
                             COLORS["warning"]).pack(pady=(10,0))
        
        interval_frame = tk.Frame(system_card, bg=COLORS["bg_card"])
        interval_frame.pack(fill="x", padx=15, pady=15)
        
        tk.Label(interval_frame, text="⏰ 提醒间隔：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        
        self.interval_options = [("30分钟", 30), ("1小时", 60), ("2小时", 120), ("4小时", 240)]
        cur_interval = self.data.get("reminder_interval", 120)
        
        self.interval_combo = ttk.Combobox(interval_frame, values=[k for k, v in self.interval_options],
                                           state="readonly", width=12, font=FONTS["content"])
        label_for_val = {v: k for k, v in self.interval_options}
        self.interval_combo.set(label_for_val.get(cur_interval, "2小时"))
        self.interval_combo.pack(side="left", padx=(10,20))
        
        tk.Label(interval_frame, text="自定义(分钟)：", bg=COLORS["bg_card"],
                 font=FONTS["section"]).pack(side="left")
        self.custom_interval_entry = tk.Entry(interval_frame, width=8, font=FONTS["content"])
        self.custom_interval_entry.pack(side="left", padx=5)
        self.custom_interval_entry.insert(0, str(cur_interval))

        switch_frame = tk.Frame(system_card, bg=COLORS["bg_card"])
        switch_frame.pack(fill="x", padx=15, pady=(0,15))
        
        self.reminder_chk_var = tk.BooleanVar(value=self.data.get("reminder_enabled", True))
        self.startup_chk_var = tk.BooleanVar(value=self.data.get("startup_enabled", False))
        
        tk.Checkbutton(switch_frame, text="🔔 开启定时提醒", variable=self.reminder_chk_var,
                       bg=COLORS["bg_card"], font=FONTS["large"]).pack(anchor="w", pady=5)
        tk.Checkbutton(switch_frame, text="🚀 开机自动启动", variable=self.startup_chk_var,
                       bg=COLORS["bg_card"], font=FONTS["large"]).pack(anchor="w", pady=5)
        
        bottom_frame = tk.Frame(parent, bg=COLORS["bg_main"])
        bottom_frame.pack(fill="x", padx=20, pady=20)
        
        create_modern_button(bottom_frame, "💾 保存所有设置",
                             lambda: self.save_all_settings(cp_window),
                             COLORS["success"], width=20).pack(side="right", padx=10)
        create_modern_button(bottom_frame, "❌ 取消", cp_window.destroy,
                             COLORS["text_secondary"], width=15).pack(side="right")


    def open_life_dialog(self):
        """Open life settings dialog"""
        try:
            logging.info("Opening life settings dialog")
            dlg = tk.Toplevel(self.root)
            dlg.title("⏰ 生命倒计时配置")
            dlg.configure(bg=COLORS["bg_main"])
            center_window(dlg, 400, 350)
            dlg.deiconify()  # Ensure dialog is visible
            dlg.lift()  # Bring dialog to front
            logging.info("Life settings dialog created and raised")

            title_frame = tk.Frame(dlg, bg=COLORS["primary"], height=50)
            title_frame.pack(fill="x")
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text="⏰ 生命倒计时设置", font=FONTS["title"],
                     bg=COLORS["primary"], fg="white").pack(pady=12)
            
            content_frame = tk.Frame(dlg, bg=COLORS["bg_main"])
            content_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Current age
            tk.Label(content_frame, text="🎂 当前年龄：", bg=COLORS["bg_main"],
                     font=FONTS["section"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(0,5))
            
            cur_age_frame = tk.Frame(content_frame, bg=COLORS["bg_main"])
            cur_age_frame.pack(fill="x", pady=(0,15))
            cur_age = tk.IntVar(value=self.data.get("life_settings", {}).get("current_age", 25))
            tk.Entry(cur_age_frame, textvariable=cur_age, font=FONTS["content"], width=20).pack(anchor="center")
            
            # 理想年龄
            tk.Label(content_frame, text="🎯 理想寿命：", bg=COLORS["bg_main"],
                     font=FONTS["section"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(0,5))
            
            ideal_age_frame = tk.Frame(content_frame, bg=COLORS["bg_main"])
            ideal_age_frame.pack(fill="x", pady=(0,15))
            ideal_age = tk.IntVar(value=self.data.get("life_settings", {}).get("ideal_age", 80))
            tk.Entry(ideal_age_frame, textvariable=ideal_age, font=FONTS["content"], width=20).pack(anchor="center")
            
            tk.Label(content_frame, text=f"💡 提示：理想寿命最大为{MAX_AGE}岁",
                     bg=COLORS["bg_main"], fg=COLORS["text_secondary"],
                     font=FONTS["default"]).pack(anchor="w", pady=(0,20))
            
            def save_life():
                try:
                    ca = cur_age.get()
                    ia = ideal_age.get()
                    
                    if ca < 0 or ca > MAX_AGE:
                        messagebox.showerror("错误", f"当前年龄应在0-{MAX_AGE}岁之间")
                        logging.error(f"Invalid current age: {ca}")
                        return
                    
                    if ia > MAX_AGE:
                        result = messagebox.askyesno("长寿提醒",
                                                     f"理想寿命超过{MAX_AGE}岁！\n您想长生不老吗？🧙‍♂️\n\n设置为{MAX_AGE}岁？")
                        if result:
                            ia = MAX_AGE
                            ideal_age.set(MAX_AGE)
                        else:
                            logging.info("User declined to set max age")
                            return
                    
                    if ia <= 0:
                        messagebox.showerror("错误", "理想寿命必须大于0")
                        logging.error("Ideal age is zero or negative")
                        return
                        
                    if ca >= ia:
                        messagebox.showwarning("提醒", "当前年龄不能大于或等于理想寿命！")
                        logging.error(f"Current age {ca} >= ideal age {ia}")
                        return
                    # 保存年龄
                    self.data.setdefault("life_settings", {})["current_age"] = ca
                    self.data.setdefault("life_settings", {})["ideal_age"] = ia
                    # 重置每日递减基线
                    self.data["life_settings"]["remain_base_days"] = max(ia - ca, 0) * 365
                    self.data["life_settings"]["remain_base_date"] = datetime.date.today().isoformat()
                    save_data(self.data)
                    self.update_reminder_text()
                    dlg.destroy()
                    messagebox.showinfo("保存成功", "生命设置已保存！✨")
                    logging.info(f"Life settings saved: current_age={ca}, ideal_age={ia}")
                    
                except ValueError as e:
                    messagebox.showerror("错误", "请输入有效的数字年龄")
                    logging.error(f"Invalid numeric input in life settings: {e}")
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败：{e}")
                    logging.error(f"Failed to save life settings: {e}")
            
            btn_frame = tk.Frame(content_frame, bg=COLORS["bg_main"])
            btn_frame.pack(fill="x", pady=20)
            
            ok_button = create_modern_button(btn_frame, "✅ 确定", save_life, 
                                           button_type="success", width=10)
            ok_button.pack(side="right", padx=10)
            
            cancel_button = create_modern_button(btn_frame, "❌ 取消", dlg.destroy, 
                                               button_type="error", width=10)
            cancel_button.pack(side="right", padx=10)
            
            logging.info("Life settings dialog fully configured")
            
        except Exception as e:
            logging.error(f"Failed to open life settings dialog: {e}")
            messagebox.showerror("错误", f"打开生命设置窗口失败：{e}")



    def get_date_from_widget(self, widget):
        """从日期组件获取日期"""
        try:
            if CALENDAR_AVAILABLE and hasattr(widget, 'get_date'):
                return widget.get_date().strftime("%Y-%m-%d")
            else:
                date_str = widget.get().strip()
                datetime.date.fromisoformat(date_str)
                return date_str
        except ValueError:
            messagebox.showwarning("警告", "无效的日期格式，使用今天的日期")
            return today_str()
        except Exception:
            return today_str()

    def add_order(self, is_shipping, date_widget, entry_widget, listbox_widget, remark_widget=None):
        """Add order"""
        try:
            d = self.get_date_from_widget(date_widget)
            o = entry_widget.get().strip()
            remark = remark_widget.get().strip() if remark_widget else ""
            
            if not d or not o:
                messagebox.showwarning("提示", "请输入完整的日期和订单号")
                return
            
            key = "shipping_orders" if is_shipping else "pre_shipping_orders"
            self.data.setdefault(key, {}).setdefault(d, [])
            
            # 检查重复订单（考虑备注）
            if is_shipping:
                # 发货订单：检查订单号是否重复
                if any((item == o) or (isinstance(item, dict) and item.get("order") == o) for item in self.data[key][d]):
                    messagebox.showwarning("重复订单", "该订单号已存在！")
                    return
                # 保存为带备注的对象
                self.data[key][d].append({"order": o, "remark": remark})
            else:
                # 预备订单保存为带状态的对象
                # 向后兼容：如果已有为字符串的相同订单，视为重复
                existing = self.data[key][d]
                if any((item == o) or (isinstance(item, dict) and item.get("order") == o) for item in existing):
                    messagebox.showwarning("重复订单", "该订单号已存在！")
                    return
                self.data[key][d].append({"order": o, "done": False, "remark": remark})
            save_data(self.data)
            # 刷新所有相关表格
            if is_shipping:
                self.refresh_order_tables(['main_shipping', 'control_shipping'])
            else:
                self.refresh_order_tables(['main_pre', 'control_pre'])
            entry_widget.delete(0, tk.END)
            if remark_widget:
                remark_widget.delete(0, tk.END)
            self.update_reminder_text()
            
            order_type = "发货订单" if is_shipping else "预备订单"
            messagebox.showinfo("添加成功", f"{order_type}已添加！")
            
        except Exception as e:
            logging.error(f"Failed to add order: {e}")
            messagebox.showerror("错误", f"添加订单失败：{e}")

    def del_order(self, is_shipping, date_widget, listbox_widget):
        """Delete order"""
        try:
            sel = []
            # 兼容 Listbox 与 Treeview
            if isinstance(listbox_widget, tk.Listbox):
                sel = list(listbox_widget.curselection())
            else:
                try:
                    sel_ids = list(listbox_widget.selection())
                    # iids 使用插入顺序为从1开始，这里映射为索引
                    for iid in sel_ids:
                        try:
                            sel.append(int(iid) - 1)
                        except Exception:
                            # Fallback: 根据当前children顺序查找
                            children = list(listbox_widget.get_children(""))
                            sel.append(children.index(iid))
                except Exception:
                    sel = []
            if not sel:
                messagebox.showwarning("提示", "请先选择要删除的订单")
                return
            
            result = messagebox.askyesno("确认删除", f"确定要删除选中的{len(sel)}个订单吗？")
            if not result:
                return
                
            sel.sort(reverse=True)
            d = self.get_date_from_widget(date_widget)
            key = "shipping_orders" if is_shipping else "pre_shipping_orders"
            arr = self.data.get(key, {}).get(d, [])
            
            for idx in sel:
                if 0 <= idx < len(arr):
                    arr.pop(idx)
            if not arr:
                self.data.get(key, {}).pop(d, None)
            
            save_data(self.data)
            
            # 刷新所有相关表格
            if is_shipping:
                self.refresh_order_tables(['main_shipping', 'control_shipping'])
            else:
                self.refresh_order_tables(['main_pre', 'control_pre'])
            
            self.update_reminder_text()
            messagebox.showinfo("删除成功", "选中的订单已删除！")
            
        except Exception as e:
            logging.error(f"Failed to delete order: {e}")
            messagebox.showerror("错误", f"删除订单失败：{e}")

    def refresh_order_listbox(self, date_widget, listbox, is_shipping):
        """Refresh order listbox"""
        try:
            d = self.get_date_from_widget(date_widget)
            # 兼容 Listbox 与 Treeview
            if isinstance(listbox, tk.Listbox):
                listbox.delete(0, tk.END)
            
            key = "shipping_orders" if is_shipping else "pre_shipping_orders"
            orders = self.data.get(key, {}).get(d, [])
            
            if isinstance(listbox, tk.Listbox):
                for order in orders:
                    if isinstance(order, dict):
                        listbox.insert(tk.END, order.get("order", ""))
                    else:
                        listbox.insert(tk.END, order)
            else:
                # Treeview 填充
                for item in list(listbox.get_children("")):
                    listbox.delete(item)
                if is_shipping:
                    for i, order in enumerate(orders, 1):
                        if isinstance(order, dict):
                            val = order.get("order", "")
                            remark = order.get("remark", "")
                        else:
                            val = str(order)
                            remark = ""
                        listbox.insert("", "end", iid=str(i), values=(i, val, remark))
                else:
                    for i, order in enumerate(orders, 1):
                        if isinstance(order, dict):
                            val = order.get("order", "")
                            status = "完成" if order.get("done", False) else "未完成"
                        else:
                            val = str(order)
                            status = "未完成"
                        # 使用与_refresh_pre_table相同的iid格式
                        listbox.insert("", "end", iid=f"pre_{d}_{i}", values=(d, val, status))
        except Exception as e:
            logging.error(f"Failed to refresh order listbox: {e}")

    def on_pre_order_double_click(self, event):
        """预备订单表格双击切换状态 - 通用方法"""
        try:
            # 获取被双击的表格控件
            tree = event.widget
            sel = tree.selection()
            if not sel:
                return
            
            iid = sel[0]
            logging.info(f"Double-clicked iid: {iid}")
            
            # 解析 iid 获取日期和索引信息
            # 格式: "pre_2025-09-21_1" 或 "test_pre1" 或 "1" (旧格式)
            if iid.startswith("pre_"):
                try:
                    # 从 iid 中提取日期和索引
                    parts = iid.split("_")
                    if len(parts) >= 3:
                        date_str = parts[1]  # 日期部分
                        idx = int(parts[2]) - 1  # 索引部分
                        logging.info(f"Parsed from iid: date={date_str}, idx={idx}")
                    else:
                        # 如果是测试数据，使用当前日期
                        date_str = today_str()
                        idx = 0
                        logging.info(f"Test data fallback: date={date_str}, idx={idx}")
                except (ValueError, IndexError) as e:
                    logging.error(f"Failed to parse iid {iid}: {e}")
                    # 如果解析失败，尝试其他方法
                    children = list(tree.get_children(""))
                    idx = children.index(iid)
                    # 从表格数据中获取日期
                    date_str = self._get_date_from_table_row(tree, iid)
                    logging.info(f"Fallback parsing: date={date_str}, idx={idx}")
            elif iid.isdigit():
                # 兼容旧格式 "1", "2", "3" 等
                children = list(tree.get_children(""))
                idx = children.index(iid)
                date_str = self._get_date_from_table_row(tree, iid)
                logging.info(f"Old format iid: date={date_str}, idx={idx}")
            else:
                # 其他格式，尝试从表格行获取信息
                children = list(tree.get_children(""))
                idx = children.index(iid)
                date_str = self._get_date_from_table_row(tree, iid)
                logging.info(f"Other format iid: date={date_str}, idx={idx}")
            
            # 获取对应日期的订单数据
            arr = self.data.setdefault("pre_shipping_orders", {}).setdefault(date_str, [])
            
            if 0 <= idx < len(arr):
                item = arr[idx]
                if isinstance(item, dict):
                    # 切换完成状态
                    old_status = item.get("done", False)
                    item["done"] = not old_status
                    new_status = "完成" if item["done"] else "未完成"
                    logging.info(f"Toggled pre-order status: {item.get('order', '')} -> {new_status}")
                else:
                    # 将字符串升级为带状态的对象
                    arr[idx] = {"order": str(item), "done": True}
                    logging.info(f"Upgraded pre-order to dict: {item} -> 完成")
                
                save_data(self.data)
                
                # 刷新所有相关表格
                self.refresh_order_tables(['main_pre', 'control_pre'])
                self.update_reminder_text()
                
                # 显示状态变更提示
                order_name = item.get("order", "") if isinstance(item, dict) else str(item)
                status_text = "完成" if (isinstance(item, dict) and item.get("done", False)) else "未完成"
                messagebox.showinfo("状态更新", f"订单 '{order_name}' 状态已更新为: {status_text}")
            else:
                logging.warning(f"Index {idx} out of range for date {date_str}")
                
        except Exception as e:
            logging.error(f"Failed to toggle pre-shipping status: {e}")
            messagebox.showerror("错误", f"切换状态失败：{e}")
    
    def _get_date_from_table_row(self, tree, iid):
        """从表格行获取日期信息"""
        try:
            # 获取行的值
            values = tree.item(iid, "values")
            if values and len(values) >= 1:
                return values[0]  # 第一列是日期
            else:
                return today_str()  # 默认返回今天
        except Exception:
            return today_str()

    def choose_excel_dir(self):
        """Choose Excel directory"""
        try:
            d = filedialog.askdirectory(title="选择Excel文件夹",
                                        initialdir=self.data.get("excel_dir", HOME))
            if d:
                self.excel_dir_var.set(d)
                self.data["excel_dir"] = d
                save_data(self.data)
        except Exception as e:
            logging.error(f"Failed to choose Excel directory: {e}")

    def manual_import_excel(self):
        """Manual import from Excel"""
        try:
            count = import_orders_from_excel(self.data)
            if count > 0:
                save_data(self.data)
                self.refresh_order_tables()  # 刷新所有表格
                self.update_reminder_text()
            
            messagebox.showinfo("导入完成", f"Excel数据导入完成！共导入{count}个订单")
        except Exception as e:
            logging.error(f"Failed to manual import Excel: {e}")
            messagebox.showerror("错误", f"导入失败：{e}")

    def save_all_settings(self, cp_window):
        """Save all settings"""
        try:
            for i in range(7):
                if i in self.work_entries:
                    self.data["work_plan"][str(i)] = self.work_entries[i].get().strip()
            
            try:
                if self.custom_interval_entry:
                    custom_val = self.custom_interval_entry.get().strip()
                    if custom_val:
                        custom_val = int(custom_val)
                        if custom_val <= 0:
                            messagebox.showerror("错误", "提醒间隔必须大于0分钟")
                            return
                        self.data["reminder_interval"] = custom_val
                    else:
                        sel = self.interval_combo.get()
                        for label, val in self.interval_options:
                            if label == sel:
                                self.data["reminder_interval"] = val
                                break
            except ValueError:
                messagebox.showerror("错误", "请输入有效的提醒间隔（整数分钟）")
                return
            
            if self.reminder_chk_var:
                self.data["reminder_enabled"] = self.reminder_chk_var.get()
            if self.startup_chk_var:
                self.data["startup_enabled"] = self.startup_chk_var.get()
            if self.excel_dir_var:
                excel_dir = self.excel_dir_var.get().strip()
                if excel_dir and os.path.isdir(excel_dir):
                    self.data["excel_dir"] = excel_dir
                else:
                    self.data["excel_dir"] = self.data.get("excel_dir", default_data["excel_dir"])
            
            save_data(self.data)
            set_startup(self.data["startup_enabled"])
            self.update_reminder_text()
            
            messagebox.showinfo("保存成功", "所有设置已保存！✨")
            cp_window.destroy()
            self.schedule_reminder()
            
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
            messagebox.showerror("保存失败", f"保存设置错误：{str(e)}")

    def show_about(self):
        """Show about info"""
        try:
            act_data = load_activation()
            if act_data.get("activated", False):
                status = "✅ 已激活"
            else:
                start = act_data.get("trial_start")
                if start:
                    try:
                        start_date = datetime.date.fromisoformat(start)
                        days_used = (datetime.date.today() - start_date).days
                        days_left = max(TRIAL_DAYS - days_used, 0)
                        status = f"⏳ 试用中，剩余 {days_left} 天"
                    except ValueError:
                        status = f"⏳ 试用中，剩余 {TRIAL_DAYS} 天"
                else:
                    status = f"⏳ 试用中，剩余 {TRIAL_DAYS} 天"
            
            deps_status = []
            install_commands = []
            if not EXCEL_AVAILABLE:
                deps_status.append("❌ Excel导入功能不可用(缺少openpyxl)")
                install_commands.append("pip install openpyxl")
            if not CALENDAR_AVAILABLE:
                deps_status.append("❌ 日期选择器不可用(缺少tkcalendar)")
                install_commands.append("pip install tkcalendar")
            if not PIL_AVAILABLE:
                deps_status.append("❌ 托盘图标不可用(缺少Pillow)")
                install_commands.append("pip install pillow")
            if not PYSTRAY_AVAILABLE:
                deps_status.append("❌ 系统托盘不可用(缺少pystray)")
                install_commands.append("pip install pystray")
            if not DATEUTIL_AVAILABLE:
                deps_status.append("❌ 增强日期解析不可用(缺少python-dateutil)")
                install_commands.append("pip install python-dateutil")
            if not SCREENINFO_AVAILABLE:
                deps_status.append("❌ 多显示器支持不可用(缺少screeninfo)")
                install_commands.append("pip install screeninfo")
            
            deps_text = "\n".join(deps_status) if deps_status else "✅ 所有功能正常"
            
            msg = f"📌 程序名称：昱景每日提醒\n✨ 版本号：v2.0.0 美化版\n👨‍💻 开发者：坤坤\n🔐 激活状态：{status}\n\n📋 功能状态：\n{deps_text}\n\n💡 感谢使用本程序！"
            messagebox.showinfo("关于程序", msg)
        except Exception as e:
            logging.error(f"Failed to show about info: {e}")

    def show_clock_notification(self, title, message, is_clock_in=True):
        """显示上下班打卡提醒气泡"""
        try:
            # 创建气泡窗口
            bubble = tk.Toplevel(self.root)
            bubble.title("打卡提醒")
            bubble.overrideredirect(True)  # 移除标题栏
            bubble.attributes('-topmost', True)  # 置顶显示
            bubble.configure(bg=COLORS["primary"])
            
            # 设置窗口大小和位置（右下角）
            bubble_width = 300
            bubble_height = 100
            screen_width = bubble.winfo_screenwidth()
            screen_height = bubble.winfo_screenheight()
            x = screen_width - bubble_width - 20
            y = screen_height - bubble_height - 80  # 避免任务栏遮挡
            
            bubble.geometry(f"{bubble_width}x{bubble_height}+{x}+{y}")
            
            # 创建内容框架
            content_frame = tk.Frame(bubble, bg=COLORS["primary"])
            content_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # 图标和标题
            icon_text = "🌅" if is_clock_in else "🌆"
            title_label = tk.Label(content_frame, text=f"{icon_text} {title}",
                                 font=FONTS["section"], fg="white", bg=COLORS["primary"])
            title_label.pack(anchor="w", pady=(0, 5))
            
            # 消息内容
            message_label = tk.Label(content_frame, text=message,
                                   font=FONTS["default"], fg="white", bg=COLORS["primary"],
                                   wraplength=280, justify="left")
            message_label.pack(anchor="w")
            
            # 自动关闭定时器
            bubble.after(5000, bubble.destroy)  # 5秒后自动关闭
            
            # 点击关闭
            def close_bubble(event):
                bubble.destroy()
            
            bubble.bind("<Button-1>", close_bubble)
            title_label.bind("<Button-1>", close_bubble)
            message_label.bind("<Button-1>", close_bubble)
            
            # 添加关闭按钮
            close_btn = tk.Label(bubble, text="×", font=FONTS["subtitle"],
                               fg="white", bg=COLORS["primary"], cursor="hand2")
            close_btn.place(relx=0.95, rely=0.1, anchor="ne")
            close_btn.bind("<Button-1>", close_bubble)
            
        except Exception as e:
            logging.error(f"Failed to show clock notification: {e}")

    def show_custom_reminder_notification(self, title, message):
        """显示自定义提醒气泡"""
        try:
            # 创建气泡窗口
            bubble = tk.Toplevel(self.root)
            bubble.title("自定义提醒")
            bubble.overrideredirect(True)  # 移除标题栏
            bubble.attributes('-topmost', True)  # 置顶显示
            bubble.configure(bg=COLORS["accent"])
            
            # 设置窗口大小和位置（右下角）
            bubble_width = 320
            bubble_height = 120
            screen_width = bubble.winfo_screenwidth()
            screen_height = bubble.winfo_screenheight()
            x = screen_width - bubble_width - 20
            y = screen_height - bubble_height - 80  # 避免任务栏遮挡
            
            bubble.geometry(f"{bubble_width}x{bubble_height}+{x}+{y}")
            
            # 创建内容框架
            content_frame = tk.Frame(bubble, bg=COLORS["accent"])
            content_frame.pack(fill="both", expand=True, padx=12, pady=12)
            
            # 图标和标题
            title_label = tk.Label(content_frame, text=f"🔔 {title}",
                                 font=FONTS["section"], fg="white", bg=COLORS["accent"])
            title_label.pack(anchor="w", pady=(0, 8))
            
            # 消息内容
            message_label = tk.Label(content_frame, text=message,
                                   font=FONTS["default"], fg="white", bg=COLORS["accent"],
                                   wraplength=290, justify="left")
            message_label.pack(anchor="w")
            
            # 自动关闭定时器
            bubble.after(6000, bubble.destroy)  # 6秒后自动关闭
            
            # 点击关闭
            def close_bubble(event):
                bubble.destroy()
            
            bubble.bind("<Button-1>", close_bubble)
            title_label.bind("<Button-1>", close_bubble)
            message_label.bind("<Button-1>", close_bubble)
            
            # 添加关闭按钮
            close_btn = tk.Label(bubble, text="×", font=FONTS["subtitle"],
                               fg="white", bg=COLORS["accent"], cursor="hand2")
            close_btn.place(relx=0.95, rely=0.1, anchor="ne")
            close_btn.bind("<Button-1>", close_bubble)
            
            logging.info(f"Custom reminder notification shown: {title} - {message}")
            
        except Exception as e:
            logging.error(f"Failed to show custom reminder notification: {e}")

    def test_custom_reminder_notification(self):
        """测试自定义提醒气泡"""
        try:
            self.show_custom_reminder_notification("测试提醒", "这是一个测试提醒消息，用于验证气泡通知功能是否正常工作。")
            messagebox.showinfo("测试完成", "测试提醒已弹出，请查看右下角的气泡通知！")
        except Exception as e:
            logging.error(f"Failed to test custom reminder notification: {e}")
            messagebox.showerror("测试失败", f"测试提醒失败：{e}")

    def schedule_clock_reminders(self):
        """安排上下班打卡提醒"""
        try:
            # 取消现有的定时器
            if self.clock_in_timer:
                self.root.after_cancel(self.clock_in_timer)
                self.clock_in_timer = None
            if self.clock_out_timer:
                self.root.after_cancel(self.clock_out_timer)
                self.clock_out_timer = None
            
            clock_settings = self.data.get("clock_settings", {})
            
            # 上班提醒
            if clock_settings.get("clock_in_enabled", False):
                clock_in_time = clock_settings.get("clock_in_time", "09:00")
                self.schedule_clock_reminder(clock_in_time, True)
            
            # 下班提醒
            if clock_settings.get("clock_out_enabled", False):
                clock_out_time = clock_settings.get("clock_out_time", "18:00")
                self.schedule_clock_reminder(clock_out_time, False)
                
        except Exception as e:
            logging.error(f"Failed to schedule clock reminders: {e}")

    def schedule_custom_reminders(self):
        """安排自定义提醒"""
        try:
            # 取消现有的自定义提醒定时器
            for timer_id in self.custom_reminder_timers.values():
                if timer_id:
                    self.root.after_cancel(timer_id)
            self.custom_reminder_timers.clear()
            
            # 获取自定义提醒配置
            custom_reminders = self.data.get("custom_reminders", [])
            
            for i, reminder in enumerate(custom_reminders):
                if reminder.get("enabled", True):
                    time_str = reminder.get("time", "")
                    content = reminder.get("content", "")
                    
                    if time_str and content:
                        timer_id = self.schedule_custom_reminder(time_str, content, i)
                        self.custom_reminder_timers[i] = timer_id
                        
            logging.info(f"Scheduled {len(self.custom_reminder_timers)} custom reminders")
            
        except Exception as e:
            logging.error(f"Failed to schedule custom reminders: {e}")

    def schedule_custom_reminder(self, time_str, content, reminder_index):
        """安排单个自定义提醒"""
        try:
            # 获取提醒配置
            custom_reminders = self.data.get("custom_reminders", [])
            if reminder_index >= len(custom_reminders):
                return None
                
            reminder = custom_reminders[reminder_index]
            date_type = reminder.get("date_type", "daily")
            specific_date = reminder.get("specific_date", "")
            
            # 解析时间
            hour, minute = map(int, time_str.split(':'))
            now = datetime.datetime.now()
            
            if date_type == "specific" and specific_date:
                # 特定日期提醒
                try:
                    target_date = datetime.date.fromisoformat(specific_date)
                    target_time = datetime.datetime.combine(target_date, datetime.time(hour, minute))
                    
                    # 如果特定日期已过，不安排提醒
                    if target_time <= now:
                        logging.info(f"Specific date reminder '{content}' for {specific_date} has passed, skipping")
                        return None
                        
                except ValueError:
                    logging.error(f"Invalid specific date format: {specific_date}")
                    return None
            else:
                # 每日重复提醒
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # 如果今天的时间已过，安排明天
                if target_time <= now:
                    target_time += datetime.timedelta(days=1)
            
            # 计算延迟时间（毫秒）
            delay_ms = int((target_time - now).total_seconds() * 1000)
            
            # 安排提醒
            timer_id = self.root.after(delay_ms, 
                                     lambda: self.trigger_custom_reminder(time_str, content, reminder_index))
            
            date_info = specific_date if date_type == "specific" else "daily"
            logging.info(f"Scheduled custom reminder '{content}' for {time_str} on {date_info}")
            return timer_id
            
        except Exception as e:
            logging.error(f"Failed to schedule custom reminder: {e}")
            return None

    def trigger_custom_reminder(self, time_str, content, reminder_index):
        """触发自定义提醒"""
        try:
            # 显示气泡通知
            self.show_custom_reminder_notification("自定义提醒", content)
            
            # 获取提醒配置
            custom_reminders = self.data.get("custom_reminders", [])
            if reminder_index < len(custom_reminders):
                reminder = custom_reminders[reminder_index]
                date_type = reminder.get("date_type", "daily")
                
                # 只有每日重复的提醒才重新安排
                if date_type == "daily":
                    timer_id = self.schedule_custom_reminder(time_str, content, reminder_index)
                    self.custom_reminder_timers[reminder_index] = timer_id
                else:
                    # 特定日期提醒触发后不再重新安排
                    if reminder_index in self.custom_reminder_timers:
                        del self.custom_reminder_timers[reminder_index]
            
            logging.info(f"Triggered custom reminder: {content} at {time_str}")
            
        except Exception as e:
            logging.error(f"Failed to trigger custom reminder: {e}")

    def schedule_clock_reminder(self, time_str, is_clock_in):
        """安排单个打卡提醒"""
        try:
            # 解析时间
            hour, minute = map(int, time_str.split(':'))
            now = datetime.datetime.now()
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 如果今天的时间已过，安排明天
            if target_time <= now:
                target_time += datetime.timedelta(days=1)
            
            # 计算延迟时间（毫秒）
            delay_ms = int((target_time - now).total_seconds() * 1000)
            
            # 安排提醒
            if is_clock_in:
                self.clock_in_timer = self.root.after(delay_ms, self.trigger_clock_in_reminder)
            else:
                self.clock_out_timer = self.root.after(delay_ms, self.trigger_clock_out_reminder)
                
            logging.info(f"Scheduled {'clock in' if is_clock_in else 'clock out'} reminder for {time_str}")
            
        except Exception as e:
            logging.error(f"Failed to schedule clock reminder: {e}")

    def trigger_clock_in_reminder(self):
        """触发上班提醒"""
        try:
            clock_settings = self.data.get("clock_settings", {})
            title = "上班打卡提醒"
            message = clock_settings.get("clock_in_message", "上班时间到了，记得打卡哦！")
            self.show_clock_notification(title, message, True)
            
            # 安排明天的提醒
            self.schedule_clock_reminder(clock_settings.get("clock_in_time", "09:00"), True)
            
        except Exception as e:
            logging.error(f"Failed to trigger clock in reminder: {e}")

    def trigger_clock_out_reminder(self):
        """触发下班提醒"""
        try:
            clock_settings = self.data.get("clock_settings", {})
            title = "下班打卡提醒"
            message = clock_settings.get("clock_out_message", "下班时间到了，记得打卡哦！")
            self.show_clock_notification(title, message, False)
            
            # 安排明天的提醒
            self.schedule_clock_reminder(clock_settings.get("clock_out_time", "18:00"), False)
            
        except Exception as e:
            logging.error(f"Failed to trigger clock out reminder: {e}")

    def open_custom_reminder_settings(self):
        """打开自定义提醒设置窗口"""
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title("🔔 自定义提醒设置")
            dlg.configure(bg=COLORS["bg_main"])
            center_window(dlg, 900, 650)
            dlg.resizable(True, True)


            # 主内容区域
            content_frame = tk.Frame(dlg, bg=COLORS["bg_main"])
            content_frame.pack(fill="both", expand=True, padx=20, pady=20)

            # 左侧：提醒列表
            left_frame = tk.Frame(content_frame, bg=COLORS["bg_card"])
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
            
            tk.Label(left_frame, text="📋 提醒事项列表", font=FONTS["content"], 
                    bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(pady=10)
            
            # 创建提醒列表
            list_frame = tk.Frame(left_frame, bg=COLORS["bg_card"])
            list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            
            # 表格显示提醒事项
            reminder_tree = ttk.Treeview(list_frame, columns=("date", "time", "content", "enabled"), show="headings", height=12)
            reminder_tree.heading("date", text="日期")
            reminder_tree.heading("time", text="时间")
            reminder_tree.heading("content", text="提醒内容")
            reminder_tree.heading("enabled", text="状态")
            reminder_tree.column("date", width=120, anchor="center")
            reminder_tree.column("time", width=80, anchor="center")
            reminder_tree.column("content", width=200, anchor="w")
            reminder_tree.column("enabled", width=80, anchor="center")
            
            # 滚动条
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=reminder_tree.yview)
            reminder_tree.configure(yscrollcommand=scrollbar.set)
            
            reminder_tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # 右侧：编辑表单
            right_frame = tk.Frame(content_frame, bg=COLORS["bg_card"])
            right_frame.pack(side="right", fill="y", padx=(10, 0))
            right_frame.configure(width=400)
            
            
            # 编辑表单
            form_frame = tk.Frame(right_frame, bg=COLORS["bg_card"])
            form_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            # 提醒时间输入 - 时间轴形式
            tk.Label(form_frame, text="提醒时间:", font=FONTS["content"], 
                    bg=COLORS["bg_card"]).pack(anchor="w", pady=(0, 5))
            
            # 时间轴容器
            time_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            time_frame.pack(fill="x", pady=(0, 10))
            
            # 小时选择
            hour_frame = tk.Frame(time_frame, bg=COLORS["bg_card"])
            hour_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            tk.Label(hour_frame, text="时", font=FONTS["default"], 
                    bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="w")
            
            hour_var = tk.IntVar(value=9)
            hour_scale = tk.Scale(hour_frame, from_=0, to=23, orient="horizontal", 
                                variable=hour_var, bg=COLORS["bg_card"], 
                                font=FONTS["default"], length=150, 
                                showvalue=True, tickinterval=4)
            hour_scale.pack(fill="x", pady=(2, 0))
            
            # 分钟选择
            minute_frame = tk.Frame(time_frame, bg=COLORS["bg_card"])
            minute_frame.pack(side="right", fill="x", expand=True, padx=(5, 0))
            
            tk.Label(minute_frame, text="分", font=FONTS["default"], 
                    bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="w")
            
            minute_var = tk.IntVar(value=0)
            minute_scale = tk.Scale(minute_frame, from_=0, to=59, orient="horizontal", 
                                  variable=minute_var, bg=COLORS["bg_card"], 
                                  font=FONTS["default"], length=150, 
                                  showvalue=True, tickinterval=15)
            minute_scale.pack(fill="x", pady=(2, 0))
            
            # 时间显示标签
            time_display_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            time_display_frame.pack(fill="x", pady=(5, 0))
            
            time_display_label = tk.Label(time_display_frame, text="09:00", 
                                        font=FONTS["section"], bg=COLORS["bg_card"], 
                                        fg=COLORS["primary"])
            time_display_label.pack()
            
            # 更新时间显示
            def update_time_display(*args):
                hour = hour_var.get()
                minute = minute_var.get()
                time_str = f"{hour:02d}:{minute:02d}"
                time_display_label.config(text=time_str)
            
            hour_var.trace("w", update_time_display)
            minute_var.trace("w", update_time_display)
            
            # 快捷时间按钮
            quick_time_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            quick_time_frame.pack(fill="x", pady=(10, 0))
            
            tk.Label(quick_time_frame, text="快捷时间:", font=FONTS["default"], 
                    bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 5))
            
            quick_buttons_frame = tk.Frame(quick_time_frame, bg=COLORS["bg_card"])
            quick_buttons_frame.pack(fill="x")
            
            # 定义快捷时间
            quick_times = [
                ("09:00", "上班"), ("12:00", "午休"), ("13:00", "下午"), 
                ("18:00", "下班"), ("20:00", "晚上"), ("22:00", "睡前")
            ]
            
            def set_quick_time(hour, minute):
                hour_var.set(hour)
                minute_var.set(minute)
            
            for i, (time_str, label) in enumerate(quick_times):
                hour, minute = map(int, time_str.split(':'))
                btn = create_modern_button(quick_buttons_frame, label, 
                                         lambda h=hour, m=minute: set_quick_time(h, m),
                                         button_type="primary")
                btn.pack(side="left", padx=(0, 8), pady=2)
            
            # 日期选择
            date_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            date_frame.pack(fill="x", pady=(0, 10))
            
            tk.Label(date_frame, text="提醒日期:", font=FONTS["content"], 
                    bg=COLORS["bg_card"]).pack(anchor="w", pady=(0, 5))
            
            # 日期类型选择
            date_type_frame = tk.Frame(date_frame, bg=COLORS["bg_card"])
            date_type_frame.pack(fill="x", pady=(0, 5))
            
            date_type_var = tk.StringVar(value="daily")
            
            daily_radio = tk.Radiobutton(date_type_frame, text="每日重复", 
                                       variable=date_type_var, value="daily",
                                       bg=COLORS["bg_card"], font=FONTS["default"],
                                       command=lambda: self.toggle_date_input(date_type_var, specific_date_frame))
            daily_radio.pack(side="left", padx=(0, 20))
            
            specific_radio = tk.Radiobutton(date_type_frame, text="特定日期", 
                                          variable=date_type_var, value="specific",
                                          bg=COLORS["bg_card"], font=FONTS["default"],
                                          command=lambda: self.toggle_date_input(date_type_var, specific_date_frame))
            specific_radio.pack(side="left")
            
            # 特定日期输入框架
            specific_date_frame = tk.Frame(date_frame, bg=COLORS["bg_card"])
            specific_date_frame.pack(fill="x", pady=(5, 0))
            
            # 特定日期输入
            if CALENDAR_AVAILABLE:
                specific_date_widget = DateEntry(specific_date_frame, width=16, date_pattern="yyyy-mm-dd",
                                               font=FONTS["content"])
            else:
                specific_date_widget = tk.Entry(specific_date_frame, width=18, font=FONTS["content"])
                specific_date_widget.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
            specific_date_widget.pack(side="left", padx=(0, 10))
            
            # 快捷日期按钮
            quick_date_frame = tk.Frame(specific_date_frame, bg=COLORS["bg_card"])
            quick_date_frame.pack(side="left")
            
            def set_today():
                today = datetime.date.today()
                if CALENDAR_AVAILABLE:
                    specific_date_widget.set_date(today)
                else:
                    specific_date_widget.delete(0, tk.END)
                    specific_date_widget.insert(0, today.strftime("%Y-%m-%d"))
            
            def set_tomorrow():
                tomorrow = datetime.date.today() + datetime.timedelta(days=1)
                if CALENDAR_AVAILABLE:
                    specific_date_widget.set_date(tomorrow)
                else:
                    specific_date_widget.delete(0, tk.END)
                    specific_date_widget.insert(0, tomorrow.strftime("%Y-%m-%d"))
            
            today_btn = create_modern_button(quick_date_frame, "今天", set_today,
                                           button_type="success")
            today_btn.pack(side="left", padx=(0, 8))
            
            tomorrow_btn = create_modern_button(quick_date_frame, "明天", set_tomorrow,
                                              button_type="warning")
            tomorrow_btn.pack(side="left")
            
            # 初始隐藏特定日期输入
            specific_date_frame.pack_forget()
            
            # 提醒内容输入
            tk.Label(form_frame, text="提醒内容:", font=FONTS["content"], 
                    bg=COLORS["bg_card"]).pack(anchor="w", pady=(0, 5))
            content_var = tk.StringVar()
            content_entry = tk.Entry(form_frame, textvariable=content_var, font=FONTS["content"])
            content_entry.pack(fill="x", pady=(0, 10))
            
            # 启用开关
            enabled_var = tk.BooleanVar(value=True)
            enabled_check = tk.Checkbutton(form_frame, text="启用此提醒",
                                         variable=enabled_var,
                                         bg=COLORS["bg_card"], font=FONTS["content"])
            enabled_check.pack(anchor="w", pady=(0, 10))
            
            # 按钮区域
            btn_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            btn_frame.pack(fill="x", pady=10)
            
            def load_reminders():
                """加载提醒列表"""
                # 清空现有数据
                for item in reminder_tree.get_children():
                    reminder_tree.delete(item)
                
                # 添加提醒数据
                custom_reminders = self.data.get("custom_reminders", [])
                
                for i, reminder in enumerate(custom_reminders):
                    time_str = reminder.get("time", "")
                    content = reminder.get("content", "")
                    enabled = reminder.get("enabled", True)
                    date_type = reminder.get("date_type", "daily")
                    specific_date = reminder.get("specific_date", "")
                    
                    # 显示日期
                    if date_type == "daily":
                        date_display = "每日重复"
                    else:
                        date_display = specific_date if specific_date else "未设置"
                    
                    status = "✅ 启用" if enabled else "❌ 禁用"
                    
                    reminder_tree.insert("", "end", iid=str(i), values=(date_display, time_str, content, status))
            
            def add_reminder():
                """添加或更新提醒"""
                # 从时间轴获取时间
                hour = hour_var.get()
                minute = minute_var.get()
                time_str = f"{hour:02d}:{minute:02d}"
                content = content_var.get().strip()
                enabled = enabled_var.get()
                date_type = date_type_var.get()
                
                if not content:
                    messagebox.showerror("错误", "请输入提醒内容")
                    return
                
                # 获取特定日期
                specific_date = ""
                if date_type == "specific":
                    try:
                        if CALENDAR_AVAILABLE:
                            specific_date = specific_date_widget.get_date().strftime("%Y-%m-%d")
                        else:
                            specific_date = specific_date_widget.get().strip()
                            # 验证日期格式
                            datetime.date.fromisoformat(specific_date)
                    except ValueError:
                        messagebox.showerror("错误", "请输入有效的日期格式（YYYY-MM-DD）")
                        return
                    except Exception as e:
                        messagebox.showerror("错误", f"日期获取失败：{e}")
                        return
                
                # 添加提醒
                reminder = {
                    "time": time_str,
                    "content": content,
                    "enabled": enabled,
                    "date_type": date_type,
                    "specific_date": specific_date
                }
                
                self.data.setdefault("custom_reminders", []).append(reminder)
                save_data(self.data)
                load_reminders()
                
                # 清空输入框
                hour_var.set(9)
                minute_var.set(0)
                content_var.set("")
                enabled_var.set(True)
                date_type_var.set("daily")
                specific_date_frame.pack_forget()
                
                # 重新安排提醒
                self.schedule_custom_reminders()
                messagebox.showinfo("成功", f"提醒 '{content}' 已添加！")
            
            def delete_reminder():
                """删除选中的提醒"""
                selection = reminder_tree.selection()
                if not selection:
                    messagebox.showwarning("提示", "请选择要删除的提醒")
                    return
                
                item_id = selection[0]
                try:
                    index = int(item_id)
                    custom_reminders = self.data.get("custom_reminders", [])
                    
                    if 0 <= index < len(custom_reminders):
                        reminder = custom_reminders[index]
                        content = reminder.get("content", "")
                        
                        if messagebox.askyesno("确认删除", f"确定要删除提醒 '{content}' 吗？"):
                            del custom_reminders[index]
                            save_data(self.data)
                            load_reminders()
                            hour_var.set(9)
                            minute_var.set(0)
                            content_var.set("")
                            enabled_var.set(True)
                            date_type_var.set("daily")
                            specific_date_frame.pack_forget()
                            # 重新安排提醒
                            self.schedule_custom_reminders()
                            messagebox.showinfo("成功", f"提醒 '{content}' 已删除！")
                except (ValueError, IndexError):
                    messagebox.showerror("错误", "删除失败，请重试")
            
            def toggle_reminder():
                """切换提醒的启用状态"""
                selection = reminder_tree.selection()
                if not selection:
                    messagebox.showwarning("提示", "请选择要切换状态的提醒")
                    return
                
                item_id = selection[0]
                try:
                    index = int(item_id)
                    custom_reminders = self.data.get("custom_reminders", [])
                    
                    if 0 <= index < len(custom_reminders):
                        reminder = custom_reminders[index]
                        current_status = reminder.get("enabled", True)
                        reminder["enabled"] = not current_status
                        
                        save_data(self.data)
                        load_reminders()
                        # 重新安排提醒
                        self.schedule_custom_reminders()
                        
                        status_text = "启用" if reminder["enabled"] else "禁用"
                        messagebox.showinfo("状态更新", f"提醒状态已更新为: {status_text}")
                except (ValueError, IndexError):
                    messagebox.showerror("错误", "状态切换失败，请重试")
            
            # 添加/更新按钮
            add_btn = create_modern_button(btn_frame, "➕ 添加提醒", add_reminder,
                                         button_type="success")
            add_btn.pack(fill="x", pady=(0, 8))
            
            # 删除按钮
            delete_btn = create_modern_button(btn_frame, "🗑️ 删除", delete_reminder,
                                            button_type="error")
            delete_btn.pack(fill="x", pady=(0, 8))
            
            # 启用/禁用切换按钮
            toggle_btn = create_modern_button(btn_frame, "🔄 切换状态", toggle_reminder,
                                            button_type="warning")
            toggle_btn.pack(fill="x", pady=(0, 8))
            
            # 测试提醒按钮
            test_btn = create_modern_button(btn_frame, "🧪 测试提醒", 
                                          lambda: self.test_custom_reminder_notification(),
                                          button_type="primary")
            test_btn.pack(fill="x", pady=(0, 5))
            
            # 绑定事件
            reminder_tree.bind("<<TreeviewSelect>>", 
                             lambda e: self.on_reminder_select(reminder_tree, hour_var, minute_var, content_var, enabled_var, date_type_var, specific_date_widget, specific_date_frame))
            reminder_tree.bind("<Double-1>", lambda e: toggle_reminder())
            
            # 初始加载提醒列表
            load_reminders()
            
        except Exception as e:
            logging.error(f"Failed to open custom reminder settings: {e}")
            messagebox.showerror("错误", f"打开自定义提醒设置窗口失败：{e}")
    
    def on_reminder_select(self, tree, hour_var, minute_var, content_var, enabled_var, date_type_var, specific_date_widget, specific_date_frame):
        """选择提醒时的事件处理"""
        selection = tree.selection()
        if selection:
            item_id = selection[0]
            try:
                index = int(item_id)
                custom_reminders = self.data.get("custom_reminders", [])
                
                if 0 <= index < len(custom_reminders):
                    reminder = custom_reminders[index]
                    time_str = reminder.get("time", "09:00")
                    
                    # 解析时间字符串
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        hour_var.set(hour)
                        minute_var.set(minute)
                    except ValueError:
                        hour_var.set(9)
                        minute_var.set(0)
                    
                    content_var.set(reminder.get("content", ""))
                    enabled_var.set(reminder.get("enabled", True))
                    
                    # 设置日期类型和特定日期
                    date_type = reminder.get("date_type", "daily")
                    date_type_var.set(date_type)
                    
                    if date_type == "specific":
                        specific_date = reminder.get("specific_date", "")
                        if specific_date:
                            try:
                                if CALENDAR_AVAILABLE:
                                    specific_date_widget.set_date(datetime.date.fromisoformat(specific_date))
                                else:
                                    specific_date_widget.delete(0, tk.END)
                                    specific_date_widget.insert(0, specific_date)
                            except ValueError:
                                pass
                        specific_date_frame.pack(fill="x", pady=(5, 0))
                    else:
                        specific_date_frame.pack_forget()
                        
            except (ValueError, IndexError):
                pass

    def toggle_date_input(self, date_type_var, specific_date_frame):
        """切换日期输入显示"""
        try:
            if date_type_var.get() == "specific":
                specific_date_frame.pack(fill="x", pady=(5, 0))
            else:
                specific_date_frame.pack_forget()
        except Exception as e:
            logging.error(f"Failed to toggle date input: {e}")

    def open_clock_settings(self):
        """打开上下班打卡设置窗口"""
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title("⏰ 上下班打卡提醒")
            dlg.configure(bg=COLORS["bg_main"])
            center_window(dlg, 500, 550)
            dlg.resizable(False, False)

            # 标题
            title_frame = tk.Frame(dlg, bg=COLORS["primary"], height=50)
            title_frame.pack(fill="x")
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text="⏰ 上下班打卡提醒", font=FONTS["title"],
                     bg=COLORS["primary"], fg="white").pack(pady=12)

            # 主内容区域
            content_frame = tk.Frame(dlg, bg=COLORS["bg_main"])
            content_frame.pack(fill="both", expand=True, padx=20, pady=20)

            clock_settings = self.data.get("clock_settings", {})

            # 上班设置
            clock_in_frame = create_card_frame(content_frame, "🌅 上班打卡设置")
            clock_in_frame.pack(fill="x", pady=(0, 10))

            # 上班开关
            clock_in_enabled_var = tk.BooleanVar(value=clock_settings.get("clock_in_enabled", False))
            clock_in_check = tk.Checkbutton(clock_in_frame, text="启用上班打卡提醒",
                                          variable=clock_in_enabled_var,
                                          bg=COLORS["bg_card"], font=FONTS["section"])
            clock_in_check.pack(anchor="w", padx=15, pady=(12, 8))

            # 上班时间设置
            time_frame1 = tk.Frame(clock_in_frame, bg=COLORS["bg_card"])
            time_frame1.pack(fill="x", padx=15, pady=(0, 8))

            tk.Label(time_frame1, text="提醒时间：", bg=COLORS["bg_card"],
                     font=FONTS["content"]).pack(side="left", padx=(0, 10))

            clock_in_time_var = tk.StringVar(value=clock_settings.get("clock_in_time", "09:00"))
            clock_in_time_entry = tk.Entry(time_frame1, textvariable=clock_in_time_var,
                                         font=FONTS["content"], width=10)
            clock_in_time_entry.pack(side="left", padx=(0, 20))

            tk.Label(time_frame1, text="格式：HH:MM", bg=COLORS["bg_card"],
                     font=FONTS["default"], fg=COLORS["text_secondary"]).pack(side="left")

            # 上班提醒消息
            msg_frame1 = tk.Frame(clock_in_frame, bg=COLORS["bg_card"])
            msg_frame1.pack(fill="x", padx=15, pady=(0, 8))

            tk.Label(msg_frame1, text="提醒消息：", bg=COLORS["bg_card"],
                     font=FONTS["content"]).pack(anchor="w", pady=(0, 5))

            clock_in_msg_var = tk.StringVar(value=clock_settings.get("clock_in_message", "上班时间到了，记得打卡哦！"))
            clock_in_msg_entry = tk.Entry(msg_frame1, textvariable=clock_in_msg_var,
                                        font=FONTS["content"], width=50)
            clock_in_msg_entry.pack(fill="x")

            # 下班设置
            clock_out_frame = create_card_frame(content_frame, "🌆 下班打卡设置")
            clock_out_frame.pack(fill="x", pady=(0, 10))

            # 下班开关
            clock_out_enabled_var = tk.BooleanVar(value=clock_settings.get("clock_out_enabled", False))
            clock_out_check = tk.Checkbutton(clock_out_frame, text="启用下班打卡提醒",
                                           variable=clock_out_enabled_var,
                                           bg=COLORS["bg_card"], font=FONTS["section"])
            clock_out_check.pack(anchor="w", padx=15, pady=(12, 8))

            # 下班时间设置
            time_frame2 = tk.Frame(clock_out_frame, bg=COLORS["bg_card"])
            time_frame2.pack(fill="x", padx=15, pady=(0, 8))

            tk.Label(time_frame2, text="提醒时间：", bg=COLORS["bg_card"],
                     font=FONTS["content"]).pack(side="left", padx=(0, 10))

            clock_out_time_var = tk.StringVar(value=clock_settings.get("clock_out_time", "18:00"))
            clock_out_time_entry = tk.Entry(time_frame2, textvariable=clock_out_time_var,
                                          font=FONTS["content"], width=10)
            clock_out_time_entry.pack(side="left", padx=(0, 20))

            tk.Label(time_frame2, text="格式：HH:MM", bg=COLORS["bg_card"],
                     font=FONTS["default"], fg=COLORS["text_secondary"]).pack(side="left")

            # 下班提醒消息
            msg_frame2 = tk.Frame(clock_out_frame, bg=COLORS["bg_card"])
            msg_frame2.pack(fill="x", padx=15, pady=(0, 8))

            tk.Label(msg_frame2, text="提醒消息：", bg=COLORS["bg_card"],
                     font=FONTS["content"]).pack(anchor="w", pady=(0, 5))

            clock_out_msg_var = tk.StringVar(value=clock_settings.get("clock_out_message", "下班时间到了，记得打卡哦！"))
            clock_out_msg_entry = tk.Entry(msg_frame2, textvariable=clock_out_msg_var,
                                         font=FONTS["content"], width=50)
            clock_out_msg_entry.pack(fill="x")

            # 按钮区域 - 固定在窗口底部
            btn_frame = tk.Frame(dlg, bg=COLORS["bg_main"], height=70)
            btn_frame.pack(side="bottom", fill="x", padx=20, pady=(10, 20))
            btn_frame.pack_propagate(False)
            
            # 按钮容器
            btn_container = tk.Frame(btn_frame, bg=COLORS["bg_main"])
            btn_container.pack(expand=True)

            def save_clock_settings():
                try:
                    # 验证时间格式
                    try:
                        datetime.datetime.strptime(clock_in_time_var.get(), "%H:%M")
                        datetime.datetime.strptime(clock_out_time_var.get(), "%H:%M")
                    except ValueError:
                        messagebox.showerror("错误", "时间格式不正确，请使用HH:MM格式（如09:00）")
                        return

                    # 保存设置
                    self.data.setdefault("clock_settings", {})
                    self.data["clock_settings"]["clock_in_enabled"] = clock_in_enabled_var.get()
                    self.data["clock_settings"]["clock_out_enabled"] = clock_out_enabled_var.get()
                    self.data["clock_settings"]["clock_in_time"] = clock_in_time_var.get()
                    self.data["clock_settings"]["clock_out_time"] = clock_out_time_var.get()
                    self.data["clock_settings"]["clock_in_message"] = clock_in_msg_var.get()
                    self.data["clock_settings"]["clock_out_message"] = clock_out_msg_var.get()

                    save_data(self.data)
                    
                    # 重新安排提醒
                    self.schedule_clock_reminders()
                    
                    messagebox.showinfo("保存成功", "上下班打卡设置已保存！")
                    dlg.destroy()
                    
                except Exception as e:
                    logging.error(f"Failed to save clock settings: {e}")
                    messagebox.showerror("保存失败", f"保存设置失败：{e}")

            def test_notification():
                """测试通知"""
                try:
                    if clock_in_enabled_var.get():
                        self.show_clock_notification("上班打卡提醒", clock_in_msg_var.get(), True)
                    if clock_out_enabled_var.get():
                        self.show_clock_notification("下班打卡提醒", clock_out_msg_var.get(), False)
                except Exception as e:
                    logging.error(f"Failed to test notification: {e}")

            # 测试按钮
            test_btn = create_modern_button(btn_container, "🔔 测试通知", test_notification, COLORS["warning"])
            test_btn.pack(side="left", padx=(0, 10))

            # 保存按钮
            save_btn = create_modern_button(btn_container, "💾 保存设置", save_clock_settings, COLORS["success"])
            save_btn.pack(side="right", padx=(10, 0))

            # 取消按钮
            cancel_btn = create_modern_button(btn_container, "❌ 取消", dlg.destroy, COLORS["text_secondary"])
            cancel_btn.pack(side="right")

        except Exception as e:
            logging.error(f"Failed to open clock settings: {e}")
            messagebox.showerror("错误", f"打开设置窗口失败：{e}")

    def on_closing(self):
        """Window close handling"""
        try:
            if PYSTRAY_AVAILABLE and PIL_AVAILABLE:
                self.minimize_to_tray()
            else:
                result = messagebox.askyesno("退出", "确定要退出程序吗？")
                if result:
                    self.root.destroy()
                    sys.exit(0)
        except Exception as e:
            logging.error(f"Failed to handle closing: {e}")
            self.root.destroy()
            sys.exit(0)

    def minimize_to_tray(self):
        """Minimize to system tray"""
        try:
            if not PYSTRAY_AVAILABLE or not PIL_AVAILABLE:
                self.root.iconify()
                return
            
            self.root.withdraw()
            image = self.create_tray_image()
            if image is None:
                self.root.iconify()
                return
            
            menu = (item('📂 打开程序', self.on_tray_show),
                    item('❌ 退出程序', self.on_tray_quit))
            self.tray_icon_obj = pystray.Icon("每日提醒", image, "昱景每日工作提醒", menu)
            self.tray_thread = threading.Thread(target=self.tray_icon_obj.run, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            logging.error(f"Tray function failed: {e}")
            self.root.iconify()

    def create_tray_image(self, size=64):
        """Create tray icon"""
        if not PIL_AVAILABLE:
            logging.warning("Pillow library unavailable, cannot create custom tray icon")
            return None
        
        try:
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(image)
            
            d.ellipse([4, 4, size-4, size-4], fill=(33, 150, 243, 255), outline=(25, 118, 210, 255), width=2)
            
            d.ellipse([size/2-8, size/2-8, size/2+8, size/2+8], fill=(255, 255, 255, 255))
            
            return image
        except Exception as e:
            logging.error(f"Failed to create tray icon: {e}")
            return None

    def on_tray_quit(self, icon, item):
        """Tray quit"""
        try:
            if self.tray_icon_obj:
                self.tray_icon_obj.stop()
                self.tray_icon_obj = None
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def on_tray_show(self, icon, item):
        """Tray show"""
        try:
            if self.tray_icon_obj:
                self.tray_icon_obj.stop()
                self.tray_icon_obj = None
        except Exception:
            pass
        try:
            self.root.after(0, lambda: self.root.deiconify())
        except Exception:
            pass

    def run(self):
        """Run application"""
        try:
            # 确保数据已加载
            self.data = load_data()
            
            # 初始化界面显示
            self.update_reminder_text()
            
            # 确保表格完全初始化后再刷新数据
            self.root.after(500, lambda: self.refresh_order_tables(['main_shipping', 'main_pre']))
            self.root.after(1000, lambda: self.refresh_order_tables(['main_shipping', 'main_pre']))
            self.root.after(1500, lambda: self.refresh_order_tables(['main_shipping', 'main_pre']))
            
            # 确保数据被正确加载和显示
            self.root.after(2000, self.ensure_data_loaded)
            
            if self.data.get("reminder_enabled", True) and check_trial(self.root):
                self.schedule_reminder()
            
            # 启动上下班打卡提醒
            self.schedule_clock_reminders()
            
            # 启动自定义提醒
            self.schedule_custom_reminders()
            
            if self.data.get("startup_enabled", False):
                try:
                    set_startup(True)
                except Exception as e:
                    logging.error(f"Failed to set startup: {e}")
            
            self.root.after(2500, self.show_welcome_message)
            
            self.root.mainloop()
            
        except Exception as e:
            logging.error(f"Failed to run app: {e}")
            messagebox.showerror("启动错误", f"程序启动失败：\n{e}")

    def open_festival_manager(self):
        """打开节日管理窗口"""
        try:
            # 创建节日管理窗口
            festival_window = tk.Toplevel(self.root)
            festival_window.title("🎊 节日管理")
            festival_window.geometry("900x700")
            festival_window.configure(bg=COLORS["bg_main"])
            festival_window.transient(self.root)
            festival_window.grab_set()
            
            # 保存窗口引用以便后续刷新
            self.festival_manager_window = festival_window
            
            # 居中显示
            center_window(festival_window, 900, 650)
            
            
            # 主内容区域
            main_frame = tk.Frame(festival_window, bg=COLORS["bg_main"])
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # 左侧：节日列表
            left_frame = tk.Frame(main_frame, bg=COLORS["bg_card"], relief="solid", bd=1)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
            
            tk.Label(left_frame, text="📅 当前节日设置", font=FONTS["content"], 
                    bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(pady=10)
            
            # 节日列表
            list_frame = tk.Frame(left_frame, bg=COLORS["bg_card"])
            list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            
            # 创建Treeview
            columns = ("日期", "节日名称", "状态")
            festival_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
            
            # 设置列标题
            festival_tree.heading("日期", text="日期 (MM-DD)")
            festival_tree.heading("节日名称", text="节日名称")
            festival_tree.heading("状态", text="状态")
            
            # 设置列宽
            festival_tree.column("日期", width=100)
            festival_tree.column("节日名称", width=200)
            festival_tree.column("状态", width=150)
            
            # 滚动条
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=festival_tree.yview)
            festival_tree.configure(yscrollcommand=scrollbar.set)
            
            festival_tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # 右侧：编辑区域
            right_frame = tk.Frame(main_frame, bg=COLORS["bg_card"], relief="solid", bd=1)
            right_frame.pack(side="right", fill="y", padx=(10, 0))
            right_frame.configure(width=300)
            
            
            # 编辑表单
            form_frame = tk.Frame(right_frame, bg=COLORS["bg_card"])
            form_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            # 日期输入
            tk.Label(form_frame, text="日期 (MM-DD):", font=FONTS["content"], 
                    bg=COLORS["bg_card"]).pack(anchor="w", pady=(0, 5))
            date_var = tk.StringVar()
            date_entry = tk.Entry(form_frame, textvariable=date_var, font=FONTS["content"])
            date_entry.pack(fill="x", pady=(0, 10))
            
            # 节日名称输入
            tk.Label(form_frame, text="节日名称:", font=FONTS["content"], 
                    bg=COLORS["bg_card"]).pack(anchor="w", pady=(0, 5))
            name_var = tk.StringVar()
            name_entry = tk.Entry(form_frame, textvariable=name_var, font=FONTS["content"])
            name_entry.pack(fill="x", pady=(0, 10))
            
            # 按钮区域
            btn_frame = tk.Frame(form_frame, bg=COLORS["bg_card"])
            btn_frame.pack(fill="x", pady=10)
            
            def load_festivals():
                """加载节日列表"""
                # 清空现有数据
                for item in festival_tree.get_children():
                    festival_tree.delete(item)
                
                # 添加节日数据
                today = datetime.date.today()
                festival_reminders = self.data.get("festival_reminders", {})
                
                for date_str, name in sorted(festival_reminders.items()):
                    try:
                        mm, dd = map(int, date_str.split('-'))
                        festival_date = datetime.date(today.year, mm, dd)
                        delta = (festival_date - today).days
                        
                        if delta == 0:
                            status = "🎊 今天"
                        elif delta == 1:
                            status = "🎈 明天"
                        elif 0 < delta <= 7:
                            status = f"📅 {delta}天后"
                        elif delta < 0:
                            status = f"⏰ 已过{abs(delta)}天"
                        else:
                            status = f"📅 {delta}天后"
                        
                        festival_tree.insert("", "end", values=(date_str, name, status))
                    except ValueError:
                        # 无效日期格式
                        festival_tree.insert("", "end", values=(date_str, name, "❌ 无效日期"))
            
            def add_festival():
                """添加或更新节日"""
                date_str = date_var.get().strip()
                name = name_var.get().strip()
                
                if not date_str or not name:
                    messagebox.showerror("错误", "请输入日期和节日名称")
                    return
                
                # 验证日期格式
                try:
                    mm, dd = date_str.split('-')
                    mm = int(mm)
                    dd = int(dd)
                    if not (1 <= mm <= 12 and 1 <= dd <= 31):
                        raise ValueError("日期超出范围")
                    # 测试日期是否有效
                    datetime.date(2024, mm, dd)
                except ValueError:
                    messagebox.showerror("错误", "日期格式不正确，请使用MM-DD格式（如01-01）")
                    return
                
                # 添加或更新节日
                self.data.setdefault("festival_reminders", {})[date_str] = name
                save_data(self.data)
                load_festivals()
                
                # 清空输入框
                date_var.set("")
                name_var.set("")
                
                # 强制更新主窗口显示
                self.update_reminder_text()
                messagebox.showinfo("成功", f"节日 '{name}' 已添加/更新，主窗口已更新！")
            
            def delete_festival():
                """删除选中的节日"""
                selection = festival_tree.selection()
                if not selection:
                    messagebox.showwarning("提示", "请选择要删除的节日")
                    return
                
                item = festival_tree.item(selection[0])
                values = item['values']
                if len(values) >= 2:
                    date_str = values[0]
                    name = values[1]
                    
                    if messagebox.askyesno("确认删除", f"确定要删除节日 '{name}' ({date_str}) 吗？"):
                        if date_str in self.data.get("festival_reminders", {}):
                            del self.data["festival_reminders"][date_str]
                            save_data(self.data)
                            load_festivals()
                            date_var.set("")
                            name_var.set("")
                            # 强制更新主窗口显示
                            self.update_reminder_text()
                            messagebox.showinfo("成功", f"节日 '{name}' 已删除，主窗口已更新！")
            
            def load_online_holidays():
                """从网络加载全年节日"""
                try:
                    # 显示加载进度
                    progress_window = tk.Toplevel(festival_window)
                    progress_window.title("加载节日数据")
                    progress_window.geometry("400x150")
                    progress_window.configure(bg=COLORS["bg_main"])
                    progress_window.transient(festival_window)
                    progress_window.grab_set()
                    
                    # 居中显示
                    progress_window.geometry("+%d+%d" % (
                        festival_window.winfo_rootx() + 50,
                        festival_window.winfo_rooty() + 50
                    ))
                    
                    # 进度标签
                    progress_label = tk.Label(progress_window, text="🌐 正在从网络加载节日数据...", 
                                            font=FONTS["content"], bg=COLORS["bg_main"])
                    progress_label.pack(pady=20)
                    
                    # 进度条
                    progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
                    progress_bar.pack(fill="x", padx=20, pady=10)
                    progress_bar.start()
                    
                    # 更新窗口
                    progress_window.update()
                    
                    # 获取节日数据
                    holidays = self.get_all_holidays_2025()
                    
                    # 停止进度条
                    progress_bar.stop()
                    progress_window.destroy()
                    
                    if holidays:
                        # 询问是否替换现有节日
                        result = messagebox.askyesnocancel(
                            "加载完成", 
                            f"成功加载了 {len(holidays)} 个节日！\n\n"
                            "选择操作：\n"
                            "是 - 替换现有节日\n"
                            "否 - 合并到现有节日\n"
                            "取消 - 不保存"
                        )
                        
                        if result is True:
                            # 替换现有节日
                            self.data["festival_reminders"] = holidays.copy()
                        elif result is False:
                            # 合并节日
                            self.data.setdefault("festival_reminders", {}).update(holidays)
                        else:
                            # 取消
                            return
                        
                        save_data(self.data)
                        load_festivals()
                        self.update_reminder_text()
                        
                        messagebox.showinfo("加载成功", f"已成功加载 {len(holidays)} 个节日！")
                    else:
                        messagebox.showerror("加载失败", "无法从网络获取节日数据，请检查网络连接。")
                        
                except Exception as e:
                    messagebox.showerror("错误", f"加载节日数据时发生错误：{e}")
            
            # 添加/更新按钮
            add_btn = create_modern_button(btn_frame, "➕ 添加/更新", add_festival,
                                         button_type="success")
            add_btn.pack(fill="x", pady=(0, 5))
            
            # 删除按钮
            delete_btn = create_modern_button(btn_frame, "🗑️ 删除", delete_festival,
                                            button_type="error")
            delete_btn.pack(fill="x", pady=(0, 5))
            
            # 网络加载按钮
            load_btn = create_modern_button(btn_frame, "🌐 加载全年节日", load_online_holidays,
                                          button_type="accent")
            load_btn.pack(fill="x", pady=(0, 5))
            
            # 测试按钮
            test_btn = create_modern_button(btn_frame, "🧪 测试提醒", 
                                          lambda: self.test_festival_reminder(),
                                          button_type="primary")
            test_btn.pack(fill="x", pady=(0, 5))
            
            # 添加测试节日按钮
            add_test_btn = create_modern_button(btn_frame, "➕ 添加测试节日", 
                                              lambda: self.add_test_holidays(),
                                              button_type="warning")
            add_test_btn.pack(fill="x", pady=(0, 5))
            
            # 清除测试节日按钮
            clear_test_btn = create_modern_button(btn_frame, "🧹 清除测试节日", 
                                                lambda: self.clear_test_holidays(),
                                                button_type="error")
            clear_test_btn.pack(fill="x", pady=(0, 5))
            
            # 绑定事件
            festival_tree.bind("<<TreeviewSelect>>", lambda e: self.on_festival_select(festival_tree, date_var, name_var))
            festival_tree.bind("<Double-1>", lambda e: self.on_festival_select(festival_tree, date_var, name_var))
            
            # 初始加载节日列表
            load_festivals()
            
        except Exception as e:
            logging.error(f"Failed to open festival manager: {e}")
            messagebox.showerror("错误", f"打开节日管理窗口失败：{e}")
    
    def on_festival_select(self, tree, date_var, name_var):
        """选择节日时的事件处理"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            values = item['values']
            if len(values) >= 2:
                date_var.set(values[0])
                name_var.set(values[1])
    
    def test_festival_reminder(self):
        """测试节日提醒"""
        today = datetime.date.today()
        festival_msgs = []
        
        # 添加测试节日（今天、明天、后天）
        test_holidays = {
            today.strftime("%m-%d"): "测试节日-今天",
            (today + datetime.timedelta(days=1)).strftime("%m-%d"): "测试节日-明天",
            (today + datetime.timedelta(days=2)).strftime("%m-%d"): "测试节日-后天"
        }
        
        # 临时添加测试节日到数据中
        original_holidays = self.data.get("festival_reminders", {}).copy()
        self.data.setdefault("festival_reminders", {}).update(test_holidays)
        save_data(self.data)
        
        # 更新主窗口显示
        self.update_reminder_text()
        
        # 显示测试结果
        for date_str, name in test_holidays.items():
            try:
                mm, dd = map(int, date_str.split('-'))
                festival_date = datetime.date(today.year, mm, dd)
                delta = (festival_date - today).days
                
                if 0 <= delta <= 3:
                    if delta == 0:
                        festival_msgs.append(f"🎊 今天是{name}！")
                    elif delta == 1:
                        festival_msgs.append(f"🎈 明天是{name}")
                    else:
                        festival_msgs.append(f"🎁 {name}还有{delta}天")
            except ValueError:
                continue
        
        if festival_msgs:
            message = "🎉 节日提醒测试结果：\n\n" + "\n".join(festival_msgs) + "\n\n✅ 测试节日已添加到主窗口，请查看主窗口显示效果！\n\n💡 提示：可以使用'🧹 清除测试节日'按钮清除测试显示"
        else:
            message = "📝 近期3天内没有节日"
        
        messagebox.showinfo("节日提醒测试", message)
        
        # 询问是否保留测试节日
        result = messagebox.askyesno("测试完成", "测试节日已添加到主窗口！\n\n是否保留这些测试节日？\n\n是 - 保留测试节日\n否 - 恢复原始节日设置")
        
        if not result:
            # 恢复原始节日设置
            self.data["festival_reminders"] = original_holidays
            save_data(self.data)
            # 强制更新主窗口显示
            self.update_reminder_text()
            # 刷新节日管理窗口的列表（如果存在）
            if hasattr(self, 'festival_manager_window') and self.festival_manager_window.winfo_exists():
                self.refresh_festival_list()
            messagebox.showinfo("已恢复", "已恢复原始节日设置，主窗口已更新！")
    
    def add_test_holidays(self):
        """添加测试节日到主窗口"""
        try:
            today = datetime.date.today()
            
            # 添加测试节日（今天、明天、后天）
            test_holidays = {
                today.strftime("%m-%d"): "测试节日-今天",
                (today + datetime.timedelta(days=1)).strftime("%m-%d"): "测试节日-明天",
                (today + datetime.timedelta(days=2)).strftime("%m-%d"): "测试节日-后天"
            }
            
            # 添加到数据中
            self.data.setdefault("festival_reminders", {}).update(test_holidays)
            save_data(self.data)
            
            # 更新主窗口显示
            self.update_reminder_text()
            
            messagebox.showinfo("测试节日已添加", 
                f"已添加测试节日：\n"
                f"🎊 今天是测试节日-今天！\n"
                f"🎈 明天是测试节日-明天\n"
                f"🎁 测试节日-后天还有2天\n\n"
                f"请查看主窗口的节日提醒显示效果！")
            
        except Exception as e:
            logging.error(f"Failed to add test holidays: {e}")
            messagebox.showerror("错误", f"添加测试节日失败：{e}")
    
    def clear_test_holidays(self):
        """清除测试节日"""
        try:
            today = datetime.date.today()
            
            # 识别测试节日（今天、明天、后天的测试节日）
            test_holidays_to_remove = []
            for date_str, name in self.data.get("festival_reminders", {}).items():
                if ("测试节日" in name and 
                    (date_str == today.strftime("%m-%d") or
                     date_str == (today + datetime.timedelta(days=1)).strftime("%m-%d") or
                     date_str == (today + datetime.timedelta(days=2)).strftime("%m-%d"))):
                    test_holidays_to_remove.append(date_str)
            
            if not test_holidays_to_remove:
                messagebox.showinfo("提示", "当前没有测试节日需要清除")
                return
            
            # 确认清除
            result = messagebox.askyesno("确认清除", 
                f"发现 {len(test_holidays_to_remove)} 个测试节日：\n\n" +
                "\n".join([f"  {date}: {self.data['festival_reminders'][date]}" 
                          for date in test_holidays_to_remove]) +
                "\n\n确定要清除这些测试节日吗？")
            
            if result:
                # 清除测试节日
                for date_str in test_holidays_to_remove:
                    if date_str in self.data.get("festival_reminders", {}):
                        del self.data["festival_reminders"][date_str]
                
                save_data(self.data)
                
                # 更新主窗口显示
                self.update_reminder_text()
                
                # 刷新节日管理窗口列表
                self.refresh_festival_list()
                
                messagebox.showinfo("清除完成", 
                    f"已成功清除 {len(test_holidays_to_remove)} 个测试节日！\n主窗口已更新。")
            
        except Exception as e:
            logging.error(f"Failed to clear test holidays: {e}")
            messagebox.showerror("错误", f"清除测试节日失败：{e}")
    
    def refresh_festival_list(self):
        """刷新节日管理窗口的列表"""
        try:
            if hasattr(self, 'festival_manager_window') and self.festival_manager_window.winfo_exists():
                # 查找节日列表控件
                for widget in self.festival_manager_window.winfo_children():
                    if isinstance(widget, tk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, tk.Frame):
                                for grandchild in child.winfo_children():
                                    if hasattr(grandchild, 'get_children'):
                                        # 找到Treeview控件，刷新数据
                                        self.refresh_festival_treeview(grandchild)
                                        break
        except Exception as e:
            logging.error(f"Failed to refresh festival list: {e}")
    
    def refresh_festival_treeview(self, tree_widget):
        """刷新节日列表控件"""
        try:
            if not tree_widget:
                return
                
            # 清空现有数据
            for item in tree_widget.get_children():
                tree_widget.delete(item)
            
            # 添加节日数据
            today = datetime.date.today()
            festival_reminders = self.data.get("festival_reminders", {})
            
            for date_str, name in sorted(festival_reminders.items()):
                try:
                    mm, dd = map(int, date_str.split('-'))
                    festival_date = datetime.date(today.year, mm, dd)
                    delta = (festival_date - today).days
                    
                    if delta == 0:
                        status = "🎊 今天"
                    elif delta == 1:
                        status = "🎈 明天"
                    elif 0 < delta <= 7:
                        status = f"📅 {delta}天后"
                    elif delta < 0:
                        status = f"⏰ 已过{abs(delta)}天"
                    else:
                        status = f"📅 {delta}天后"
                    
                    tree_widget.insert("", "end", values=(date_str, name, status))
                except ValueError:
                    # 无效日期格式
                    tree_widget.insert("", "end", values=(date_str, name, "❌ 无效日期"))
        except Exception as e:
            logging.error(f"Failed to refresh festival treeview: {e}")
    
    def get_all_holidays_2025(self):
        """获取2025年所有节日数据"""
        try:
            import requests
            
            # 创建会话
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # 本地节日数据
            holidays = {
                # 法定节假日
                "01-01": "元旦",
                "01-28": "春节", "01-29": "春节", "01-30": "春节", "01-31": "春节",
                "02-01": "春节", "02-02": "春节", "02-03": "春节",
                "04-05": "清明节", "04-06": "清明节", "04-07": "清明节",
                "05-01": "劳动节", "05-02": "劳动节", "05-03": "劳动节", "05-04": "劳动节", "05-05": "劳动节",
                "05-31": "端午节", "06-01": "端午节", "06-02": "端午节",
                "10-01": "国庆节", "10-02": "国庆节", "10-03": "国庆节", "10-04": "国庆节",
                "10-05": "国庆节", "10-06": "国庆节", "10-07": "国庆节",
                
                # 传统节日
                "02-09": "元宵节", "02-14": "情人节", "03-08": "妇女节", "03-12": "植树节",
                "04-01": "愚人节", "05-04": "青年节", "06-01": "儿童节", "06-14": "端午节",
                "07-01": "建党节", "08-01": "建军节", "08-15": "中秋节", "09-09": "重阳节",
                "09-10": "教师节", "12-25": "圣诞节",
                
                # 国际节日
                "03-15": "消费者权益日", "04-22": "世界地球日", "06-05": "世界环境日",
                "11-11": "光棍节"
            }
            
            # 尝试从网络获取额外数据
            try:
                api_urls = [
                    "https://api.apihubs.cn/holiday/get?field=workday,holiday&year=2025",
                    "https://timor.tech/api/holiday/year/2025",
                ]
                
                for url in api_urls:
                    try:
                        response = session.get(url, timeout=5)
                        response.raise_for_status()
                        data = response.json()
                        
                        if 'data' in data and isinstance(data['data'], dict):
                            for date_str, info in data['data'].items():
                                if isinstance(info, dict) and info.get('holiday'):
                                    if 'name' in info:
                                        holidays[date_str] = info['name']
                                    elif info.get('holiday'):
                                        holidays[date_str] = "节假日"
                            break
                    except:
                        continue
            except:
                pass
            
            return holidays
            
        except Exception as e:
            logging.error(f"Failed to get holidays: {e}")
            return {}

    def show_welcome_message(self):
        """显示欢迎消息"""
        try:
            missing_deps = []
            install_commands = []
            if not PIL_AVAILABLE:
                missing_deps.append("PIL/Pillow (托盘图标)")
                install_commands.append("pip install pillow")
            if not PYSTRAY_AVAILABLE:
                missing_deps.append("pystray (系统托盘)")
                install_commands.append("pip install pystray")
            if not EXCEL_AVAILABLE:
                missing_deps.append("openpyxl (Excel导入)")
                install_commands.append("pip install openpyxl")
            if not CALENDAR_AVAILABLE:
                missing_deps.append("tkcalendar (日期选择器)")
                install_commands.append("pip install tkcalendar")
            if not DATEUTIL_AVAILABLE:
                missing_deps.append("python-dateutil (增强日期解析)")
                install_commands.append("pip install python-dateutil")
            if not SCREENINFO_AVAILABLE:
                missing_deps.append("screeninfo (多显示器支持)")
                install_commands.append("pip install screeninfo")
            
            welcome_msg = "🎉 欢迎使用昱景每日工作提醒！\n程序已启动并在后台运行"
            if missing_deps:
                welcome_msg += f"\n\n💡 提示：以下功能需要安装对应库：\n• " + "\n• ".join(missing_deps)
                welcome_msg += f"\n\n可使用以下命令安装：\n" + "\n".join(install_commands)
            
            messagebox.showinfo("欢迎", welcome_msg)
        except Exception as e:
            logging.error(f"Failed to show welcome message: {e}")

# -------------------- 全局函数 --------------------
def update_reminder_text():
    """全局更新函数"""
    global app
    if app is None:
        logging.error("错误：应用程序实例未初始化")
        return
    app.update_reminder_text()

# -------------------- 主程序入口 --------------------
def main():
    """主程序入口"""
    global app
    try:
        logging.info("Starting 昱景每日工作提醒...")
        
        app = DailyReminderApp()
        
        app.run()
        
    except KeyboardInterrupt:
        logging.info("Program interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Program startup failed: {e}")
        error_root = tk.Tk()
        error_root.title("启动错误")
        error_root.configure(bg="#FAFAFA")
        center_window(error_root, 500, 300)
        
        title_frame = tk.Frame(error_root, bg="#F44336", height=60)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="⚠️ 程序启动失败", font=FONTS["title"],
                 bg="#F44336", fg="white").pack(pady=15)
        
        content_frame = tk.Frame(error_root, bg="#FAFAFA")
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        tk.Label(content_frame, text="错误详情：", font=FONTS["section"],
                 bg="#FAFAFA", fg="#212121").pack(anchor="w", pady=(0,10))
        
        error_text = tk.Text(content_frame, font=FONTS["default"], height=8, width=60,
                             bg="white", fg="#212121", relief="solid", bd=1)
        error_text.pack(fill="both", expand=True, pady=(0,20))
        error_text.insert("1.0", str(e))
        error_text.config(state=tk.DISABLED)
        
        tk.Label(content_frame, text="请检查Python环境和依赖库是否正确安装。",
                 font=FONTS["default"], bg="#FAFAFA", fg="#757575").pack(pady=(0,10))
        
        btn_frame = tk.Frame(content_frame, bg="#FAFAFA")
        btn_frame.pack(fill="x")
        
        def copy_error():
            try:
                error_root.clipboard_clear()
                error_root.clipboard_append(str(e))
                messagebox.showinfo("已复制", "错误信息已复制到剪贴板")
            except Exception:
                pass
        
        tk.Button(btn_frame, text="复制错误信息", command=copy_error,
                  bg="#2196F3", fg="white", font=FONTS["button"],
                  relief="flat", padx=15, pady=5).pack(side="left", padx=(0,10))
        
        tk.Button(btn_frame, text="关闭", command=error_root.destroy,
                  bg="#757575", fg="white", font=FONTS["button"],
                  relief="flat", padx=15, pady=5).pack(side="right")
        
        error_root.mainloop()

if __name__ == "__main__":
    main()