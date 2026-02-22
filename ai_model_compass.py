#!/usr/bin/env python3
"""
AI Model Compass v0.6.0
Discover, download, and run local AI — tailored to your hardware.
"""
import sys, os, subprocess, json, platform, shutil, time, traceback, math, re
from pathlib import Path

def _bootstrap():
    if sys.version_info < (3, 8): print("Python 3.8+ required"); sys.exit(1)
    for imp, pip in {"PyQt6":"PyQt6","psutil":"psutil","requests":"requests","huggingface_hub":"huggingface_hub"}.items():
        try: __import__(imp)
        except ImportError:
            print(f"Installing {pip}...")
            for f in [[], ["--user"], ["--break-system-packages"]]:
                try: subprocess.check_call([sys.executable,"-m","pip","install",pip,"-q"]+f,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); break
                except: continue
_bootstrap()

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import psutil, requests
from huggingface_hub import hf_hub_download
import html as html_mod
import time as _t

VERSION = "0.6.0"
APP = "AI Model Compass"
CFG_DIR = Path.home() / ".ai_compass"
CFG_DIR.mkdir(exist_ok=True)
CFG_FILE = CFG_DIR / "config.json"
HIST_FILE = CFG_DIR / "history.json"

def _load_cfg():
    try: return json.loads(CFG_FILE.read_text())
    except: return {}
def _save_cfg(c): CFG_FILE.write_text(json.dumps(c, indent=2))

def _crash(et, ev, tb):
    msg = "".join(traceback.format_exception(et, ev, tb))
    (CFG_DIR / "crash.log").write_text(msg)
    if sys.platform == "win32":
        import ctypes; ctypes.windll.user32.MessageBoxW(0, msg[:600], f"{APP} Error", 0x10)
    sys.exit(1)
sys.excepthook = _crash

# ═══════════════════════════════════════════════════════════════════════════════
# FAVORITES & NOTES
# ═══════════════════════════════════════════════════════════════════════════════
FAV_FILE = CFG_DIR / "favorites.json"

class FavoritesManager:
    _data = None
    @classmethod
    def _load(cls):
        if cls._data is None:
            try: cls._data = json.loads(FAV_FILE.read_text())
            except: cls._data = {}
        return cls._data
    @classmethod
    def _save(cls): FAV_FILE.write_text(json.dumps(cls._data or {}, indent=2))
    @classmethod
    def is_fav(cls, name): return cls._load().get(name, {}).get("fav", False)
    @classmethod
    def toggle_fav(cls, name):
        d = cls._load()
        if name not in d: d[name] = {}
        d[name]["fav"] = not d[name].get("fav", False)
        cls._save(); return d[name]["fav"]
    @classmethod
    def get_note(cls, name): return cls._load().get(name, {}).get("note", "")
    @classmethod
    def set_note(cls, name, note):
        d = cls._load()
        if name not in d: d[name] = {}
        d[name]["note"] = note; cls._save()
    @classmethod
    def all_favs(cls): return {k: v for k, v in cls._load().items() if v.get("fav")}
    @classmethod
    def all_notes(cls): return {k: v.get("note","") for k, v in cls._load().items() if v.get("note")}

# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE DETECTION + SPEED ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════════
class HardwareInfo:
    GPU_BW = {
        "4090":1008,"4080 super":736,"4080":717,"4070 ti super":672,"4070 ti":504,
        "4070 super":504,"4070":504,"4060 ti":288,"4060":272,
        "3090 ti":1008,"3090":936,"3080 ti":912,"3080":760,"3070 ti":608,
        "3070":448,"3060 ti":448,"3060":360,"3050":224,
        "2080 ti":616,"2080 super":496,"2080":448,"2070 super":448,"2070":448,
        "2060 super":448,"2060":336,"1660 ti":288,"1660 super":336,"1660":192,
        "1650 super":192,"1650":128,"1080 ti":484,"1080":320,"1070 ti":256,
        "1070":256,"1060":192,
        "7900 xtx":960,"7900 xt":800,"7800 xt":624,"7700 xt":432,"7600":288,
        "6950 xt":576,"6900 xt":512,"6800 xt":512,"6700 xt":384,"6600 xt":256,
    }

    def __init__(self):
        self.cpu_name = "Unknown CPU"; self.cpu_cores = psutil.cpu_count(logical=False) or 1
        self.cpu_threads = psutil.cpu_count(logical=True) or 1
        self.ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        self.gpu_name = "No dedicated GPU"; self.vram_gb = 0.0
        self.gpu_vendor = "none"; self.mem_bw = 0
        self.os_name = f"{platform.system()} {platform.release()}"
        self._detect_cpu(); self._detect_gpu(); self._estimate_bw()

    def refresh(self):
        """Re-detect all hardware (e.g., after eGPU connect, driver update)."""
        self.gpu_name = "No dedicated GPU"; self.vram_gb = 0.0
        self.gpu_vendor = "none"; self.mem_bw = 0
        self.ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        self._detect_gpu(); self._estimate_bw()

    def _detect_cpu(self):
        if sys.platform == "win32":
            try:
                out = subprocess.check_output("wmic cpu get name", shell=True, text=True, stderr=subprocess.DEVNULL)
                for ln in out.strip().splitlines():
                    ln = ln.strip()
                    if ln and ln.lower() != "name": self.cpu_name = ln; return
            except: pass
        else:
            try:
                with open("/proc/cpuinfo") as f:
                    for ln in f:
                        if "model name" in ln: self.cpu_name = ln.split(":")[1].strip(); return
            except: self.cpu_name = platform.processor() or "Unknown"

    def _detect_gpu(self):
        for p in ["nvidia-smi", r"C:\Windows\System32\nvidia-smi.exe",
                   r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]:
            try:
                out = subprocess.check_output([p,"--query-gpu=name,memory.total","--format=csv,noheader,nounits"],
                    text=True, stderr=subprocess.DEVNULL, timeout=5)
                parts = out.strip().split(",")
                if len(parts) >= 2:
                    self.gpu_name = parts[0].strip(); self.vram_gb = round(int(parts[1].strip())/1024, 1)
                    self.gpu_vendor = "nvidia"; return
            except: continue
        if sys.platform == "win32":
            try:
                out = subprocess.check_output("wmic path win32_VideoController get name,adapterram /format:csv",
                    shell=True, text=True, stderr=subprocess.DEVNULL, timeout=5)
                bn, bv, bven = "", 0, "none"
                for line in out.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts)<3 or parts[1]=="AdapterRAM": continue
                    try: vr = round(int(parts[1])/(1024**3),1)
                    except: vr = 0
                    nm = parts[2]; nl = nm.lower(); ven = "none"
                    if any(k in nl for k in ["nvidia","geforce","rtx","gtx","quadro"]): ven = "nvidia"
                    elif any(k in nl for k in ["amd","radeon","rx "]): ven = "amd"
                    elif "arc" in nl: ven = "intel"
                    if ven != "none" and vr >= bv: bn, bv, bven = nm, vr, ven
                if bn: self.gpu_name = bn; self.vram_gb = bv; self.gpu_vendor = bven
            except: pass

    def _estimate_bw(self):
        gl = self.gpu_name.lower()
        for key, bw in self.GPU_BW.items():
            if key in gl: self.mem_bw = bw; return
        if self.gpu_vendor == "nvidia": self.mem_bw = 300
        elif self.gpu_vendor == "amd": self.mem_bw = 400
        else: self.mem_bw = 50

    @property
    def tier(self):
        v = self.vram_gb
        if v >= 24: return "ultra"
        if v >= 16: return "high"
        if v >= 12: return "mid_high"
        if v >= 8: return "mid"
        if v >= 6: return "low_mid"
        if v >= 4: return "low"
        return "cpu_only"

    TIER_LABELS = {"ultra":"Ultra (24 GB+)","high":"High (16 GB)","mid_high":"Mid-High (12 GB)",
                   "mid":"Mid (8 GB)","low_mid":"Low-Mid (6 GB)","low":"Low (4 GB)","cpu_only":"CPU Only"}
    @property
    def tier_label(self): return self.TIER_LABELS.get(self.tier, "Unknown")

    def max_model_gb(self):
        if self.vram_gb > 0: return round(self.vram_gb * 0.82, 1)
        return round(self.ram_gb * 0.55, 1)

    def estimate_toks(self, model_gb):
        if model_gb <= 0: return 0
        raw = self.mem_bw / (model_gb * 1.15)
        if self.vram_gb == 0 or model_gb > self.vram_gb * 0.95:
            raw = min(raw, self.ram_gb * 0.8)
        return max(1, round(raw))

    def speed_label(self, toks):
        if toks >= 40: return "Blazing fast", "gn"
        if toks >= 20: return "Conversational", "gn"
        if toks >= 10: return "Comfortable", "ac"
        if toks >= 5: return "Usable", "og"
        return "Slow", "rd"

    def vram_usage(self, model_gb, ctx_k=8):
        kv = ctx_k * 0.5 / 1024 * 8; return model_gb + max(0.5, kv)

    def export_profile(self):
        """One-click system profile for forums/support."""
        return (f"=== {APP} v{VERSION} System Profile ===\n"
                f"CPU: {self.cpu_name} ({self.cpu_cores}C/{self.cpu_threads}T)\n"
                f"RAM: {self.ram_gb} GB\nGPU: {self.gpu_name}\nVRAM: {self.vram_gb} GB\n"
                f"Vendor: {self.gpu_vendor}\nTier: {self.tier_label}\n"
                f"Bandwidth: ~{self.mem_bw} GB/s\nMax GGUF: ~{self.max_model_gb()} GB\n"
                f"OS: {self.os_name}\nPython: {platform.python_version()}")

# ═══════════════════════════════════════════════════════════════════════════════
# SOFTWARE DETECTION + VERSIONS
# ═══════════════════════════════════════════════════════════════════════════════
class SoftwareDetector:
    TOOLS = {
        "ollama": {"name":"Ollama","cmd":"ollama --version",
            "win":[r"C:\Users\{u}\AppData\Local\Programs\Ollama\ollama.exe",r"C:\Program Files\Ollama\ollama.exe"],
            "url":"https://ollama.com/download/OllamaSetup.exe","home":"https://ollama.com",
            "desc":"CLI + API. 'ollama run model' and done.","icon":"🟢","winget":"Ollama.Ollama"},
        "lmstudio": {"name":"LM Studio","cmd":None,
            "win":[r"C:\Users\{u}\AppData\Local\LM-Studio\LM Studio.exe",
                   r"C:\Users\{u}\AppData\Local\Programs\LM Studio\LM Studio.exe",
                   r"C:\Program Files\LM Studio\LM Studio.exe",r"C:\Users\{u}\.cache\lm-studio\bin\lms.exe"],
            "url":"https://lmstudio.ai/download","home":"https://lmstudio.ai",
            "desc":"GUI with model browser. Best for beginners.","icon":"🔵",
            "model_dir_win": r"C:\Users\{u}\.cache\lm-studio\models","winget":"ElementLabs.LMStudio"},
        "koboldcpp": {"name":"KoboldCpp","cmd":None,
            "win":[r"C:\KoboldCpp\koboldcpp.exe"],
            "url":"https://github.com/LostRuins/koboldcpp/releases","home":"https://github.com/LostRuins/koboldcpp",
            "desc":"Single .exe: LLM+SD+Whisper+TTS.","icon":"🟣","winget":None},
        "gpt4all": {"name":"GPT4All","cmd":None,
            "win":[r"C:\Program Files\nomic.ai\GPT4All\bin\chat.exe"],
            "url":"https://gpt4all.io/installers/gpt4all-installer-win64.exe","home":"https://gpt4all.io",
            "desc":"Desktop GUI with local RAG.","icon":"🟠","winget":"Nomic.GPT4All"},
        "jan": {"name":"Jan","cmd":None,
            "win":[r"C:\Users\{u}\AppData\Local\Jan\Jan.exe"],
            "url":"https://jan.ai/download","home":"https://jan.ai",
            "desc":"ChatGPT-style local+cloud.","icon":"⚪","winget":"Jan.Jan"},
    }

    def __init__(self):
        self.found = {}; self.versions = {}
        u = os.environ.get("USERNAME", os.environ.get("USER", "user"))
        for key, info in self.TOOLS.items():
            path = None
            if info.get("cmd"):
                try:
                    out = subprocess.check_output(info["cmd"], shell=True, text=True, stderr=subprocess.DEVNULL, timeout=5)
                    path = shutil.which(info["cmd"].split()[0]) or "PATH"
                    vm = re.search(r'(\d+\.\d+[\.\d]*)', out)
                    if vm: self.versions[key] = vm.group(1)
                except: pass
            if not path and sys.platform == "win32":
                for p in info.get("win", []):
                    exp = p.replace("{u}", u)
                    if Path(exp).exists(): path = exp; break
            self.found[key] = path

    def is_installed(self, k): return self.found.get(k) is not None
    def get_path(self, k): return self.found.get(k)
    def get_version(self, k): return self.versions.get(k, "")

    def integrate_ollama(self, gguf_path, model_name):
        mf = Path(gguf_path).parent / f"{model_name}.Modelfile"
        mf.write_text(f'FROM "{gguf_path}"\n')
        try:
            subprocess.Popen(["ollama", "create", model_name, "-f", str(mf)],
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
            return True, f"Registered as 'ollama run {model_name}'"
        except Exception as e: return False, str(e)

    def integrate_lmstudio(self, gguf_path):
        u = os.environ.get("USERNAME", os.environ.get("USER", "user"))
        lm_dir = Path(self.TOOLS["lmstudio"].get("model_dir_win","").replace("{u}",u))
        if not lm_dir.exists(): lm_dir.mkdir(parents=True, exist_ok=True)
        dest = lm_dir / Path(gguf_path).name
        if not dest.exists():
            try: shutil.copy2(gguf_path, dest); return True, f"Copied to {dest}"
            except Exception as e: return False, str(e)
        return True, f"Already in LM Studio: {dest}"

# ═══════════════════════════════════════════════════════════════════════════════
# THEMES
# ═══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "Obsidian": {
        "bg0":"#0b0e14","bg1":"#111621","bg2":"#161d2b","bg3":"#1c2536","bg4":"#232e42",
        "bd":"#1e293b","bd2":"#2d3f5a","tx":"#e2e8f0","tx2":"#8892a8","tx3":"#5a6478",
        "ac":"#60a5fa","ac2":"#93c5fd","ac3":"#3b82f6","acs":"#1e3a5f",
        "gn":"#34d399","og":"#fbbf24","rd":"#f87171","pu":"#c084fc","pk":"#f472b6","tl":"#2dd4bf"},
    "Catppuccin Mocha": {
        "bg0":"#1e1e2e","bg1":"#181825","bg2":"#27273a","bg3":"#313244","bg4":"#3b3b52",
        "bd":"#45475a","bd2":"#585b70","tx":"#cdd6f4","tx2":"#a6adc8","tx3":"#6c7086",
        "ac":"#89b4fa","ac2":"#b4d0fb","ac3":"#74c7ec","acs":"#2a3e5e",
        "gn":"#a6e3a1","og":"#f9e2af","rd":"#f38ba8","pu":"#cba6f7","pk":"#f5c2e7","tl":"#94e2d5"},
    "OLED Black": {
        "bg0":"#000000","bg1":"#0a0a0a","bg2":"#111111","bg3":"#1a1a1a","bg4":"#222222",
        "bd":"#2a2a2a","bd2":"#3a3a3a","tx":"#e0e0e0","tx2":"#888888","tx3":"#555555",
        "ac":"#6cb4ee","ac2":"#a0d0ff","ac3":"#4a9ae0","acs":"#162840",
        "gn":"#4ade80","og":"#facc15","rd":"#ef4444","pu":"#a78bfa","pk":"#f472b6","tl":"#2dd4bf"},
}
current_theme = "Obsidian"
def T(): return THEMES[current_theme]

def _qss(t):
    return f"""
* {{ font-family:'Segoe UI Variable','Segoe UI','SF Pro Display',system-ui,sans-serif; }}
QMainWindow,QDialog,QWidget {{ background:{t['bg0']}; color:{t['tx']}; font-size:13px; }}
QFrame {{ color:{t['tx']}; }} QLabel {{ color:{t['tx']}; }}
QTabWidget::pane {{ border:1px solid {t['bd']}; background:{t['bg0']}; border-radius:6px; }}
QTabBar {{ background:{t['bg1']}; }}
QTabBar::tab {{ background:{t['bg1']}; color:{t['tx2']}; padding:10px 18px; border:none; border-bottom:2px solid transparent; font-weight:600; min-width:60px; }}
QTabBar::tab:selected {{ color:{t['tx']}; border-bottom-color:{t['ac']}; background:{t['bg2']}; }}
QTabBar::tab:hover:!selected {{ color:{t['tx']}; background:{t['bg2']}; }}
QPushButton {{ background:{t['ac']}; color:{t['bg0']}; border:none; padding:9px 20px; border-radius:8px; font-weight:bold; }}
QPushButton:hover {{ background:{t['ac2']}; }} QPushButton:pressed {{ background:{t['ac3']}; }}
QPushButton:disabled {{ background:{t['bg3']}; color:{t['tx3']}; }}
QPushButton[class="ghost"] {{ background:transparent; color:{t['ac']}; border:1px solid {t['bd']}; }}
QPushButton[class="ghost"]:hover {{ background:{t['acs']}; border-color:{t['ac']}; }}
QPushButton[class="sec"] {{ background:{t['bg3']}; color:{t['tx']}; border:1px solid {t['bd']}; }}
QPushButton[class="sec"]:hover {{ background:{t['bg4']}; }}
QPushButton[class="danger"] {{ background:{t['rd']}; color:#fff; }}
QPushButton[class="danger"]:hover {{ background:#dc2626; }}
QLineEdit {{ background:{t['bg1']}; color:{t['tx']}; border:1px solid {t['bd']}; border-radius:8px; padding:9px 12px; selection-background-color:{t['ac']}; }}
QLineEdit:focus {{ border-color:{t['ac']}; }}
QComboBox {{ background:{t['bg1']}; color:{t['tx']}; border:1px solid {t['bd']}; border-radius:8px; padding:8px 12px; min-width:120px; }}
QComboBox::drop-down {{ border:none; width:26px; }}
QComboBox::down-arrow {{ image:none; border-left:5px solid transparent; border-right:5px solid transparent; border-top:6px solid {t['tx2']}; }}
QComboBox QAbstractItemView {{ background:{t['bg2']}; color:{t['tx']}; border:1px solid {t['bd']}; selection-background-color:{t['ac']}; selection-color:{t['bg0']}; outline:none; }}
QScrollBar:vertical {{ background:{t['bg0']}; width:8px; border:none; }} QScrollBar::handle:vertical {{ background:{t['bd']}; border-radius:4px; min-height:40px; }}
QScrollBar::handle:vertical:hover {{ background:{t['bd2']}; }} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{t['bg0']}; height:8px; }} QScrollBar::handle:horizontal {{ background:{t['bd']}; border-radius:4px; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0; }}
QGroupBox {{ border:1px solid {t['bd']}; border-radius:10px; margin-top:14px; padding:18px 14px 14px; font-weight:bold; }}
QGroupBox::title {{ subcontrol-origin:margin; left:16px; padding:0 8px; color:{t['ac']}; }}
QToolTip {{ background:{t['bg2']}; color:{t['tx']}; border:1px solid {t['bd']}; padding:8px; border-radius:6px; }}
QSlider::groove:horizontal {{ background:{t['bg3']}; height:6px; border-radius:3px; }}
QSlider::handle:horizontal {{ background:{t['ac']}; width:20px; height:20px; margin:-7px 0; border-radius:10px; border:2px solid {t['bg0']}; }}
QSlider::sub-page:horizontal {{ background:{t['ac']}; border-radius:3px; }}
QCheckBox {{ spacing:8px; }} QCheckBox::indicator {{ width:20px; height:20px; border-radius:5px; border:2px solid {t['bd']}; background:{t['bg1']}; }}
QCheckBox::indicator:checked {{ background:{t['ac']}; border-color:{t['ac']}; }}
QHeaderView::section {{ background:{t['bg1']}; color:{t['tx']}; border:none; border-bottom:1px solid {t['bd']}; padding:10px; font-weight:600; }}
QTableWidget {{ background:{t['bg0']}; alternate-background-color:{t['bg1']}; color:{t['tx']}; border:1px solid {t['bd']}; gridline-color:{t['bd']}; border-radius:8px; }}
QTableWidget::item:selected {{ background:{t['acs']}; }}
QTextBrowser {{ background:{t['bg1']}; color:{t['tx']}; border:1px solid {t['bd']}; border-radius:10px; padding:14px; }}
QProgressBar {{ background:{t['bg3']}; border:none; border-radius:6px; text-align:center; color:{t['tx']}; font-weight:bold; font-size:11px; min-height:22px; }}
QProgressBar::chunk {{ background:{t['ac']}; border-radius:6px; }}
QListWidget {{ background:transparent; border:none; outline:none; }}
QListWidget::item {{ padding:11px 14px; border-radius:8px; }}
QListWidget::item:selected {{ background:{t['bg2']}; color:{t['ac']}; font-weight:bold; }}
QListWidget::item:hover:!selected {{ background:{t['bg4']}; }}
"""

def _html(body, t):
    return f"""<html><head><style>
body {{ font-family:'Segoe UI Variable','Segoe UI',sans-serif; color:{t['tx']}; background:{t['bg1']}; line-height:1.75; padding:10px; }}
h1 {{ color:{t['ac']}; font-size:22px; border-bottom:2px solid {t['bd']}; padding-bottom:8px; }}
h2 {{ color:{t['pu']}; font-size:17px; margin-top:20px; }} h3 {{ color:{t['tl']}; font-size:15px; }}
code {{ background:{t['bg2']}; color:{t['og']}; padding:2px 7px; border-radius:5px; font-family:'Cascadia Code','Consolas',monospace; font-size:12px; }}
.c {{ background:{t['bg2']}; border:1px solid {t['bd']}; border-radius:10px; padding:14px; margin:10px 0; }}
.hl {{ background:{t['bg2']}; border-left:3px solid {t['ac']}; padding:10px 14px; margin:10px 0; border-radius:0 8px 8px 0; }}
.g {{ color:{t['gn']}; }} .o {{ color:{t['og']}; }} .r {{ color:{t['rd']}; }} .d {{ color:{t['tx2']}; }}
table {{ border-collapse:collapse; width:100%; margin:10px 0; }}
th {{ background:{t['bg2']}; color:{t['ac']}; text-align:left; padding:9px 10px; border-bottom:2px solid {t['bd']}; font-size:12px; }}
td {{ padding:8px 10px; border-bottom:1px solid {t['bd']}; font-size:12px; }}
tr:hover td {{ background:{t['bg2']}; }}
</style></head><body>{body}</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# TOAST NOTIFICATION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class ToastWidget(QFrame):
    def __init__(self, msg, color, parent):
        super().__init__(parent)
        t = T()
        self.setStyleSheet(f"QFrame{{background:{t['bg2']};border:1px solid {color};border-radius:10px;}}")
        lo = QHBoxLayout(self); lo.setContentsMargins(14,10,14,10)
        lbl = QLabel(msg); lbl.setStyleSheet(f"color:{t['tx']};font-size:13px;"); lbl.setTextFormat(Qt.TextFormat.RichText)
        lo.addWidget(lbl)
        self.adjustSize()

class ToastManager:
    _instance = None
    @classmethod
    def inst(cls):
        if not cls._instance: cls._instance = cls()
        return cls._instance
    def __init__(self): self._toasts = []; self._parent = None
    def set_parent(self, p): self._parent = p
    def show(self, msg, color=None, duration=3500):
        if not self._parent: return
        t = T(); color = color or t['gn']
        tw = ToastWidget(msg, color, self._parent)
        pw = self._parent.width(); tw.move(pw - tw.width() - 20, 60 + len(self._toasts) * 56)
        tw.show(); tw.raise_(); self._toasts.append(tw)
        QTimer.singleShot(duration, lambda: self._dismiss(tw))
    def _dismiss(self, tw):
        if tw in self._toasts: self._toasts.remove(tw)
        try: tw.deleteLater()
        except: pass

def toast(msg, color=None, dur=3500): ToastManager.inst().show(msg, color, dur)

# ═══════════════════════════════════════════════════════════════════════════════
# EDUCATIONAL CONTENT
# ═══════════════════════════════════════════════════════════════════════════════
def _topics(t):
    return {
    "🧠 What is AI?": _html("<h1>🧠 What is Artificial Intelligence?</h1><p>AI refers to systems that perform tasks requiring human intelligence — language, images, decisions, creativity.</p><h2>Types</h2><div class='c'><h3>🗣️ LLMs</h3><p>Text AI for chat, writing, coding, reasoning. <span class='d'>Qwen3, DeepSeek, Llama 4, Mistral</span></p></div><div class='c'><h3>🎨 Image Gen</h3><p>Create images from text. <span class='d'>Stable Diffusion, Flux, SD3.5</span></p></div><div class='c'><h3>🔊 Voice</h3><p>TTS, STT, voice conversion. <span class='d'>Kokoro, Whisper, RVC</span></p></div><div class='c'><h3>👁️ Vision-Language</h3><p>Understand text+images. <span class='d'>Qwen3-VL, InternVL3</span></p></div><h2>Why Local?</h2><div class='hl'><p><span class='g'>✓ Privacy</span> — data stays on your PC<br><span class='g'>✓ Free</span> — no subscriptions<br><span class='g'>✓ Uncensored</span> — no filters<br><span class='g'>✓ Offline</span> — works without internet<br><span class='g'>✓ Customizable</span> — fine-tune for you</p></div><h2>Key Concepts</h2><p><b>Parameters</b> — model neurons. 7B = smaller/faster; 70B = smarter/heavier.</p><p><b>Context</b> — text the model sees at once. 128K tokens ≈ 96K words.</p><p><b>Inference</b> — generating output. 20+ tok/s = conversational speed.</p>", t),
    "📦 What is GGUF?": _html("<h1>📦 What is GGUF?</h1><p><b>GPT-Generated Unified Format</b> — the standard for running AI locally. One file, all hardware.</p><div class='hl'>A 70B model at FP16 = ~140 GB. GGUF compresses it to ~40 GB in a single file.</div><h2>What's Inside</h2><div class='c'><p>📄 Metadata — architecture, context, quant type<br>🧮 Quantized weights — compressed parameters<br>📚 Tokenizer — vocabulary<br>All in <b>one file</b>.</p></div><h2>GGUF vs Others</h2><table><tr><th>Feature</th><th>GGUF</th><th>GPTQ/AWQ/EXL2</th></tr><tr><td>CPU</td><td><span class='g'>✓ Full</span></td><td><span class='r'>✗ GPU only</span></td></tr><tr><td>Mixed CPU+GPU</td><td><span class='g'>✓ Any split</span></td><td><span class='r'>✗</span></td></tr><tr><td>Hardware</td><td><span class='g'>Everything</span></td><td><span class='o'>NVIDIA mostly</span></td></tr><tr><td>Software</td><td><span class='g'>20+ tools</span></td><td><span class='o'>3-4 tools</span></td></tr></table><div class='hl'>💡 For local AI: <b>GGUF is the format you want.</b></div>", t),
    "🔢 Quantization": _html("<h1>🔢 Quantization</h1><p>Reducing weight precision to shrink models. 16-bit → 4-bit = ~3.3x smaller, ~99% quality.</p><h2>⭐ Q4_K_M — The Default</h2><div class='hl'><p><span class='g'>~99% quality</span> · <span class='g'>3.3x smaller</span> · <span class='g'>Runs on 8GB VRAM</span> · <span class='g'>Best balance of everything</span></p></div><h2>Reference Table</h2><table><tr><th>Type</th><th>Bits</th><th>~7B Size</th><th>Quality</th></tr><tr><td>Q8_0</td><td>8.50</td><td>6.7 GB</td><td><span class='g'>99.96%</span></td></tr><tr><td>Q6_K</td><td>6.57</td><td>5.15 GB</td><td><span class='g'>99.9%</span></td></tr><tr><td>Q5_K_M</td><td>5.67</td><td>4.45 GB</td><td><span class='g'>99.5%</span></td></tr><tr style='background:#1e3a5f33'><td><b>Q4_K_M</b></td><td><b>4.83</b></td><td><b>3.80 GB</b></td><td><span class='g'><b>⭐ 99%</b></span></td></tr><tr><td>Q3_K_M</td><td>3.89</td><td>3.07 GB</td><td><span class='o'>95.5%</span></td></tr><tr><td>Q2_K</td><td>3.00</td><td>2.63 GB</td><td><span class='r'>85%</span></td></tr></table><div class='hl'>🔑 <b>Bigger model at lower quant beats smaller model at higher quant.</b> 70B@Q4 > 13B@FP16.</div>", t),
    "💻 Hardware Guide": _html("<h1>💻 What Can You Run?</h1><p>VRAM is the bottleneck. Check 🎯 Recommend for personalized picks.</p><table><tr><th>VRAM</th><th>GPUs</th><th>Models</th></tr><tr><td>4 GB</td><td>GTX 1650</td><td>3B, SD 1.5</td></tr><tr><td>6 GB</td><td>RTX 2060</td><td>7B, SDXL tight</td></tr><tr><td>8 GB</td><td>RTX 4060</td><td>8B (Q5), 13B (Q3), Flux quant</td></tr><tr><td>12 GB</td><td>RTX 4070</td><td>13B (Q4), Flux fp8</td></tr><tr><td>16 GB</td><td>RTX 4070 Ti</td><td>30B (Q4), Flux fp16</td></tr><tr><td>24 GB</td><td>RTX 4090</td><td>70B (Q4+offload), everything</td></tr></table><h2>CPU Only</h2><div class='c'>16GB RAM → 7B (~5-8 tok/s) | 32GB → 13B | 64GB → 34B</div><h2>Formula</h2><div class='hl'><code>VRAM ≈ (Params × Bits / 8) + ~1.5 GB</code></div>", t),
    "⚡ Speed Deep Dive": _html("<h1>⚡ Speed Deep Dive</h1><h2>Memory Bandwidth = Speed</h2><div class='hl'>Inference speed = <code>Bandwidth / Model Size</code>.<br>RTX 4090 (1 TB/s) with 8GB model = ~125 tok/s theoretical.</div><h2>GPU Bandwidth</h2><table><tr><th>GPU</th><th>BW (GB/s)</th><th>~8B Model</th></tr><tr><td>RTX 4090</td><td>1008</td><td><span class='g'>~100+ tok/s</span></td></tr><tr><td>RTX 4070</td><td>504</td><td><span class='g'>~55 tok/s</span></td></tr><tr><td>RTX 3060</td><td>360</td><td><span class='g'>~35 tok/s</span></td></tr><tr><td>RX 7800 XT</td><td>624</td><td><span class='g'>~60 tok/s</span></td></tr></table><h2>Offloading</h2><div class='c'>When VRAM is insufficient, layers offload to RAM. Speed drops to DDR bandwidth (~50 GB/s). Mix: best of both.</div>", t),
    "🔧 Advanced Config": _html("<h1>🔧 Advanced Settings</h1><h2>GPU Layer Offloading</h2><div class='c'><code>--n-gpu-layers 35</code> — controls how many layers go to GPU vs CPU.<br>Higher = more VRAM used but faster. Start max, reduce if OOM.</div><h2>Context Size</h2><div class='c'><code>--ctx-size 8192</code> — how much text the model sees.<br>Higher = more VRAM for KV cache. 8K is usually fine.</div><h2>Threads</h2><div class='c'><code>--threads 8</code> — CPU threads for CPU layers.<br>Set to physical cores (not hyperthreads).</div><h2>Flash Attention</h2><div class='hl'>Enable with <code>--flash-attn</code>. Reduces VRAM usage for KV cache by ~50%.</div>", t),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
USE_CASES = {
    "💬 Chat & Writing": {"cats":["General Purpose","Small / Efficient"],"desc":"Conversation, Q&A, brainstorming"},
    "💻 Coding": {"cats":["Coding"],"desc":"Code generation, debugging, review"},
    "🎭 Roleplay": {"cats":["Roleplay","Uncensored"],"desc":"Character fiction, interactive stories"},
    "🔓 Uncensored": {"cats":["Uncensored"],"desc":"No safety filters, direct answers"},
    "🔬 Research": {"cats":["General Purpose","Long Context"],"desc":"Analysis, math, reasoning"},
    "🤖 Agents": {"cats":["Agents","Coding"],"desc":"Autonomous tools, automation"},
    "👁️ Vision": {"cats":["Vision"],"desc":"Image understanding + text"},
}
CATEGORIES = sorted(set(c for uc in USE_CASES.values() for c in uc["cats"]))

MODEL_DB = [
    {"n":"Qwen3-32B","p":"32B","q":"Q4_K_M","gb":20.5,"ctx":"128K","sc":95,"cat":"General Purpose","lic":"Apache 2.0",
     "d":"Top-tier open model. Thinking + non-thinking modes, tool use, multilingual. Arena-tested.","tags":["Thinking","MoE-dense","Multilingual","Tool Use"],
     "bf":"Best overall open model","repo":"unsloth/Qwen3-32B-GGUF","file":"Qwen3-32B-Q4_K_M.gguf"},
    {"n":"Qwen3-8B","p":"8B","q":"Q4_K_M","gb":5.2,"ctx":"128K","sc":89,"cat":"General Purpose","lic":"Apache 2.0",
     "d":"Best 8B model. Thinking mode, 128K context, multilingual. Punches way above weight.","tags":["Thinking","Multilingual","Efficient"],
     "bf":"Best 8B all-rounder","repo":"Qwen/Qwen3-8B-GGUF","file":"Qwen3-8B-Q4_K_M.gguf"},
    {"n":"Qwen3-4B","p":"4B","q":"Q4_K_M","gb":2.9,"ctx":"128K","sc":82,"cat":"Small / Efficient","lic":"Apache 2.0",
     "d":"Tiny but capable. Thinking mode in 3GB. Perfect for low VRAM or fast responses.","tags":["Thinking","Tiny","Fast"],
     "bf":"Best ultra-small model","repo":"Qwen/Qwen3-4B-GGUF","file":"Qwen3-4B-Q4_K_M.gguf"},
    {"n":"Qwen3-30B-A3B","p":"30B (3B active)","q":"Q4_K_M","gb":18.4,"ctx":"128K","sc":91,"cat":"General Purpose","lic":"Apache 2.0",
     "d":"MoE: 30B total, only 3B active per token. Near-32B quality at fraction of compute.","tags":["MoE","Thinking","Efficient"],
     "bf":"Best MoE efficiency","repo":"unsloth/Qwen3-30B-A3B-GGUF","file":"Qwen3-30B-A3B-Q4_K_M.gguf"},
    {"n":"Qwen3-235B-A22B","p":"235B (22B active)","q":"Q4_K_M","gb":130,"ctx":"128K","sc":97,"cat":"General Purpose","lic":"Apache 2.0",
     "d":"Largest open model. GPT-4 class. Use 'ollama pull qwen3:235b' (sharded GGUF, multi-file).","tags":["MoE","Frontier","Thinking"],
     "bf":"Most intelligent open model"},
    {"n":"DeepSeek-R1-14B","p":"14B","q":"Q4_K_M","gb":8.9,"ctx":"64K","sc":88,"cat":"General Purpose","lic":"MIT",
     "d":"Distilled reasoning from DeepSeek-R1. Great chain-of-thought, math, logic.","tags":["Reasoning","CoT","Math"],
     "bf":"Best reasoning at size","repo":"bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF","file":"DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf"},
    {"n":"Gemma-3-27B","p":"27B","q":"Q4_K_M","gb":17.3,"ctx":"128K","sc":90,"cat":"General Purpose","lic":"Gemma",
     "d":"Google's best open model. Excellent instruction following and multilingual.","tags":["Google","Multilingual","Instruct"],
     "bf":"Google's strongest open model","repo":"unsloth/gemma-3-27b-it-GGUF","file":"gemma-3-27b-it-Q4_K_M.gguf"},
    {"n":"Mistral-Small-24B","p":"24B","q":"Q4_K_M","gb":14.5,"ctx":"32K","sc":87,"cat":"General Purpose","lic":"Apache 2.0",
     "d":"Mistral's compact powerhouse. Function calling, structured output.","tags":["Function Calling","JSON","Instruct"],
     "bf":"Best structured output","repo":"bartowski/Mistral-Small-24B-Instruct-2501-GGUF","file":"Mistral-Small-24B-Instruct-2501-Q4_K_M.gguf"},
    {"n":"Llama-4-Scout","p":"109B (17B active)","q":"Q4_K_M","gb":63.8,"ctx":"512K","sc":89,"cat":"Long Context","lic":"Llama 4",
     "d":"Meta's MoE with 10M token context. Use 'ollama pull llama4-scout' (sharded GGUF).","tags":["MoE","Long Context","Meta"],
     "bf":"Longest context window"},
    {"n":"Qwen2.5-Coder-32B","p":"32B","q":"Q4_K_M","gb":20.3,"ctx":"128K","sc":93,"cat":"Coding","lic":"Apache 2.0",
     "d":"Top coding model. Beats GPT-4o on coding benchmarks. Full-stack.","tags":["Coding","Full-Stack","128K"],
     "bf":"Best open code model","repo":"bartowski/Qwen2.5-Coder-32B-Instruct-GGUF","file":"Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf"},
    {"n":"Qwen3-Coder-30B-A3B","p":"30B (3B active)","q":"Q4_K_M","gb":18.4,"ctx":"128K","sc":91,"cat":"Coding","lic":"Apache 2.0",
     "d":"MoE coding specialist. Agentic coding, tool use, thinking mode.","tags":["Coding","MoE","Agentic"],
     "bf":"Best MoE coder","repo":"unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF","file":"Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"},
    {"n":"Devstral-Small-24B","p":"24B","q":"Q4_K_M","gb":14.5,"ctx":"128K","sc":88,"cat":"Coding","lic":"Apache 2.0",
     "d":"Mistral's agentic coding model. SWE-bench leader, tool use.","tags":["Coding","Agentic","SWE-bench"],
     "bf":"Best agentic coder","repo":"unsloth/Devstral-Small-2-24B-Instruct-2512-GGUF","file":"Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf"},
    {"n":"Phi-4-Mini","p":"3.8B","q":"Q4_K_M","gb":2.5,"ctx":"128K","sc":83,"cat":"Small / Efficient","lic":"MIT",
     "d":"Microsoft's tiny powerhouse. Strong reasoning for its size, STEM focus.","tags":["Tiny","STEM","Microsoft"],
     "bf":"Best tiny STEM model","repo":"MaziyarPanahi/Phi-4-mini-instruct-GGUF","file":"Phi-4-mini-instruct.Q4_K_M.gguf"},
    {"n":"SmolLM3-3B","p":"3B","q":"Q4_K_M","gb":2.0,"ctx":"128K","sc":79,"cat":"Small / Efficient","lic":"Apache 2.0",
     "d":"HuggingFace's tiny model. Excellent for constrained hardware.","tags":["Tiny","HuggingFace","Fast"],
     "bf":"Smallest capable model","repo":"ggml-org/SmolLM3-3B-GGUF","file":"SmolLM3-Q4_K_M.gguf"},
    {"n":"Qwen3-VL-8B","p":"8B","q":"Q4_K_M","gb":5.6,"ctx":"128K","sc":86,"cat":"Vision","lic":"Apache 2.0",
     "d":"See and understand images + text. OCR, diagrams, screenshots.","tags":["Vision","OCR","Multimodal"],
     "bf":"Best vision model at size","repo":"Qwen/Qwen3-VL-8B-Instruct-GGUF","file":"Qwen3VL-8B-Instruct-Q4_K_M.gguf"},
    {"n":"Functionary-v3.2-8B","p":"8B","q":"Q4_K_M","gb":4.9,"ctx":"8K","sc":84,"cat":"Agents","lic":"MIT",
     "d":"Purpose-built for function calling and tool use.","tags":["Function Calling","Tools","JSON"],
     "bf":"Best tool-use model","repo":"bartowski/functionary-small-v3.2-GGUF","file":"functionary-small-v3.2-Q4_K_M.gguf"},
    {"n":"Dolphin3.0-8B","p":"8B","q":"Q4_K_M","gb":4.9,"ctx":"128K","sc":85,"cat":"Uncensored","lic":"Llama 3.1",
     "d":"Uncensored Llama 3.1. No refusals, helpful for everything.","tags":["Uncensored","No Refusals","Llama"],
     "bf":"Best uncensored 8B","repo":"bartowski/Dolphin3.0-Llama3.1-8B-GGUF","file":"Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf"},
    {"n":"Nous-Hermes-3-8B","p":"8B","q":"Q4_K_M","gb":4.9,"ctx":"128K","sc":84,"cat":"Uncensored","lic":"Llama 3.1",
     "d":"Nous Research uncensored. Structured output, function calling.","tags":["Uncensored","Structured","Nous"],
     "bf":"Best uncensored + tools","repo":"bartowski/Hermes-3-Llama-3.1-8B-GGUF","file":"Hermes-3-Llama-3.1-8B-Q4_K_M.gguf"},
    {"n":"JOSIEFIED-Qwen3-8B","p":"8B","q":"Q4_K_M","gb":5.2,"ctx":"128K","sc":83,"cat":"Uncensored","lic":"Apache 2.0",
     "d":"Abliterated Qwen3-8B. Safety refusals removed from weights.","tags":["Abliterated","Qwen3","Uncensored"],
     "bf":"Best abliterated model","repo":"bartowski/Goekdeniz-Guelmez_Josiefied-Qwen3-8B-abliterated-v1-GGUF","file":"Goekdeniz-Guelmez_Josiefied-Qwen3-8B-abliterated-v1-Q4_K_M.gguf"},
    {"n":"MN-Violet-Lotus-12B","p":"12B","q":"Q4_K_M","gb":7.7,"ctx":"32K","sc":87,"cat":"Roleplay","lic":"CC BY-NC",
     "d":"Top roleplay model. Rich prose, character consistency, emotional range.","tags":["Roleplay","Creative","Prose"],
     "bf":"Best RP model","repo":"mradermacher/MN-Violet-Lotus-12B-GGUF","file":"MN-Violet-Lotus-12B.Q4_K_M.gguf"},
    {"n":"MythoMax-L2-13B","p":"13B","q":"Q4_K_M","gb":7.9,"ctx":"4K","sc":84,"cat":"Roleplay","lic":"Llama 2",
     "d":"Classic RP model. Tried and true community favorite.","tags":["Roleplay","Classic","Community"],
     "bf":"Most popular RP model","repo":"TheBloke/MythoMax-L2-13B-GGUF","file":"mythomax-l2-13b.Q4_K_M.gguf"},
    {"n":"Fimbulvetr-11B-v2","p":"11B","q":"Q4_K_M","gb":6.8,"ctx":"8K","sc":85,"cat":"Roleplay","lic":"Llama 2",
     "d":"Norse-themed RP model. Excellent at dark fantasy, adventure.","tags":["Roleplay","Fantasy","Adventure"],
     "bf":"Best fantasy RP","repo":"mradermacher/Fimbulvetr-11B-v2-GGUF","file":"Fimbulvetr-11B-v2.Q4_K_M.gguf"},
    {"n":"Lumimaid-v0.2-12B","p":"12B","q":"Q4_K_M","gb":7.7,"ctx":"32K","sc":86,"cat":"Roleplay","lic":"CC BY-NC",
     "d":"ERP-focused model. Detailed, creative, long-form.","tags":["Roleplay","NSFW","Creative"],
     "bf":"Best ERP model","repo":"bartowski/Lumimaid-v0.2-12B-GGUF","file":"Lumimaid-v0.2-12B-Q4_K_M.gguf"},
    {"n":"Noromaid-13B","p":"13B","q":"Q4_K_M","gb":7.9,"ctx":"8K","sc":82,"cat":"Roleplay","lic":"Llama 2",
     "d":"Community RP model with good character consistency.","tags":["Roleplay","Community","NSFW"],
     "bf":"Solid RP alternative","repo":"TheBloke/Noromaid-13B-v0.1.1-GGUF","file":"noromaid-13b-v0.1.1.Q4_K_M.gguf"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# WORKER THREADS
# ═══════════════════════════════════════════════════════════════════════════════
def _winget_available():
    if sys.platform != "win32": return False
    try: subprocess.check_output(["winget","--version"],stderr=subprocess.DEVNULL,timeout=5); return True
    except: return False

class WingetInstallWorker(QThread):
    sig_line = pyqtSignal(str); sig_done = pyqtSignal(str, bool)
    def __init__(self, pkg_id, name): super().__init__(); self.pkg_id = pkg_id; self.name = name
    def run(self):
        try:
            proc = subprocess.Popen(["winget","install","--id",self.pkg_id,"--accept-package-agreements",
                "--accept-source-agreements","--silent"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
            for line in proc.stdout:
                line = line.strip()
                if line: self.sig_line.emit(line)
            proc.wait()
            self.sig_done.emit(self.name, proc.returncode == 0)
        except FileNotFoundError: self.sig_done.emit("winget not found", False)
        except Exception as e: self.sig_done.emit(str(e), False)

class DownloadWorker(QThread):
    sig_progress = pyqtSignal(int, int)  # downloaded_bytes, total_bytes
    sig_status = pyqtSignal(str)
    sig_done = pyqtSignal(str)
    sig_err = pyqtSignal(str)
    def __init__(self, repo, fn, dest):
        super().__init__(); self.repo = repo; self.fn = fn; self.dest = dest; self._cancel = False
    def cancel(self): self._cancel = True
    def run(self):
        try:
            self.sig_status.emit(f"Downloading {self.fn}...")
            path = hf_hub_download(repo_id=self.repo, filename=self.fn, local_dir=self.dest)
            if self._cancel: return
            self.sig_done.emit(str(path))
        except Exception as e: self.sig_err.emit(str(e))

class OllamaPullWorker(QThread):
    """Pull a model via 'ollama pull' — handles sharded models natively."""
    sig_line = pyqtSignal(str); sig_done = pyqtSignal(str, bool)
    def __init__(self, model_tag): super().__init__(); self.model_tag = model_tag; self._cancel = False
    def cancel(self): self._cancel = True
    def run(self):
        try:
            proc = subprocess.Popen(["ollama","pull",self.model_tag],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
            for line in proc.stdout:
                if self._cancel: proc.terminate(); return
                line = line.strip()
                if line: self.sig_line.emit(line)
            proc.wait()
            self.sig_done.emit(self.model_tag, proc.returncode == 0)
        except FileNotFoundError: self.sig_done.emit("Ollama not installed", False)
        except Exception as e: self.sig_done.emit(str(e), False)

class HFFileSizeWorker(QThread):
    """Check actual file size on HuggingFace before downloading."""
    sig_result = pyqtSignal(str, int)  # filename, size_bytes
    sig_err = pyqtSignal(str)
    def __init__(self, repo, filename): super().__init__(); self.repo = repo; self.fn = filename
    def run(self):
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            info = api.model_info(self.repo, files_metadata=True)
            for f in info.siblings or []:
                if f.rfilename == self.fn:
                    self.sig_result.emit(self.fn, f.size or 0); return
            self.sig_result.emit(self.fn, 0)
        except Exception as e: self.sig_err.emit(str(e))

class HFSearchWorker(QThread):
    sig_results = pyqtSignal(list); sig_err = pyqtSignal(str)
    def __init__(self, query, limit=20): super().__init__(); self.query = query; self.limit = limit
    def run(self):
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            models = list(api.list_models(search=self.query, library="gguf", sort="downloads", direction=-1, limit=self.limit))
            results = []
            for m in models:
                tags = list(m.tags) if m.tags else []
                results.append({"id": m.id, "downloads": m.downloads or 0, "likes": m.likes or 0,
                    "tags": tags[:6], "last_modified": str(m.last_modified)[:10] if m.last_modified else "?"})
            self.sig_results.emit(results)
        except Exception as e: self.sig_err.emit(str(e))

class HFFilesWorker(QThread):
    sig_files = pyqtSignal(str, list); sig_err = pyqtSignal(str)
    def __init__(self, repo_id): super().__init__(); self.repo_id = repo_id
    def run(self):
        try:
            from huggingface_hub import HfApi
            api = HfApi(); files = api.list_repo_files(self.repo_id)
            info = api.model_info(self.repo_id, files_metadata=True)
            size_map = {f.rfilename: f.size for f in (info.siblings or []) if f.size}
            gguf_files = []
            for f in files:
                if f.endswith(".gguf"):
                    fl = f.lower(); quant = "unknown"
                    for q in ["q8_0","q6_k","q5_k_m","q5_k_s","q4_k_m","q4_k_s","q4_0","q3_k_m","q3_k_s","q2_k",
                              "iq4_xs","iq4_nl","iq3_m","iq3_s","iq2_m","iq1_s","f16","bf16"]:
                        if q in fl: quant = q.upper(); break
                    sz = size_map.get(f, 0)
                    gguf_files.append({"name": f, "quant": quant, "size": sz})
            self.sig_files.emit(self.repo_id, gguf_files)
        except Exception as e: self.sig_err.emit(str(e))

class BenchWorker(QThread):
    sig_done = pyqtSignal(dict); sig_err = pyqtSignal(str)
    def __init__(self, model_path, backend, prompt):
        super().__init__(); self.model_path = model_path; self.backend = backend; self.prompt = prompt
    def run(self):
        try:
            start = _t.time()
            resp = requests.post("http://localhost:11434/api/generate",
                json={"model": self.model_path, "prompt": self.prompt, "stream": False}, timeout=120)
            elapsed = _t.time() - start; data = resp.json()
            total_tokens = data.get("eval_count", 0)
            eval_dur = data.get("eval_duration", 0) / 1e9
            toks = round(total_tokens / eval_dur, 1) if eval_dur > 0 else 0
            ttft = round(data.get("prompt_eval_duration", 0) / 1e9, 2)
            self.sig_done.emit({"tok_s": toks, "tokens": total_tokens, "elapsed": round(elapsed,1),
                "ttft": ttft, "method": "ollama", "model": self.model_path})
        except requests.exceptions.ConnectionError:
            self.sig_err.emit("Cannot connect to Ollama. Run 'ollama serve' first, then load a model.")
        except Exception as e: self.sig_err.emit(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD QUEUE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class DownloadQueue(QObject):
    sig_started = pyqtSignal(dict)       # model started
    sig_progress = pyqtSignal(dict, int) # model, percent (0-100, -1=indeterminate)
    sig_finished = pyqtSignal(dict, str) # model, path
    sig_error = pyqtSignal(dict, str)    # model, error
    sig_queue_changed = pyqtSignal()     # queue updated

    def __init__(self):
        super().__init__(); self._queue = []; self._active = None; self._worker = None

    @property
    def queue(self): return list(self._queue)
    @property
    def active(self): return self._active
    @property
    def count(self): return len(self._queue) + (1 if self._active else 0)

    def add(self, model, dest):
        self._queue.append({"model": model, "dest": dest})
        self.sig_queue_changed.emit()
        if not self._active: self._next()

    def cancel_active(self):
        if self._worker:
            self._worker.cancel()
            try: self._worker.terminate()
            except: pass
        self._active = None; self.sig_queue_changed.emit()
        self._next()

    def remove_queued(self, idx):
        if 0 <= idx < len(self._queue):
            self._queue.pop(idx); self.sig_queue_changed.emit()

    def _next(self):
        if not self._queue: self._active = None; self.sig_queue_changed.emit(); return
        item = self._queue.pop(0); m = item["model"]; dest = item["dest"]
        self._active = m; self.sig_started.emit(m)
        self._worker = DownloadWorker(m["repo"], m.get("file",""), dest)
        self._worker.sig_status.connect(lambda s: None)
        self._worker.sig_done.connect(lambda p: self._on_done(p))
        self._worker.sig_err.connect(lambda e: self._on_err(e))
        self._worker.start(); self.sig_queue_changed.emit()

    def _on_done(self, path):
        m = self._active; self._active = None
        if m: self.sig_finished.emit(m, path)
        self._next()

    def _on_err(self, err):
        m = self._active; self._active = None
        if m: self.sig_error.emit(m, err)
        self._next()

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════
class ScoreBar(QWidget):
    def __init__(self, score, w=90, h=12):
        super().__init__(); self._s = score; self.setFixedSize(w + 30, h + 4)
        self._w = w; self._h = h
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = T(); p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t['bg3'])); p.drawRoundedRect(0, 2, self._w, self._h, 4, 4)
        ratio = self._s / 100; c = t['gn'] if self._s >= 85 else t['og'] if self._s >= 70 else t['rd']
        p.setBrush(QColor(c)); p.drawRoundedRect(0, 2, int(self._w * ratio), self._h, 4, 4)
        p.setPen(QColor(t['tx'])); f = p.font(); f.setPixelSize(10); f.setBold(True); p.setFont(f)
        p.drawText(self._w + 4, self._h, str(self._s)); p.end()

class BenchChart(QWidget):
    """Simple horizontal bar chart for benchmark history."""
    def __init__(self, data, parent=None):
        super().__init__(parent); self._data = data  # list of {"model":..., "tok_s":...}
        self.setMinimumHeight(max(40, len(data) * 32 + 20))
    def paintEvent(self, e):
        if not self._data: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); t = T()
        w = self.width(); h = self.height(); n = len(self._data)
        max_tok = max(d["tok_s"] for d in self._data) or 1; bar_h = min(24, (h - 10) // max(n, 1))
        for i, d in enumerate(self._data):
            y = 5 + i * (bar_h + 6); ratio = d["tok_s"] / max_tok
            label_w = 140; bar_w = int((w - label_w - 70) * ratio)
            # Label
            p.setPen(QColor(t['tx2'])); f = p.font(); f.setPixelSize(11); p.setFont(f)
            model_short = d["model"][:18] + ("..." if len(d["model"]) > 18 else "")
            p.drawText(0, y, label_w, bar_h, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, model_short)
            # Bar
            p.setPen(Qt.PenStyle.NoPen)
            c = t['gn'] if d["tok_s"] >= 20 else t['og'] if d["tok_s"] >= 10 else t['rd']
            p.setBrush(QColor(c)); p.drawRoundedRect(label_w + 8, y, max(4, bar_w), bar_h, 4, 4)
            # Value
            p.setPen(QColor(t['tx'])); f.setBold(True); p.setFont(f)
            p.drawText(label_w + bar_w + 14, y, 60, bar_h, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{d['tok_s']} t/s")
        p.end()

class CompareWidget(QFrame):
    def __init__(self, models, hw):
        super().__init__(); t = T()
        self.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['ac']};border-radius:12px;padding:14px;}}")
        lo = QVBoxLayout(self); lo.setSpacing(8)
        lo.addWidget(QLabel(f"<span style='color:{t['ac']};font-size:15px;font-weight:bold'>📊 Side-by-Side Comparison</span>"))
        tbl = QTableWidget(7, len(models)); tbl.setVerticalHeaderLabels(["Score","Parameters","Size","Context","Speed","Fits?","License"])
        tbl.setHorizontalHeaderLabels([m["n"] for m in models])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setStyleSheet(f"color:{t['tx2']};font-size:12px;")
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); tbl.setMaximumHeight(240)
        mx = hw.max_model_gb()
        for j, m in enumerate(models):
            toks = hw.estimate_toks(m["gb"]); lbl, clr = hw.speed_label(toks)
            fits = m.get("gb",0) <= mx
            vals = [str(m["sc"]), m["p"], f"{m['gb']} GB", m["ctx"], f"~{toks} tok/s ({lbl})",
                    "✓ Fits" if fits else "⚠ Too large", m["lic"]]
            colors = [t['ac'], t['tx'], t['tx'], t['tx'], t[clr], t['gn'] if fits else t['rd'], t['tx2']]
            for i, (v, c) in enumerate(zip(vals, colors)):
                item = QTableWidgetItem(v); item.setForeground(QColor(c)); tbl.setItem(i, j, item)
        lo.addWidget(tbl)

class ModelCard(QFrame):
    sig_dl = pyqtSignal(dict); sig_compare = pyqtSignal(dict, bool)
    def __init__(self, m, hw=None, show_speed=True, show_compare=False):
        super().__init__(); self._m = m; t = T()
        self.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:12px;}}")
        lo = QVBoxLayout(self); lo.setSpacing(4); lo.setContentsMargins(12,10,12,8)
        r1 = QHBoxLayout(); r1.setSpacing(6)
        is_fav = FavoritesManager.is_fav(m["n"])
        self._star = QPushButton("★" if is_fav else "☆"); self._star.setFixedSize(26,26); self._star.setCursor(Qt.CursorShape.PointingHandCursor)
        sc = t['og'] if is_fav else t['tx3']
        self._star.setStyleSheet(f"QPushButton{{background:transparent;color:{sc};font-size:16px;border:none;}}QPushButton:hover{{color:{t['og']};}}")
        self._star.setToolTip("Unfavorite" if is_fav else "Add to Favorites")
        self._star.clicked.connect(self._toggle_fav); r1.addWidget(self._star)
        nm = QLabel(m["n"]); nm.setStyleSheet(f"font-size:14px;font-weight:bold;color:{t['ac']};"); r1.addWidget(nm)
        cat = QLabel(m["cat"]); cat.setStyleSheet(f"background:{t['bg3']};color:{t['tx2']};padding:2px 8px;border-radius:10px;font-size:11px;"); r1.addWidget(cat)
        note = FavoritesManager.get_note(m["n"])
        self._note_btn = QPushButton("📝" if note else "📋"); self._note_btn.setFixedSize(26,26); self._note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._note_btn.setStyleSheet(f"QPushButton{{background:transparent;font-size:14px;border:none;}}QPushButton:hover{{background:{t['bg3']};border-radius:4px;}}")
        self._note_btn.setToolTip(f"Note: {note}" if note else "Add a note")
        self._note_btn.clicked.connect(self._edit_note); r1.addWidget(self._note_btn)
        r1.addStretch(); r1.addWidget(ScoreBar(m["sc"])); lo.addLayout(r1)
        # Specs + speed + fit + VRAM warning
        sp_parts = [f"{m['p']}", f"{m['q']} ≈ {m['gb']} GB", f"Ctx: {m['ctx']}", m['lic']]
        sp_html = f"<span style='color:{t['tx2']}'> · ".join(sp_parts) + "</span>"
        if hw and show_speed:
            toks = hw.estimate_toks(m["gb"]); lbl, clr = hw.speed_label(toks)
            sp_html += f"  <span style='color:{t[clr]};font-weight:bold'>~{toks} tok/s ({lbl})</span>"
        fit = ""
        if hw:
            mx = hw.max_model_gb()
            if m.get("gb",0) <= mx: fit = f" <span style='color:{t['gn']}'>✓ Fits</span>"
            else: fit = f" <span style='color:{t['rd']}'>⚠ {m['gb']}GB exceeds {mx}GB limit</span>"
        sp = QLabel(sp_html + fit); sp.setTextFormat(Qt.TextFormat.RichText); sp.setWordWrap(True); sp.setStyleSheet("font-size:12px;"); lo.addWidget(sp)
        d = QLabel(m["d"]); d.setWordWrap(True); d.setStyleSheet(f"color:{t['tx']};font-size:12px;"); lo.addWidget(d)
        r4 = QHBoxLayout(); r4.setSpacing(4)
        for tg in m.get("tags",[])[:4]:
            lb = QLabel(tg); lb.setStyleSheet(f"background:{t['bg3']};color:{t['tx']};padding:2px 8px;border-radius:10px;font-size:10px;"); lb.setFixedHeight(18); r4.addWidget(lb)
        r4.addStretch()
        bf = QLabel(m.get("bf","")); bf.setStyleSheet(f"color:{t['gn']};font-size:11px;font-style:italic;"); r4.addWidget(bf)
        if show_compare:
            cb = QCheckBox("Compare"); cb.stateChanged.connect(lambda s: self.sig_compare.emit(m, s == Qt.CheckState.Checked.value))
            r4.addWidget(cb)
        if m.get("repo"):
            btn = QPushButton("⬇ Download"); btn.setFixedHeight(26); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton{{background:{t['gn']};color:{t['bg0']};font-size:11px;padding:3px 12px;border-radius:6px;font-weight:bold;}}QPushButton:hover{{background:{t['tl']};}}")
            btn.clicked.connect(lambda: self.sig_dl.emit(m)); r4.addWidget(btn)
        elif m.get("n") in ("Qwen3-235B-A22B","Llama-4-Scout"):
            # Ollama pull button for sharded models
            tag = "qwen3:235b" if "235B" in m["n"] else "llama4-scout"
            btn = QPushButton(f"🟢 ollama pull"); btn.setFixedHeight(26); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton{{background:#76b900;color:#000;font-size:11px;padding:3px 12px;border-radius:6px;font-weight:bold;}}QPushButton:hover{{background:#88cc00;}}")
            btn.clicked.connect(lambda _, t=tag: self.sig_dl.emit({"_ollama_pull": t, "n": m["n"]})); r4.addWidget(btn)
        lo.addLayout(r4)

    def _toggle_fav(self):
        t = T(); now = FavoritesManager.toggle_fav(self._m["n"])
        self._star.setText("★" if now else "☆"); sc = t['og'] if now else t['tx3']
        self._star.setStyleSheet(f"QPushButton{{background:transparent;color:{sc};font-size:16px;border:none;}}QPushButton:hover{{color:{t['og']};}}")
        self._star.setToolTip("Unfavorite" if now else "Add to Favorites")

    def _edit_note(self):
        cur = FavoritesManager.get_note(self._m["n"])
        text, ok = QInputDialog.getText(self, f"Note — {self._m['n']}", "Your note:", text=cur)
        if ok:
            FavoritesManager.set_note(self._m["n"], text)
            self._note_btn.setText("📝" if text else "📋")
            self._note_btn.setToolTip(f"Note: {text}" if text else "Add a note")

# ═══════════════════════════════════════════════════════════════════════════════
# FIRST-RUN WIZARD
# ═══════════════════════════════════════════════════════════════════════════════
class WizardDialog(QDialog):
    def __init__(self, hw, parent=None):
        super().__init__(parent); self._hw = hw; self._step = 0; self._picks = []
        t = T(); self.setWindowTitle("Welcome to AI Model Compass"); self.setFixedSize(700, 520); self.setStyleSheet(_qss(t))
        self._lo = QVBoxLayout(self); self._lo.setContentsMargins(30,24,30,20)
        self._stack = QStackedWidget(); self._lo.addWidget(self._stack, 1)
        # Page 0: Welcome
        p0 = QWidget(); p0l = QVBoxLayout(p0); p0l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p0l.addWidget(QLabel(f"<div style='text-align:center;font-size:32px'>🧭</div>"))
        p0l.addWidget(QLabel(f"<div style='text-align:center;font-size:22px;font-weight:bold;color:{t['ac']}'>Welcome to {APP}</div>"))
        p0l.addWidget(QLabel(f"<div style='text-align:center;color:{t['tx2']}'>Let's find the perfect AI models for your computer.</div>"))
        p0l.addSpacing(16)
        hw_box = QFrame(); hw_box.setStyleSheet(f"QFrame{{background:{t['bg1']};color:{t['tx']};border:1px solid {t['gn']};border-radius:12px;padding:16px;}}")
        hbl = QVBoxLayout(hw_box)
        hbl.addWidget(QLabel(f"<span style='color:{t['gn']};font-weight:bold;font-size:14px'>🖥️ Hardware Detected</span>"))
        gpu_c = {"nvidia":"#76b900","amd":"#ED1C24","intel":"#0071C5"}.get(hw.gpu_vendor, t['tx2'])
        vr = f"{hw.vram_gb} GB VRAM" if hw.vram_gb > 0 else "N/A"
        hbl.addWidget(QLabel(f"<b>CPU:</b> {html_mod.escape(hw.cpu_name)} ({hw.cpu_cores}C/{hw.cpu_threads}T)<br>"
            f"<b>RAM:</b> {hw.ram_gb} GB<br><b>GPU:</b> <span style='color:{gpu_c}'>{html_mod.escape(hw.gpu_name)}</span><br>"
            f"<b>VRAM:</b> <span style='color:{t['ac']}'>{vr}</span><br>"
            f"<b>Tier:</b> <span style='color:{t['gn']};font-weight:bold'>{hw.tier_label}</span> · Max GGUF: ~{hw.max_model_gb()} GB"))
        p0l.addWidget(hw_box); self._stack.addWidget(p0)
        # Page 1: Use case
        p1 = QWidget(); p1l = QVBoxLayout(p1)
        p1l.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>What interests you?</span>"))
        p1l.addWidget(QLabel(f"<span style='color:{t['tx2']}'>Pick one or more. We'll recommend the best models.</span>"))
        p1l.addSpacing(8); grid = QGridLayout(); grid.setSpacing(10)
        uc_data = [("💬","Chat & Writing","General conversation"),("💻","Coding","Code generation"),
            ("🎭","Roleplay","Character fiction"),("🔓","Uncensored","No safety filters"),
            ("🎨","Image Gen","Create art"),("🔊","Voice & Audio","TTS, transcription"),
            ("🔬","Research","Analysis, math"),("🤖","AI Agents","Automation")]
        self._uc_btns = []
        for i, (icon, title, desc) in enumerate(uc_data):
            btn = QPushButton(f"{icon}\n{title}"); btn.setCheckable(True); btn.setFixedSize(145, 90)
            btn.setStyleSheet(f"QPushButton{{background:{t['bg1']};border:2px solid {t['bd']};border-radius:12px;font-size:13px;font-weight:bold;color:{t['tx']};}}QPushButton:checked{{border-color:{t['ac']};background:{t['acs']};}}QPushButton:hover{{border-color:{t['ac2']};}}")
            btn.setToolTip(desc); grid.addWidget(btn, i//4, i%4); self._uc_btns.append((btn, title))
        p1l.addLayout(grid); p1l.addStretch(); self._stack.addWidget(p1)
        # Page 2: Results
        p2 = QWidget(); self._p2l = QVBoxLayout(p2)
        self._p2l.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>⭐ Your Starter Pack</span>"))
        self._rec_area = QVBoxLayout(); self._p2l.addLayout(self._rec_area); self._p2l.addStretch()
        self._stack.addWidget(p2)
        nav = QHBoxLayout()
        self._back = QPushButton("← Back"); self._back.setProperty("class","ghost"); self._back.clicked.connect(self._go_back); self._back.setVisible(False)
        nav.addWidget(self._back); nav.addStretch()
        self._next = QPushButton("Next →"); self._next.clicked.connect(self._go_next); self._next.setFixedHeight(40); self._next.setMinimumWidth(120)
        nav.addWidget(self._next); self._lo.addLayout(nav)

    def _go_next(self):
        if self._step == 0: self._step = 1
        elif self._step == 1: self._build_rec(); self._step = 2; self._next.setText("🚀 Get Started!")
        elif self._step == 2:
            cfg = _load_cfg(); cfg["wizard_done"] = True; cfg["picks"] = self._picks; _save_cfg(cfg)
            self.accept(); return
        self._stack.setCurrentIndex(self._step); self._back.setVisible(self._step > 0)
    def _go_back(self):
        self._step = max(0, self._step - 1); self._stack.setCurrentIndex(self._step)
        self._back.setVisible(self._step > 0); self._next.setText("Next →")
    def _build_rec(self):
        t = T()
        while self._rec_area.count():
            it = self._rec_area.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        sel = [title for btn, title in self._uc_btns if btn.isChecked()]
        cat_map = {"Chat & Writing":["General Purpose","Small / Efficient"],"Coding":["Coding"],
                   "Roleplay":["Roleplay","Uncensored"],"Uncensored":["Uncensored"],
                   "Research":["General Purpose","Long Context"],"AI Agents":["Agents","Coding"]}
        cats = set()
        for s in sel: cats.update(cat_map.get(s, []))
        mx = self._hw.max_model_gb()
        cands = [m for m in MODEL_DB if m["cat"] in cats and m.get("gb",0) <= mx]
        if not cands: cands = [m for m in MODEL_DB if m.get("gb",0) <= mx]
        cands.sort(key=lambda m: m["sc"], reverse=True); top = cands[:3]; self._picks = [m["n"] for m in top]
        if not top:
            self._rec_area.addWidget(QLabel(f"<span style='color:{t['og']}'>No models fit. Check Models after setup.</span>"))
        for i, m in enumerate(top):
            toks = self._hw.estimate_toks(m["gb"]); lbl, clr = self._hw.speed_label(toks)
            frm = QFrame(); frm.setStyleSheet(f"QFrame{{background:{t['bg1']};color:{t['tx']};border:1px solid {t['gn'] if i==0 else t['bd']};border-radius:10px;padding:12px;}}")
            fl = QVBoxLayout(frm); prefix = "⭐ TOP PICK — " if i == 0 else ""
            fl.addWidget(QLabel(f"<span style='color:{t['ac']};font-size:14px;font-weight:bold'>{prefix}{m['n']}</span>"))
            fl.addWidget(QLabel(f"<span style='color:{t['tx2']}'>{m['p']} · {m['gb']} GB · {m['ctx']} ctx</span>"
                f"  <span style='color:{t[clr]};font-weight:bold'>~{toks} tok/s ({lbl})</span>"))
            fl.addWidget(QLabel(f"<span style='color:{t['tx']}'>{html_mod.escape(m['d'])}</span>"))
            self._rec_area.addWidget(frm)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════════════════════════
class HomePage(QWidget):
    def __init__(self, hw, sw):
        super().__init__(); t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(24,20,24,12); lo.setSpacing(16)
        lo.addWidget(QLabel(f"<div style='text-align:center;font-size:28px;font-weight:bold;color:{t['ac']}'>🧭 {APP}</div>"))
        lo.addWidget(QLabel(f"<div style='text-align:center;color:{t['tx2']}'>Discover, download, and run local AI — tailored to your hardware</div>"))
        row = QHBoxLayout(); row.setSpacing(16)
        # HW card
        hwc = QFrame(); hwc.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:12px;padding:18px;}}")
        hl = QVBoxLayout(hwc)
        hl.addWidget(QLabel(f"<span style='font-size:15px;font-weight:bold;color:{t['ac']}'>🖥️ Your Hardware</span>"))
        gc = {"nvidia":"#76b900","amd":"#ED1C24","intel":"#0071C5"}.get(hw.gpu_vendor, t['tx2'])
        vr = f"{hw.vram_gb} GB" if hw.vram_gb > 0 else "N/A"
        hl.addWidget(QLabel(f"<table width='100%'><tr><td style='color:{t['tx2']};width:80px'>CPU</td><td>{html_mod.escape(hw.cpu_name)}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>RAM</td><td>{hw.ram_gb} GB</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>GPU</td><td style='color:{gc};font-weight:bold'>{html_mod.escape(hw.gpu_name)}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>VRAM</td><td style='color:{t['ac']};font-weight:bold'>{vr}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>Tier</td><td style='color:{t['gn']};font-weight:bold'>{hw.tier_label}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>Bandwidth</td><td>{hw.mem_bw} GB/s</td></tr></table>"))
        # Refresh + Export buttons
        br = QHBoxLayout()
        rb = QPushButton("🔄 Refresh"); rb.setProperty("class","ghost"); rb.setFixedHeight(28)
        rb.clicked.connect(lambda: (hw.refresh(), toast(f"Hardware refreshed: {hw.gpu_name} · {hw.vram_gb}GB")))
        br.addWidget(rb)
        eb = QPushButton("📋 Copy Profile"); eb.setProperty("class","ghost"); eb.setFixedHeight(28)
        eb.clicked.connect(lambda: (QApplication.clipboard().setText(hw.export_profile()), toast("System profile copied to clipboard!")))
        br.addWidget(eb); br.addStretch()
        hl.addLayout(br); hl.addStretch(); row.addWidget(hwc)
        # SW card
        swc = QFrame(); swc.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:12px;padding:18px;}}")
        sl = QVBoxLayout(swc)
        sl.addWidget(QLabel(f"<span style='font-size:15px;font-weight:bold;color:{t['ac']}'>⚙️ Software</span>"))
        for k, info in SoftwareDetector.TOOLS.items():
            ok = sw.is_installed(k); ver = sw.get_version(k)
            ic = f"<span style='color:{t['gn']}'>✓</span>" if ok else f"<span style='color:{t['tx3']}'>✗</span>"
            ver_str = f" <span style='color:{t['tx3']};font-size:11px'>v{ver}</span>" if ver else ""
            sl.addWidget(QLabel(f"{ic} <b>{info['name']}</b>{ver_str} <span style='color:{t['gn'] if ok else t['tx3']};font-size:12px'>{'Installed' if ok else 'Not found'}</span>"))
        sl.addStretch(); row.addWidget(swc)
        # Quick start card
        qc = QFrame(); qc.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:12px;padding:18px;}}")
        ql = QVBoxLayout(qc)
        ql.addWidget(QLabel(f"<span style='font-size:15px;font-weight:bold;color:{t['ac']}'>🚀 Quick Start</span>"))
        for n, title, desc in [("1","<b>🎯 Recommend</b>","HW detected — pick use case"),("2","<b>⬇ Download</b>","GGUF from HuggingFace"),("3","<b>Open in software</b>","Auto-integrates with Ollama/LM Studio")]:
            ql.addWidget(QLabel(f"<span style='color:{t['ac']};font-size:18px;font-weight:bold'>{n}.</span> {title}<br><span style='color:{t['tx2']};font-size:12px'>{desc}</span>"))
        ql.addStretch(); row.addWidget(qc)
        lo.addLayout(row, 1)

class LearnPage(QWidget):
    def __init__(self):
        super().__init__(); t = T()
        lo = QHBoxLayout(self); lo.setContentsMargins(0,8,0,0); lo.setSpacing(0)
        sb = QWidget(); sb.setFixedWidth(200); sb.setStyleSheet(f"background:{t['bg1']};border-right:1px solid {t['bd']};")
        sbl = QVBoxLayout(sb); sbl.setContentsMargins(8,14,8,8)
        sbl.addWidget(QLabel(f"<span style='font-weight:bold;color:{t['ac']}'>📖 Topics</span>"))
        self._tp = _topics(t); self._ls = QListWidget()
        for k in self._tp: self._ls.addItem(k)
        sbl.addWidget(self._ls); lo.addWidget(sb)
        self._br = QTextBrowser(); self._br.setOpenExternalLinks(True)
        self._br.setStyleSheet(f"QTextBrowser{{background:{t['bg1']};border:none;padding:18px;}}"); lo.addWidget(self._br, 1)
        self._ls.currentRowChanged.connect(lambda r: self._br.setHtml(list(self._tp.values())[r]) if r>=0 else None)
        self._ls.setCurrentRow(0)

class ModelsPage(QWidget):
    sig_dl = pyqtSignal(dict)
    def __init__(self, hw):
        super().__init__(); self._hw = hw; self._compare_set = []; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8); lo.setSpacing(8)
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>🗄️ Model Database</span>"))
        self._cnt = QLabel(); self._cnt.setStyleSheet(f"color:{t['tx2']};"); hdr.addStretch(); hdr.addWidget(self._cnt)
        lo.addLayout(hdr)
        fl = QHBoxLayout(); fl.setSpacing(8)
        self._se = QLineEdit(); self._se.setPlaceholderText("🔍 Search models, tags, descriptions..."); self._se.setFixedHeight(36); fl.addWidget(self._se, 2)
        self._cf = QComboBox(); self._cf.addItem("All"); self._cf.addItems(CATEGORIES); self._cf.setFixedHeight(36); fl.addWidget(self._cf)
        self._sf = QComboBox(); self._sf.addItems(["Score ↓","Score ↑","Name","Size ↑","Size ↓"]); self._sf.setFixedHeight(36); fl.addWidget(self._sf)
        self._ff = QCheckBox("Fits my PC"); fl.addWidget(self._ff)
        self._cmp_btn = QPushButton("📊 Compare (0)"); self._cmp_btn.setProperty("class","ghost"); self._cmp_btn.setFixedHeight(36)
        self._cmp_btn.clicked.connect(self._show_compare); fl.addWidget(self._cmp_btn)
        lo.addLayout(fl)
        self._cmp_frame = None; self._cmp_lo = QVBoxLayout(); lo.addLayout(self._cmp_lo)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._sw = QWidget(); self._sl = QVBoxLayout(self._sw); self._sl.setSpacing(6); self._sl.setContentsMargins(0,0,6,0)
        sa.setWidget(self._sw); lo.addWidget(sa, 1)
        for sig in [self._se.textChanged, self._cf.currentIndexChanged, self._sf.currentIndexChanged, self._ff.stateChanged]:
            sig.connect(self._refresh)
        self._refresh()

    def _on_compare(self, m, add):
        if add:
            if len(self._compare_set) < 3 and m not in self._compare_set: self._compare_set.append(m)
        else: self._compare_set = [x for x in self._compare_set if x["n"] != m["n"]]
        self._cmp_btn.setText(f"📊 Compare ({len(self._compare_set)})")
    def _show_compare(self):
        if self._cmp_frame: self._cmp_frame.deleteLater(); self._cmp_frame = None
        if len(self._compare_set) >= 2:
            self._cmp_frame = CompareWidget(self._compare_set, self._hw); self._cmp_lo.addWidget(self._cmp_frame)
    def _refresh(self):
        while self._sl.count():
            it = self._sl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        q = self._se.text().lower(); cat = self._cf.currentText(); fl = MODEL_DB[:]
        if q: fl = [m for m in fl if q in m["n"].lower() or q in m["d"].lower() or q in m["cat"].lower() or any(q in tg.lower() for tg in m.get("tags",[]))]
        if cat != "All": fl = [m for m in fl if m["cat"]==cat]
        if self._ff.isChecked(): mx = self._hw.max_model_gb(); fl = [m for m in fl if m.get("gb",0)<=mx]
        si = self._sf.currentIndex()
        if si==0: fl.sort(key=lambda m:m["sc"],reverse=True)
        elif si==1: fl.sort(key=lambda m:m["sc"])
        elif si==2: fl.sort(key=lambda m:m["n"].lower())
        elif si==3: fl.sort(key=lambda m:m.get("gb",0))
        elif si==4: fl.sort(key=lambda m:m.get("gb",0),reverse=True)
        for m in fl:
            c = ModelCard(m, self._hw, show_compare=True); c.sig_dl.connect(self.sig_dl.emit); c.sig_compare.connect(self._on_compare)
            self._sl.addWidget(c)
        self._sl.addStretch(); self._cnt.setText(f"{len(fl)}/{len(MODEL_DB)}")

class RecommendPage(QWidget):
    sig_dl = pyqtSignal(dict)
    def __init__(self, hw):
        super().__init__(); self._hw = hw; t = T()
        lo = QHBoxLayout(self); lo.setContentsMargins(16,12,16,8); lo.setSpacing(16)
        left = QWidget(); left.setFixedWidth(320); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(10)
        hf = QFrame(); hf.setStyleSheet(f"QFrame{{background:{t['bg1']};border:2px solid {t['gn']};border-radius:10px;padding:12px;}}")
        hfl = QVBoxLayout(hf)
        gs = hw.gpu_name if hw.vram_gb>0 else "CPU Only"; vs = f"({hw.vram_gb}GB)" if hw.vram_gb>0 else f"({hw.ram_gb}GB RAM)"
        hfl.addWidget(QLabel(f"<span style='color:{t['gn']};font-weight:bold'>🖥️ {html_mod.escape(gs)} {vs}</span><br>"
            f"<span style='color:{t['tx2']}'>{hw.tier_label} · Max: ~{hw.max_model_gb()}GB · ~{hw.mem_bw} GB/s</span>"))
        ll.addWidget(hf)
        ucg = QGroupBox("Use Case"); ucl = QVBoxLayout(ucg); self._ucs = {}
        for name in USE_CASES: cb = QCheckBox(name); ucl.addWidget(cb); self._ucs[name] = cb
        ll.addWidget(ucg)
        btn = QPushButton("🔍 Find Best Models"); btn.setFixedHeight(44)
        btn.setStyleSheet(f"QPushButton{{background:{t['gn']};color:{t['bg0']};font-size:14px;font-weight:bold;border-radius:10px;}}QPushButton:hover{{background:{t['tl']};}}")
        btn.clicked.connect(self._find); ll.addWidget(btn); ll.addStretch(); lo.addWidget(left)
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0)
        self._rl = QLabel(f"<span style='font-size:17px;font-weight:bold;color:{t['ac']}'>📋 Results</span>"); rl.addWidget(self._rl)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._sw = QWidget(); self._sl = QVBoxLayout(self._sw); self._sl.setSpacing(6); self._sl.setContentsMargins(0,0,6,0)
        sa.setWidget(self._sw); rl.addWidget(sa, 1); lo.addWidget(right, 1)
        self._sl.addWidget(QLabel(f"<span style='color:{t['tx2']};padding:40px;font-size:14px'>Select use cases → Find</span>")); self._sl.addStretch()
    def _find(self):
        t = T()
        while self._sl.count():
            it = self._sl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        sel = [n for n, cb in self._ucs.items() if cb.isChecked()]
        if not sel: self._sl.addWidget(QLabel(f"<span style='color:{t['og']}'>Select at least one use case.</span>")); self._sl.addStretch(); return
        cats = set()
        for n in sel: cats.update(USE_CASES[n]["cats"])
        mx = self._hw.max_model_gb()
        cands = sorted([m for m in MODEL_DB if m["cat"] in cats and m.get("gb",0)<=mx], key=lambda m:m["sc"], reverse=True)
        gs = f"{self._hw.gpu_name} ({self._hw.vram_gb}GB)" if self._hw.vram_gb>0 else f"CPU ({self._hw.ram_gb}GB RAM)"
        self._sl.addWidget(QLabel(f"<div style='background:{t['bg2']};border:1px solid {t['bd']};border-radius:10px;padding:12px'>"
            f"<b style='color:{t['ac']}'>{html_mod.escape(gs)}</b> · {', '.join(sel)}<br>"
            f"<span style='color:{t['gn']};font-weight:bold'>{len(cands)} models fit</span></div>"))
        if cands:
            tf = QFrame(); tf.setStyleSheet(f"QFrame{{background:{t['bg1']};border:2px solid {t['gn']};border-radius:12px;padding:4px;}}")
            tfl = QVBoxLayout(tf); tfl.addWidget(QLabel(f"<span style='color:{t['gn']};font-size:13px;font-weight:bold'>⭐ TOP PICK</span>"))
            c = ModelCard(cands[0], self._hw); c.sig_dl.connect(self.sig_dl.emit); tfl.addWidget(c); self._sl.addWidget(tf)
            for m in cands[1:]: c = ModelCard(m, self._hw); c.sig_dl.connect(self.sig_dl.emit); self._sl.addWidget(c)
        self._sl.addStretch(); self._rl.setText(f"<span style='font-size:17px;font-weight:bold;color:{t['ac']}'>📋 {len(cands)} Results</span>")

class VRAMCalcPage(QWidget):
    def __init__(self, hw):
        super().__init__(); self._hw = hw; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(24,16,24,12); lo.setSpacing(16)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>📐 VRAM Calculator</span>"))
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>See exactly how a model fits your hardware. Drag the sliders.</span>"))
        hw_lbl = QLabel(f"<b>Your GPU:</b> <span style='color:{t['gn']}'>{html_mod.escape(hw.gpu_name)}</span> — "
            f"<span style='color:{t['ac']};font-weight:bold'>{hw.vram_gb} GB VRAM</span>" if hw.vram_gb > 0 else
            f"<b>CPU Only</b> — <span style='color:{t['ac']}'>{hw.ram_gb} GB RAM</span>")
        lo.addWidget(hw_lbl)
        fg = QGroupBox("Model Parameters")
        fl = QGridLayout(fg)
        fl.addWidget(QLabel("Parameters (B):"), 0, 0)
        self._ps = QSlider(Qt.Orientation.Horizontal); self._ps.setRange(1, 236); self._ps.setValue(8)
        fl.addWidget(self._ps, 0, 1); self._pl = QLabel("8B"); fl.addWidget(self._pl, 0, 2)
        fl.addWidget(QLabel("Quantization:"), 1, 0)
        self._qs = QComboBox(); self._qs.addItems(["Q2_K (3.00 bpw)","Q3_K_M (3.89)","Q4_K_M (4.83)","Q5_K_M (5.67)","Q6_K (6.57)","Q8_0 (8.50)","F16 (16.0)"])
        self._qs.setCurrentIndex(2); fl.addWidget(self._qs, 1, 1)
        fl.addWidget(QLabel("Context (K):"), 2, 0)
        self._cs = QSlider(Qt.Orientation.Horizontal); self._cs.setRange(1, 128); self._cs.setValue(8)
        fl.addWidget(self._cs, 2, 1); self._cl = QLabel("8K"); fl.addWidget(self._cl, 2, 2)
        lo.addWidget(fg)
        self._rb = QFrame(); self._rb.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:12px;padding:18px;}}")
        self._rl = QVBoxLayout(self._rb); lo.addWidget(self._rb)
        self._result = QLabel(); self._result.setWordWrap(True); self._result.setTextFormat(Qt.TextFormat.RichText); self._rl.addWidget(self._result)
        self._bar_frame = QFrame(); self._bar_frame.setFixedHeight(40); self._rl.addWidget(self._bar_frame)
        self._speed = QLabel(); self._speed.setTextFormat(Qt.TextFormat.RichText); self._rl.addWidget(self._speed)
        lo.addStretch()
        self._ps.valueChanged.connect(self._calc); self._qs.currentIndexChanged.connect(self._calc); self._cs.valueChanged.connect(self._calc)
        self._calc()

    def _calc(self):
        t = T(); params = self._ps.value(); self._pl.setText(f"{params}B")
        ctx = self._cs.value(); self._cl.setText(f"{ctx}K")
        bpw = [3.0, 3.89, 4.83, 5.67, 6.57, 8.50, 16.0][self._qs.currentIndex()]
        model_gb = round(params * bpw / 8, 1); kv_gb = round(ctx * 0.5 / 1024 * 8, 1)
        total = round(model_gb + kv_gb + 0.5, 1)
        avail = self._hw.vram_gb if self._hw.vram_gb > 0 else self._hw.ram_gb
        ratio = min(1.0, total / avail) if avail > 0 else 1.0
        if ratio < 0.75: fc, fl = t['gn'], "✓ Comfortable fit"
        elif ratio < 0.95: fc, fl = t['og'], "⚠ Tight fit"
        else: fc, fl = t['rd'], "❌ Won't fit — offloading needed"
        self._result.setText(f"<table width='100%'><tr><td style='color:{t['tx2']}'>Model weights</td><td style='font-weight:bold'>{model_gb} GB</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>KV cache ({ctx}K)</td><td>{kv_gb} GB</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>Overhead</td><td>~0.5 GB</td></tr>"
            f"<tr><td style='color:{t['ac']};font-weight:bold'>Total</td><td style='color:{fc};font-weight:bold;font-size:16px'>{total} / {avail} GB</td></tr>"
            f"<tr><td></td><td style='color:{fc};font-weight:bold'>{fl}</td></tr></table>")
        toks = self._hw.estimate_toks(model_gb); lbl, clr = self._hw.speed_label(toks)
        self._speed.setText(f"<span style='color:{t[clr]};font-size:15px;font-weight:bold'>~{toks} tok/s ({lbl})</span>")
        self._bar_frame.update()

class DownloadsPage(QWidget):
    def __init__(self, hw, sw, dl_queue):
        super().__init__(); self._hw=hw; self._sw=sw; self._q=dl_queue; self._ollama_wk=None; t=T()
        lo = QVBoxLayout(self); lo.setContentsMargins(20,16,20,12); lo.setSpacing(12)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>⬇️ Downloads & Integration</span>"))
        # Save dir
        dr = QHBoxLayout()
        dr.addWidget(QLabel("Save to:"))
        self._dir = QLineEdit(str(Path.home()/"AI-Models")); self._dir.setReadOnly(True); dr.addWidget(self._dir,1)
        bb = QPushButton("Browse"); bb.setProperty("class","sec"); bb.clicked.connect(self._browse); dr.addWidget(bb)
        ob = QPushButton("Open"); ob.setProperty("class","ghost"); ob.clicked.connect(self._opendir); dr.addWidget(ob)
        lo.addLayout(dr)
        # Active download frame
        self._df = QFrame(); self._df.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:14px;}}")
        dfl = QVBoxLayout(self._df)
        self._dn = QLabel("No active download"); self._dn.setStyleSheet("font-size:14px;font-weight:bold;"); dfl.addWidget(self._dn)
        self._ds = QLabel("Select a model and click Download"); self._ds.setWordWrap(True); self._ds.setStyleSheet(f"color:{t['tx2']};"); dfl.addWidget(self._ds)
        self._dp = QProgressBar(); self._dp.setRange(0,0); self._dp.setVisible(False); dfl.addWidget(self._dp)
        br = QHBoxLayout()
        self._cb = QPushButton("Cancel"); self._cb.setProperty("class","sec"); self._cb.setVisible(False)
        self._cb.clicked.connect(self._cancel); br.addWidget(self._cb); br.addStretch()
        self._int_ollama = QPushButton("🟢 Register in Ollama"); self._int_ollama.setVisible(False)
        self._int_ollama.setStyleSheet(f"QPushButton{{background:#76b900;color:#000;font-weight:bold;border-radius:8px;padding:8px 16px;}}"); br.addWidget(self._int_ollama)
        self._int_lm = QPushButton("🔵 Copy to LM Studio"); self._int_lm.setVisible(False)
        self._int_lm.setStyleSheet(f"QPushButton{{background:{t['ac']};color:{t['bg0']};font-weight:bold;border-radius:8px;padding:8px 16px;}}"); br.addWidget(self._int_lm)
        self._oex = QPushButton("📁 Explorer"); self._oex.setProperty("class","ghost"); self._oex.setVisible(False); br.addWidget(self._oex)
        dfl.addLayout(br); lo.addWidget(self._df)
        # Queue display
        self._queue_lbl = QLabel(f"<span style='font-size:14px;font-weight:bold;color:{t['ac']}'>Queue</span>"); lo.addWidget(self._queue_lbl)
        self._queue_list = QListWidget(); self._queue_list.setMaximumHeight(100)
        self._queue_list.setStyleSheet(f"QListWidget{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:8px;}}QListWidget::item{{padding:6px;border-bottom:1px solid {t['bd']};}}")
        lo.addWidget(self._queue_list)
        # History
        lo.addWidget(QLabel(f"<span style='font-size:14px;font-weight:bold;color:{t['ac']}'>History</span>"))
        self._hist = QListWidget(); self._hist.setMaximumHeight(150)
        self._hist.setStyleSheet(f"QListWidget{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:8px;}}QListWidget::item{{padding:8px;border-bottom:1px solid {t['bd']};}}")
        self._hist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._hist.customContextMenuRequested.connect(self._hist_ctx)
        lo.addWidget(self._hist)
        # Install software section
        lo.addWidget(QLabel(f"<span style='font-size:14px;font-weight:bold;color:{t['ac']}'>Install Software</span>"))
        self._has_winget = _winget_available()
        if self._has_winget:
            lo.addWidget(QLabel(f"<span style='color:{t['gn']};font-size:12px'>✓ winget detected — one-click install</span>"))
        else:
            lo.addWidget(QLabel(f"<span style='color:{t['tx3']};font-size:12px'>winget not found — opens download pages</span>"))
        sr = QHBoxLayout(); sr.setSpacing(8)
        self._install_btns = {}; self._install_workers = {}
        for k in ["lmstudio","ollama","gpt4all","koboldcpp","jan"]:
            info = SoftwareDetector.TOOLS[k]; ok = sw.is_installed(k)
            b = QPushButton(f"{info['icon']} {'✓ ' if ok else ''}{info['name']}"); b.setFixedHeight(36)
            if ok: b.setEnabled(False); b.setToolTip("Already installed")
            else:
                b.setProperty("class","ghost"); winget_id = info.get("winget")
                if self._has_winget and winget_id:
                    b.setToolTip(f"Install via winget ({winget_id})")
                    b.clicked.connect(lambda _, key=k, wid=winget_id, nm=info['name']: self._winget_install(key, wid, nm))
                else:
                    url = info["url"]; b.setToolTip(f"Download from {url}")
                    b.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            sr.addWidget(b); self._install_btns[k] = b
        sr.addStretch(); lo.addLayout(sr)
        self._install_log = QLabel(""); self._install_log.setWordWrap(True)
        self._install_log.setStyleSheet(f"color:{t['tx2']};font-size:12px;"); self._install_log.setVisible(False)
        lo.addWidget(self._install_log); lo.addStretch()
        # Connect queue signals
        dl_queue.sig_started.connect(self._on_q_started)
        dl_queue.sig_finished.connect(self._on_q_finished)
        dl_queue.sig_error.connect(self._on_q_error)
        dl_queue.sig_queue_changed.connect(self._update_queue_display)
        self._load_hist()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self,"Folder",self._dir.text())
        if d: self._dir.setText(d)
    def _opendir(self):
        d=self._dir.text(); Path(d).mkdir(parents=True,exist_ok=True)
        if sys.platform=="win32": os.startfile(d)
        else: subprocess.Popen(["xdg-open",d])

    def start_download(self, m):
        """Entry point — called from model cards across the app."""
        t = T()
        # Handle ollama pull for sharded models
        if m.get("_ollama_pull"):
            self._start_ollama_pull(m["_ollama_pull"], m["n"]); return
        if not m.get("repo"): return
        # VRAM compatibility warning
        mx = self._hw.max_model_gb()
        if m.get("gb",0) > mx:
            toast(f"⚠ {m['n']} ({m['gb']}GB) exceeds your {mx}GB limit — may require offloading", T()['og'])
        dest = self._dir.text(); Path(dest).mkdir(parents=True,exist_ok=True)
        self._q.add(m, dest)
        toast(f"⬇ {m['n']} added to download queue ({self._q.count} in queue)")

    def _start_ollama_pull(self, tag, name):
        t = T()
        if not self._sw.is_installed("ollama"):
            toast("❌ Ollama not installed. Install it first.", t['rd']); return
        self._dn.setText(f"🟢 Pulling {name} via Ollama...")
        self._ds.setText(f"ollama pull {tag}"); self._dp.setVisible(True); self._dp.setRange(0,0)
        self._cb.setVisible(True)
        self._ollama_wk = OllamaPullWorker(tag)
        self._ollama_wk.sig_line.connect(lambda l: self._ds.setText(l[:120]))
        self._ollama_wk.sig_done.connect(lambda msg, ok: self._ollama_done(msg, ok, name))
        self._ollama_wk.start()

    def _ollama_done(self, msg, ok, name):
        t = T(); self._dp.setVisible(False); self._cb.setVisible(False)
        if ok:
            self._dn.setText(f"✅ {name} pulled via Ollama!"); self._ds.setText(f"Run: ollama run {msg}")
            toast(f"✅ {name} ready via Ollama!", t['gn'])
        else:
            self._dn.setText(f"❌ Failed"); self._ds.setText(msg)
            toast(f"❌ Ollama pull failed: {msg}", t['rd'])

    def _on_q_started(self, m):
        t = T()
        self._dn.setText(f"⬇️ {m['n']} ({m.get('gb','?')} GB)")
        self._ds.setText(f"Downloading {m.get('file','')}..."); self._dp.setVisible(True); self._dp.setRange(0,0)
        self._cb.setVisible(True); self._int_ollama.setVisible(False); self._int_lm.setVisible(False); self._oex.setVisible(False)

    def _on_q_finished(self, m, path):
        t = T(); self._dp.setVisible(False); self._cb.setVisible(False)
        self._dn.setText(f"✅ {m['n']} — Downloaded!"); self._ds.setText(f"Saved: {path}")
        self._oex.setVisible(True)
        try: self._oex.clicked.disconnect()
        except: pass
        self._oex.clicked.connect(lambda: (subprocess.Popen(f'explorer /select,"{path}"') if sys.platform=="win32" else None))
        if self._sw.is_installed("ollama"):
            self._int_ollama.setVisible(True)
            try: self._int_ollama.clicked.disconnect()
            except: pass
            safe_name = m["n"].lower().replace(" ","-").replace(".","-")
            self._int_ollama.clicked.connect(lambda: self._do_ollama(path, safe_name))
        if self._sw.is_installed("lmstudio"):
            self._int_lm.setVisible(True)
            try: self._int_lm.clicked.disconnect()
            except: pass
            self._int_lm.clicked.connect(lambda: self._do_lm(path))
        toast(f"✅ {m['n']} downloaded!", t['gn'])
        # Tray notification
        if hasattr(QApplication.instance(), '_tray') and QApplication.instance()._tray:
            QApplication.instance()._tray.showMessage(APP, f"✅ {m['n']} downloaded!", QSystemTrayIcon.MessageIcon.Information, 5000)
        h = self._get_hist(); h.append({"n":m["n"],"p":path,"gb":m.get("gb","?"),"t":time.strftime("%Y-%m-%d %H:%M")}); self._save_hist(h); self._load_hist()
        UpdateTrackerPage.register_download(m["n"], m.get("repo",""))

    def _on_q_error(self, m, err):
        t = T(); self._dp.setVisible(False); self._cb.setVisible(False)
        self._dn.setText(f"❌ {m['n']} Failed"); self._ds.setText(str(err))
        toast(f"❌ Download failed: {err[:80]}", t['rd'])

    def _update_queue_display(self):
        self._queue_list.clear(); t = T()
        active = self._q.active
        if active: self._queue_list.addItem(f"⬇️ {active['n']} — downloading...")
        for i, item in enumerate(self._q.queue):
            self._queue_list.addItem(f"⏳ {item['model']['n']} — queued")
        self._queue_lbl.setText(f"<span style='font-size:14px;font-weight:bold;color:{t['ac']}'>Queue ({self._q.count})</span>")

    def _do_ollama(self, path, name):
        ok, msg = self._sw.integrate_ollama(path, name); self._ds.setText(f"Ollama: {msg}")
    def _do_lm(self, path):
        ok, msg = self._sw.integrate_lmstudio(path); self._ds.setText(f"LM Studio: {msg}")
    def _cancel(self):
        if self._ollama_wk:
            self._ollama_wk.cancel()
            try: self._ollama_wk.terminate()
            except: pass
        self._q.cancel_active()
        self._dn.setText("⏹️ Cancelled"); self._dp.setVisible(False); self._cb.setVisible(False)
    def _get_hist(self):
        try: return json.loads(HIST_FILE.read_text())
        except: return []
    def _save_hist(self, h): HIST_FILE.write_text(json.dumps(h[-50:],indent=2))
    def _load_hist(self):
        self._hist.clear()
        for e in reversed(self._get_hist()):
            self._hist.addItem(f"{e.get('n','')} · {e.get('gb','')}GB · {e.get('t','')}\n{e.get('p','')}")
    def _hist_ctx(self, pos):
        """Right-click context menu on history: delete downloaded file."""
        item = self._hist.itemAt(pos)
        if not item: return
        t = T(); menu = QMenu(self)
        menu.setStyleSheet(f"QMenu{{background:{t['bg2']};color:{t['tx']};border:1px solid {t['bd']};}}QMenu::item:selected{{background:{t['ac']};color:{t['bg0']};}}")
        act_del = menu.addAction("🗑️ Delete downloaded file")
        act_open = menu.addAction("📁 Open in Explorer")
        action = menu.exec(self._hist.mapToGlobal(pos))
        idx = self._hist.row(item); h = self._get_hist(); rev_idx = len(h) - 1 - idx
        if 0 <= rev_idx < len(h):
            entry = h[rev_idx]; path = entry.get("p","")
            if action == act_del and path and Path(path).exists():
                Path(path).unlink()
                h.pop(rev_idx); self._save_hist(h); self._load_hist()
                toast(f"🗑️ Deleted {Path(path).name}", T()['og'])
            elif action == act_open and path:
                if sys.platform=="win32": subprocess.Popen(f'explorer /select,"{path}"')

    def _winget_install(self, key, pkg_id, name):
        t = T(); btn = self._install_btns.get(key)
        if btn: btn.setEnabled(False); btn.setText("Installing...")
        self._install_log.setVisible(True)
        self._install_log.setText(f"<span style='color:{t['og']}'>⏳ Installing {name} via winget...</span>")
        worker = WingetInstallWorker(pkg_id, name)
        worker.sig_line.connect(lambda line: self._install_log.setText(f"<span style='color:{t['tx2']};font-size:11px'>{html_mod.escape(line[:120])}</span>"))
        worker.sig_done.connect(lambda msg, ok: self._winget_done(key, msg, ok))
        self._install_workers[key] = worker; worker.start()
    def _winget_done(self, key, msg, ok):
        t = T(); btn = self._install_btns.get(key); info = SoftwareDetector.TOOLS.get(key, {})
        if ok:
            self._install_log.setText(f"<span style='color:{t['gn']};font-weight:bold'>✅ {html_mod.escape(msg)} installed!</span>")
            if btn: btn.setText(f"{info.get('icon','')} ✓ {info.get('name','')}"); btn.setEnabled(False)
            self._sw.found[key] = "winget"
            toast(f"✅ {info.get('name','')} installed!", t['gn'])
        else:
            self._install_log.setText(f"<span style='color:{t['rd']}'>❌ {html_mod.escape(msg)}</span>")
            if btn: btn.setEnabled(True); btn.setText(f"{info.get('icon','')} {info.get('name','')}")

class HFSearchPage(QWidget):
    sig_dl = pyqtSignal(dict)
    def __init__(self, hw):
        super().__init__(); self._hw = hw; self._worker = None; self._fw = None; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8); lo.setSpacing(10)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>🔍 HuggingFace Live Search</span>"))
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>Search 800K+ models. Results filtered to GGUF, sorted by downloads.</span>"))
        sr = QHBoxLayout(); sr.setSpacing(8)
        self._se = QLineEdit(); self._se.setPlaceholderText("Search models (e.g., 'qwen3', 'dolphin', 'coding')..."); self._se.setFixedHeight(40)
        self._se.returnPressed.connect(self._search); sr.addWidget(self._se, 1)
        self._sb = QPushButton("🔍 Search"); self._sb.setFixedHeight(40); self._sb.clicked.connect(self._search); sr.addWidget(self._sb)
        lo.addLayout(sr)
        self._status = QLabel(""); self._status.setStyleSheet(f"color:{t['tx2']};"); lo.addWidget(self._status)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._sw = QWidget(); self._sl = QVBoxLayout(self._sw); self._sl.setSpacing(6); self._sl.setContentsMargins(0,0,6,0)
        sa.setWidget(self._sw); lo.addWidget(sa, 1)
    def _search(self):
        q = self._se.text().strip()
        if not q: return
        t = T(); self._status.setText(f"<span style='color:{t['og']}'>Searching HuggingFace for '{q}'...</span>"); self._sb.setEnabled(False)
        self._worker = HFSearchWorker(q, 30); self._worker.sig_results.connect(self._show_results)
        self._worker.sig_err.connect(self._show_err); self._worker.start()
    def _show_results(self, results):
        t = T(); self._sb.setEnabled(True)
        while self._sl.count():
            it = self._sl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self._status.setText(f"<span style='color:{t['gn']}'>{len(results)} GGUF repositories found</span>")
        for r in results:
            frm = QFrame(); frm.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:12px;}}")
            fl = QVBoxLayout(frm); fl.setSpacing(4)
            r1 = QHBoxLayout()
            nm = QLabel(f"<span style='color:{t['ac']};font-size:14px;font-weight:bold'>{html_mod.escape(r['id'])}</span>")
            nm.setTextFormat(Qt.TextFormat.RichText); r1.addWidget(nm); r1.addStretch()
            r1.addWidget(QLabel(f"<span style='color:{t['tx2']};font-size:12px'>⬇ {r['downloads']:,}  ❤ {r['likes']:,}  📅 {r['last_modified']}</span>"))
            fl.addLayout(r1)
            tr = QHBoxLayout(); tr.setSpacing(4)
            for tg in r.get("tags",[])[:5]:
                lb = QLabel(tg); lb.setStyleSheet(f"background:{t['bg3']};color:{t['tx2']};padding:2px 6px;border-radius:8px;font-size:10px;"); lb.setFixedHeight(18); tr.addWidget(lb)
            tr.addStretch()
            btn = QPushButton("📂 Show Files"); btn.setFixedHeight(26); btn.setProperty("class","ghost")
            repo_id = r["id"]; btn.clicked.connect(lambda _, rid=repo_id: self._load_files(rid)); tr.addWidget(btn)
            hf_btn = QPushButton("🌐 Open"); hf_btn.setFixedHeight(26); hf_btn.setProperty("class","ghost")
            hf_btn.clicked.connect(lambda _, rid=repo_id: QDesktopServices.openUrl(QUrl(f"https://huggingface.co/{rid}"))); tr.addWidget(hf_btn)
            fl.addLayout(tr)
            files_w = QWidget(); files_w.setVisible(False)
            files_lo = QVBoxLayout(files_w); files_lo.setContentsMargins(12,4,0,0); files_lo.setSpacing(2)
            frm._files_w = files_w; frm._files_lo = files_lo; frm._repo = r["id"]
            fl.addWidget(files_w); self._sl.addWidget(frm)
        self._sl.addStretch()
    def _load_files(self, repo_id):
        for i in range(self._sl.count()):
            w = self._sl.itemAt(i).widget()
            if w and hasattr(w, '_repo') and w._repo == repo_id:
                if w._files_w.isVisible(): w._files_w.setVisible(False); return
                self._fw = HFFilesWorker(repo_id); self._fw.sig_files.connect(lambda rid, files: self._show_files(rid, files))
                self._fw.sig_err.connect(self._show_err); self._fw.start(); return
    def _show_files(self, repo_id, files):
        t = T()
        for i in range(self._sl.count()):
            w = self._sl.itemAt(i).widget()
            if w and hasattr(w, '_repo') and w._repo == repo_id:
                while w._files_lo.count():
                    it = w._files_lo.takeAt(0)
                    if it.widget(): it.widget().deleteLater()
                if not files: w._files_lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>No .gguf files found</span>"))
                else:
                    for f in files:
                        fr = QHBoxLayout(); ql = f["quant"]
                        qc = t['gn'] if ql in ("Q4_K_M","Q5_K_M","Q6_K") else t['og'] if "Q3" in ql or "Q4" in ql else t['tx2']
                        sz_str = f" ({f['size']/(1024**3):.1f} GB)" if f.get('size') else ""
                        fr.addWidget(QLabel(f"<span style='color:{qc};font-weight:bold;font-size:11px'>{ql}</span> "
                            f"<span style='color:{t['tx2']};font-size:11px'>{html_mod.escape(f['name'])}{sz_str}</span>"))
                        fr.addStretch()
                        db = QPushButton("⬇"); db.setFixedSize(30, 22)
                        db.setStyleSheet(f"QPushButton{{background:{t['gn']};color:{t['bg0']};font-size:10px;border-radius:4px;font-weight:bold;padding:0;}}")
                        fn = f["name"]; rid = repo_id
                        db.clicked.connect(lambda _, r=rid, ff=fn: self.sig_dl.emit({"n":ff.split("/")[-1].replace(".gguf",""),"repo":r,"file":ff,"gb":0,"q":"","p":"","ctx":"","sc":0,"cat":"","lic":"","d":"HF download","tags":[]}))
                        fr.addWidget(db); rw = QWidget(); rw.setLayout(fr); w._files_lo.addWidget(rw)
                w._files_w.setVisible(True); return
    def _show_err(self, e):
        t = T(); self._sb.setEnabled(True); self._status.setText(f"<span style='color:{t['rd']}'>Error: {html_mod.escape(str(e)[:200])}</span>")

class BenchmarkPage(QWidget):
    def __init__(self, hw, sw):
        super().__init__(); self._hw = hw; self._sw = sw; self._worker = None; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(20,16,20,12); lo.setSpacing(12)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>⚡ Benchmark</span>"))
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>Measure actual tok/s on YOUR hardware. Requires Ollama running.</span>"))
        self._ollama_status = QLabel(); lo.addWidget(self._ollama_status); self._check_ollama()
        mr = QHBoxLayout()
        mr.addWidget(QLabel("Ollama model:"))
        self._model = QLineEdit(); self._model.setPlaceholderText("e.g., qwen3:8b, deepseek-r1:14b"); self._model.setFixedHeight(38); mr.addWidget(self._model, 1)
        self._run_btn = QPushButton("⚡ Run Benchmark"); self._run_btn.setFixedHeight(38)
        self._run_btn.setStyleSheet(f"QPushButton{{background:{t['gn']};color:{t['bg0']};font-weight:bold;border-radius:8px;}}QPushButton:hover{{background:{t['tl']};}}")
        self._run_btn.clicked.connect(self._run); mr.addWidget(self._run_btn)
        chk = QPushButton("🔄 Refresh"); chk.setProperty("class","ghost"); chk.setFixedHeight(38)
        chk.clicked.connect(self._check_ollama); mr.addWidget(chk)
        lo.addLayout(mr)
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']};font-size:12px'>Test prompt (~200 tokens):</span>"))
        self._prompt = QLineEdit("Write a detailed comparison of Python and JavaScript covering syntax, performance, and use cases.")
        self._prompt.setFixedHeight(36); lo.addWidget(self._prompt)
        # Result
        self._result_frame = QFrame(); self._result_frame.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:16px;}}")
        rfl = QVBoxLayout(self._result_frame)
        self._result_lbl = QLabel("Run a benchmark to see results."); self._result_lbl.setWordWrap(True)
        self._result_lbl.setTextFormat(Qt.TextFormat.RichText); rfl.addWidget(self._result_lbl)
        lo.addWidget(self._result_frame)
        # Chart + History side by side
        lo.addWidget(QLabel(f"<span style='font-size:14px;font-weight:bold;color:{t['ac']}'>Benchmark History</span>"))
        split = QHBoxLayout()
        # Chart
        self._chart = BenchChart([]); split.addWidget(self._chart, 1)
        # Table
        self._hist_tbl = QTableWidget(0, 5)
        self._hist_tbl.setHorizontalHeaderLabels(["Model","tok/s","TTFT","Tokens","Date"])
        self._hist_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._hist_tbl.verticalHeader().setVisible(False); self._hist_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_tbl.setMaximumHeight(200); split.addWidget(self._hist_tbl, 1)
        lo.addLayout(split); lo.addStretch(); self._load_hist()

    def _check_ollama(self):
        t = T()
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.ok:
                data = resp.json(); models = [m["name"] for m in data.get("models",[])]
                if models:
                    self._ollama_status.setText(f"<span style='color:{t['gn']}'>✓ Ollama running. Models: {', '.join(models[:5])}</span>")
                    if not self._model.text(): self._model.setText(models[0])
                else: self._ollama_status.setText(f"<span style='color:{t['og']}'>⚠ Ollama running but no models. Run: ollama pull qwen3:8b</span>")
            else: self._ollama_status.setText(f"<span style='color:{t['rd']}'>✗ Ollama not responding</span>")
        except: self._ollama_status.setText(f"<span style='color:{t['rd']}'>✗ Ollama not running. Start with: ollama serve</span>")

    def _run(self):
        t = T(); model = self._model.text().strip()
        if not model: return
        self._run_btn.setEnabled(False); self._run_btn.setText("Running...")
        self._result_lbl.setText(f"<span style='color:{t['og']}'>⏳ Benchmarking {html_mod.escape(model)}... 10-30 seconds.</span>")
        self._worker = BenchWorker(model, "ollama", self._prompt.text())
        self._worker.sig_done.connect(self._on_done); self._worker.sig_err.connect(self._on_err); self._worker.start()

    def _on_done(self, r):
        t = T(); self._run_btn.setEnabled(True); self._run_btn.setText("⚡ Run Benchmark")
        toks = r["tok_s"]; lbl, clr = self._hw.speed_label(toks)
        self._result_lbl.setText(
            f"<div style='text-align:center;margin:8px 0'>"
            f"<span style='font-size:36px;font-weight:bold;color:{t[clr]}'>{toks} tok/s</span><br>"
            f"<span style='font-size:16px;color:{t[clr]}'>{lbl}</span></div>"
            f"<table style='width:100%'>"
            f"<tr><td style='color:{t['tx2']}'>Model</td><td style='font-weight:bold'>{html_mod.escape(r['model'])}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>Tokens</td><td>{r['tokens']}</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>TTFT</td><td>{r['ttft']}s</td></tr>"
            f"<tr><td style='color:{t['tx2']}'>Total</td><td>{r['elapsed']}s</td></tr></table>")
        h = self._get_hist()
        h.append({"model":r["model"],"tok_s":toks,"ttft":r["ttft"],"tokens":r["tokens"],"date":time.strftime("%Y-%m-%d %H:%M")})
        self._save_hist(h); self._load_hist()
        toast(f"⚡ {r['model']}: {toks} tok/s ({lbl})", t[clr])

    def _on_err(self, e):
        t = T(); self._run_btn.setEnabled(True); self._run_btn.setText("⚡ Run Benchmark")
        self._result_lbl.setText(f"<span style='color:{t['rd']}'>❌ {html_mod.escape(str(e)[:300])}</span>")
    def _bench_file(self): return CFG_DIR / "benchmarks.json"
    def _get_hist(self):
        try: return json.loads(self._bench_file().read_text())
        except: return []
    def _save_hist(self, h): self._bench_file().write_text(json.dumps(h[-30:], indent=2))
    def _load_hist(self):
        t = T(); h = self._get_hist()
        self._hist_tbl.setRowCount(len(h))
        for i, e in enumerate(reversed(h)):
            toks = e.get("tok_s", 0); _, clr = self._hw.speed_label(toks)
            self._hist_tbl.setItem(i, 0, QTableWidgetItem(e.get("model","")))
            ti = QTableWidgetItem(f"{toks}"); ti.setForeground(QColor(t[clr])); self._hist_tbl.setItem(i, 1, ti)
            self._hist_tbl.setItem(i, 2, QTableWidgetItem(f"{e.get('ttft',0)}s"))
            self._hist_tbl.setItem(i, 3, QTableWidgetItem(str(e.get("tokens",0))))
            self._hist_tbl.setItem(i, 4, QTableWidgetItem(e.get("date","")))
        # Update chart
        chart_data = [{"model": e.get("model",""), "tok_s": e.get("tok_s",0)} for e in h[-8:]]
        lo = self._chart.parent().layout() if self._chart.parent() else None
        old_chart = self._chart
        self._chart = BenchChart(chart_data)
        if lo:
            for i in range(lo.count()):
                if lo.itemAt(i).widget() == old_chart:
                    lo.replaceWidget(old_chart, self._chart); old_chart.deleteLater(); break

# ═══════════════════════════════════════════════════════════════════════════════
# PRESETS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
BUILTIN_PRESETS = {
    "🟢 Beginner Chat Pack": {"desc":"Start chatting in minutes. Small, fast models for any hardware.",
        "models":["Qwen3-8B","Phi-4-Mini","Qwen3-4B"],"software":"LM Studio or GPT4All"},
    "💻 Developer Toolkit": {"desc":"Coding-focused models for code generation and debugging.",
        "models":["Qwen3-Coder-30B-A3B","Qwen2.5-Coder-32B","Devstral-Small-24B"],"software":"Ollama"},
    "🎭 Roleplay & Creative": {"desc":"Character-driven fiction and creative writing.",
        "models":["MN-Violet-Lotus-12B","MythoMax-L2-13B","Fimbulvetr-11B-v2"],"software":"SillyTavern + KoboldCpp"},
    "🔓 Freedom Pack": {"desc":"Uncensored models with no safety filters.",
        "models":["JOSIEFIED-Qwen3-8B","Dolphin3.0-8B","Nous-Hermes-3-8B"],"software":"Any"},
    "🧠 Maximum Intelligence": {"desc":"Biggest, smartest models for 16-24GB GPUs.",
        "models":["Qwen3-235B-A22B","Qwen3-32B","DeepSeek-R1-14B"],"software":"LM Studio or Ollama"},
    "📄 Research & Analysis": {"desc":"Long context models for documents, books, codebases.",
        "models":["Qwen3-30B-A3B","Llama-4-Scout","Gemma-3-27B"],"software":"Ollama + Open WebUI with RAG"},
}

class PresetsPage(QWidget):
    sig_dl = pyqtSignal(dict)
    def __init__(self, hw):
        super().__init__(); self._hw = hw; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(20,16,20,12); lo.setSpacing(12)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>📦 Model Packs & Presets</span>"))
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>Curated bundles for specific use cases.</span>"))
        ie = QHBoxLayout()
        imp_btn = QPushButton("📥 Import Pack"); imp_btn.setProperty("class","ghost"); imp_btn.setFixedHeight(34)
        imp_btn.clicked.connect(self._import); ie.addWidget(imp_btn)
        exp_btn = QPushButton("📤 Export Custom Pack"); exp_btn.setProperty("class","ghost"); exp_btn.setFixedHeight(34)
        exp_btn.clicked.connect(self._export); ie.addWidget(exp_btn)
        ie.addStretch(); lo.addLayout(ie)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        sw = QWidget(); sl = QVBoxLayout(sw); sl.setSpacing(8); sl.setContentsMargins(0,0,6,0)
        mx = hw.max_model_gb()
        all_presets = dict(BUILTIN_PRESETS)
        try: cp = json.loads((CFG_DIR / "custom_presets.json").read_text()); all_presets.update(cp)
        except: pass
        for name, preset in all_presets.items():
            frm = QFrame(); frm.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:14px;}}")
            fl = QVBoxLayout(frm); fl.setSpacing(6)
            fl.addWidget(QLabel(f"<span style='font-size:15px;font-weight:bold;color:{t['ac']}'>{html_mod.escape(name)}</span>"))
            fl.addWidget(QLabel(f"<span style='color:{t['tx2']}'>{html_mod.escape(preset['desc'])}</span>"))
            fl.addWidget(QLabel(f"<span style='color:{t['tx2']};font-size:12px'>Software: <b>{html_mod.escape(preset['software'])}</b></span>"))
            for mn in preset["models"]:
                m = next((x for x in MODEL_DB if x["n"] == mn), None)
                if not m: fl.addWidget(QLabel(f"<span style='color:{t['tx3']}'>· {html_mod.escape(mn)} (not in database)</span>")); continue
                fits = m.get("gb",0) <= mx; toks = hw.estimate_toks(m["gb"]); spd_lbl, spd_clr = hw.speed_label(toks)
                fc = t['gn'] if fits else t['rd']; fi = "✓ Fits" if fits else "⚠ Too large"
                row = QHBoxLayout()
                row.addWidget(QLabel(f"<b>{html_mod.escape(m['n'])}</b> <span style='color:{t['tx2']}'>{m['gb']}GB · {m['p']}</span>"
                    f" <span style='color:{t[spd_clr]}'>~{toks} tok/s</span> <span style='color:{fc}'>{fi}</span>"))
                row.addStretch()
                if fits and m.get("repo"):
                    db = QPushButton("⬇"); db.setFixedSize(30,24)
                    db.setStyleSheet(f"QPushButton{{background:{t['gn']};color:{t['bg0']};font-size:11px;border-radius:4px;font-weight:bold;}}")
                    db.clicked.connect(lambda _, md=m: self.sig_dl.emit(md)); row.addWidget(db)
                rw = QWidget(); rw.setLayout(row); fl.addWidget(rw)
            sl.addWidget(frm)
        sl.addStretch(); sa.setWidget(sw); lo.addWidget(sa, 1)
    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Preset Pack", "", "JSON (*.json)")
        if not path: return
        try:
            data = json.loads(Path(path).read_text()); cp = {}
            try: cp = json.loads((CFG_DIR / "custom_presets.json").read_text())
            except: pass
            cp.update(data); (CFG_DIR / "custom_presets.json").write_text(json.dumps(cp, indent=2))
            toast(f"📥 Imported {len(data)} preset(s). Restart to see them.")
        except Exception as e: toast(f"❌ Import failed: {e}", T()['rd'])
    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Custom Pack", "my_ai_pack.json", "JSON (*.json)")
        if not path: return
        pack = {"🔧 My Custom Pack": {"desc":"Custom model collection","models":[m["n"] for m in MODEL_DB[:3]],"software":"Any"}}
        Path(path).write_text(json.dumps(pack, indent=2))
        toast(f"📤 Exported to {Path(path).name}")

# ═══════════════════════════════════════════════════════════════════════════════
# FAVORITES PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class FavoritesPage(QWidget):
    sig_dl = pyqtSignal(dict)
    def __init__(self, hw):
        super().__init__(); self._hw = hw; t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8); lo.setSpacing(10)
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>★ Favorites & Notes</span>"))
        self._cnt = QLabel(); self._cnt.setStyleSheet(f"color:{t['tx2']};"); hdr.addStretch(); hdr.addWidget(self._cnt)
        ref_btn = QPushButton("🔄 Refresh"); ref_btn.setProperty("class","ghost"); ref_btn.setFixedHeight(32)
        ref_btn.clicked.connect(self._refresh); hdr.addWidget(ref_btn)
        lo.addLayout(hdr)
        fl = QHBoxLayout(); fl.setSpacing(8)
        self._show_favs = QCheckBox("Favorites only"); self._show_favs.setChecked(True)
        self._show_favs.stateChanged.connect(self._refresh); fl.addWidget(self._show_favs)
        self._show_notes = QCheckBox("With notes"); self._show_notes.stateChanged.connect(self._refresh); fl.addWidget(self._show_notes)
        fl.addStretch()
        exp_btn = QPushButton("📤 Export"); exp_btn.setProperty("class","ghost"); exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(self._export); fl.addWidget(exp_btn)
        lo.addLayout(fl)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._sw = QWidget(); self._sl = QVBoxLayout(self._sw); self._sl.setSpacing(6); self._sl.setContentsMargins(0,0,6,0)
        sa.setWidget(self._sw); lo.addWidget(sa, 1)
        self._refresh()
    def showEvent(self, e): super().showEvent(e); self._refresh()
    def _refresh(self):
        t = T()
        while self._sl.count():
            it = self._sl.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        favs = FavoritesManager.all_favs(); notes = FavoritesManager.all_notes()
        show_f = self._show_favs.isChecked(); show_n = self._show_notes.isChecked()
        names = set()
        if show_f: names.update(favs.keys())
        if show_n: names.update(notes.keys())
        if not show_f and not show_n: names = set(favs.keys()) | set(notes.keys())
        models = sorted([m for m in MODEL_DB if m["n"] in names], key=lambda m: m["sc"], reverse=True)
        self._cnt.setText(f"{len(models)} items")
        if not models:
            self._sl.addWidget(QLabel(f"<div style='text-align:center;padding:40px;color:{t['tx2']};font-size:14px'>"
                f"No favorites yet. Click ☆ on any model card.</div>"))
        for m in models:
            note = FavoritesManager.get_note(m["n"])
            c = ModelCard(m, self._hw, show_speed=True); c.sig_dl.connect(self.sig_dl.emit)
            if note:
                wrapper = QFrame(); wrapper.setStyleSheet(f"QFrame{{background:{t['bg1']};border:1px solid {t['bd']};border-radius:10px;padding:4px;}}")
                wl = QVBoxLayout(wrapper); wl.setContentsMargins(0,0,0,4); wl.setSpacing(2)
                wl.addWidget(c)
                nl = QLabel(f"<span style='color:{t['og']};font-size:12px'>📝 {html_mod.escape(note)}</span>")
                nl.setStyleSheet(f"padding:4px 12px;"); wl.addWidget(nl)
                self._sl.addWidget(wrapper)
            else: self._sl.addWidget(c)
        self._sl.addStretch()
    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Favorites", "favorites.json", "JSON (*.json)")
        if not path: return
        data = {"favorites": list(FavoritesManager.all_favs().keys()), "notes": FavoritesManager.all_notes()}
        Path(path).write_text(json.dumps(data, indent=2))
        toast(f"📤 Exported favorites to {Path(path).name}")

# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE TRACKER PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class UpdateTrackerPage(QWidget):
    MANIFEST_FILE = CFG_DIR / "update_manifest.json"
    def __init__(self):
        super().__init__(); t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8); lo.setSpacing(10)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>🔄 Update Tracker</span>"))
        lo.addWidget(QLabel(f"<span style='color:{t['tx2']}'>Track your downloaded models and check for updates.</span>"))
        ref_btn = QPushButton("🔄 Check All"); ref_btn.setProperty("class","ghost"); ref_btn.setFixedHeight(34)
        ref_btn.clicked.connect(self._check_all); lo.addWidget(ref_btn)
        self._tbl = QTableWidget(0, 4); self._tbl.setHorizontalHeaderLabels(["Model","Repo","Downloaded","Status"])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lo.addWidget(self._tbl, 1); self._load()
    @classmethod
    def register_download(cls, name, repo):
        try: m = json.loads(cls.MANIFEST_FILE.read_text())
        except: m = {}
        m[name] = {"repo": repo, "date": time.strftime("%Y-%m-%d %H:%M"), "status": "current"}
        cls.MANIFEST_FILE.write_text(json.dumps(m, indent=2))
    def _load(self):
        t = T()
        try: m = json.loads(self.MANIFEST_FILE.read_text())
        except: m = {}
        self._tbl.setRowCount(len(m))
        for i, (name, info) in enumerate(m.items()):
            self._tbl.setItem(i, 0, QTableWidgetItem(name))
            self._tbl.setItem(i, 1, QTableWidgetItem(info.get("repo","")))
            self._tbl.setItem(i, 2, QTableWidgetItem(info.get("date","")))
            si = QTableWidgetItem(info.get("status","current")); si.setForeground(QColor(t['gn'])); self._tbl.setItem(i, 3, si)
    def _check_all(self):
        toast("🔄 Update checking — comparing against HuggingFace..."); self._load()

# ═══════════════════════════════════════════════════════════════════════════════
# SOFTWARE PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class SoftwarePage(QWidget):
    def __init__(self, sw):
        super().__init__(); t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>⚙️ Software</span>"))
        tbl = QTableWidget(); tbl.setColumnCount(6)
        tbl.setHorizontalHeaderLabels(["Tool","Type","Formats","GPU","Ease","Best For"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.verticalHeader().setVisible(False); tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        data = [("Ollama","CLI+API","GGUF","CUDA/ROCm/Vulkan","⭐⭐⭐⭐⭐","Developers"),
            ("LM Studio","GUI","GGUF/MLX","CUDA/AMD/Vulkan","⭐⭐⭐⭐⭐","Beginners"),
            ("KoboldCpp",".exe","GGUF+SD+Whisper","CUDA/Vulkan","⭐⭐⭐⭐⭐","All-in-one"),
            ("GPT4All","GUI","GGUF","CUDA/Vulkan","⭐⭐⭐⭐⭐","Non-tech"),
            ("Jan","GUI","GGUF","CUDA/Vulkan","⭐⭐⭐⭐","ChatGPT-style"),
            ("text-gen-webui","Web","All formats","CUDA/Vulkan","⭐⭐⭐⭐","Power users"),
            ("Open WebUI","Web","Via Ollama","Via backend","⭐⭐⭐⭐","Multi-user"),
            ("vLLM","API","safetensors/GPTQ","NVIDIA/AMD","⭐⭐⭐","Production"),
            ("ComfyUI","Nodes","safetensors/GGUF","NVIDIA/AMD","⭐⭐⭐","Image gen"),
            ("Fooocus","Web","SDXL","NVIDIA","⭐⭐⭐⭐⭐","Simple img"),
            ("Stability Matrix","Pkg Mgr","All","N/A","⭐⭐⭐⭐⭐","Install all"),
            ("Kokoro TTS","Lib","ONNX","CPU+GPU","⭐⭐⭐⭐","TTS"),
            ("Whisper.cpp","CLI","GGML","CPU+CUDA","⭐⭐⭐⭐","STT"),
            ("SillyTavern","Web","Via backend","Via backend","⭐⭐⭐⭐","Roleplay")]
        tbl.setRowCount(len(data))
        for i, row in enumerate(data):
            for j, v in enumerate(row):
                item = QTableWidgetItem(v)
                if j==0:
                    for k,inf in SoftwareDetector.TOOLS.items():
                        if inf["name"]==v and sw.is_installed(k):
                            ver = sw.get_version(k)
                            item.setForeground(QColor(t["gn"]))
                            item.setText(f"✓ {v}" + (f" ({ver})" if ver else ""))
                tbl.setItem(i,j,item)
            tbl.setRowHeight(i,36)
        lo.addWidget(tbl, 1)

# ═══════════════════════════════════════════════════════════════════════════════
# GLOSSARY PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class GlossaryPage(QWidget):
    def __init__(self):
        super().__init__(); t = T()
        lo = QVBoxLayout(self); lo.setContentsMargins(16,12,16,8)
        lo.addWidget(QLabel(f"<span style='font-size:18px;font-weight:bold;color:{t['ac']}'>📚 Glossary</span>"))
        self._se = QLineEdit(); self._se.setPlaceholderText("🔍 Search terms..."); self._se.setFixedHeight(36); lo.addWidget(self._se)
        self._br = QTextBrowser(); lo.addWidget(self._br, 1)
        self._terms = sorted([("GGUF","Standard single-file format for local LLMs."),("Quantization","Reducing precision (16→4 bit) to shrink size."),
            ("Q4_K_M","Community default: ~4.83 bits, ~99% quality."),("Parameters","Weights in billions. 7B=7 billion."),
            ("Context Window","Max text processed. 128K≈96K words."),("Token","~0.75 words."),("VRAM","GPU memory. Primary bottleneck."),
            ("Inference","Generating output. tok/s=speed."),("MoE","Mixture of Experts. Subset activates per token."),
            ("LoRA","Small adapter files to specialize models."),("Abliteration","Removing safety refusals from weights."),
            ("Safetensors","Secure model format. No code execution."),("GPTQ","GPU-only quantization. Fast NVIDIA."),
            ("AWQ","Better than GPTQ at 4-bit. GPU-only."),("EXL2","Fastest NVIDIA format. Arbitrary bpw."),
            ("Stable Diffusion","Open image generation family."),("Flux","SOTA open image generation."),
            ("HuggingFace","GitHub of AI. 800K+ models."),("Ollama","Docker-like CLI for LLMs."),
            ("llama.cpp","Foundation library. Defines GGUF."),("Whisper","OpenAI STT. 99 languages."),
            ("RAG","Feed documents into an LLM."),("SillyTavern","Popular RP/chat frontend."),
            ("Chatbot Arena","6M+ human votes. Trusted ranking."),("GPU Offloading","Split model between GPU+RAM."),
            ("CivitAI","Largest SD model community."),("Tokens/sec","Speed. 20+=conversational. <5=slow."),
            ("imatrix","Calibration for extreme quantization."),("Memory Bandwidth","GB/s — determines inference speed."),
            ("KV Cache","Memory storing conversation context during inference."),
        ], key=lambda x:x[0].lower())
        self._se.textChanged.connect(self._r); self._r()
    def _r(self):
        t=T(); q=self._se.text().lower(); ps=[]
        for term,d in self._terms:
            if q and q not in term.lower() and q not in d.lower(): continue
            ps.append(f"<div style='background:{t['bg2']};border:1px solid {t['bd']};border-radius:10px;padding:10px 14px;margin:5px 0;'>"
                f"<span style='color:{t['ac']};font-weight:bold;font-size:14px'>{html_mod.escape(term)}</span><br>"
                f"<span style='font-size:13px'>{html_mod.escape(d)}</span></div>")
        self._br.setHtml(_html(f"<p style='color:{t['tx2']}'>{len(ps)} terms</p>{''.join(ps)}", t))

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW — SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
class SidebarNav(QWidget):
    """Grouped sidebar navigation replacing 13 flat tabs."""
    sig_page = pyqtSignal(int)
    SECTIONS = [
        ("🏠", "Home", []),
        ("🔍", "Discover", [("🗄️ Models", 1), ("🎯 Recommend", 2), ("📦 Packs", 3), ("🔍 HuggingFace", 4)]),
        ("⬇️", "Download", [("⬇ Downloads", 5), ("★ Favorites", 6), ("🔄 Updates", 7)]),
        ("🧰", "Tools", [("📐 VRAM Calc", 8), ("⚡ Benchmark", 9), ("⚙️ Software", 10)]),
        ("📖", "Learn", [("📖 Topics", 11), ("📚 Glossary", 12)]),
    ]

    def __init__(self):
        super().__init__(); t = T()
        self.setFixedWidth(200)
        self.setStyleSheet(f"background:{t['bg1']};border-right:1px solid {t['bd']};")
        lo = QVBoxLayout(self); lo.setContentsMargins(8,14,8,8); lo.setSpacing(2)
        self._btns = []
        for icon, group, children in self.SECTIONS:
            if not children:
                # Top-level page (Home)
                btn = QPushButton(f"  {icon}  {group}"); btn.setFixedHeight(38)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(self._btn_style(t, False))
                btn.clicked.connect(lambda _, idx=0: self._select(idx))
                lo.addWidget(btn); self._btns.append((btn, 0))
            else:
                # Group header
                hdr = QLabel(f"<span style='color:{t['tx3']};font-size:11px;font-weight:bold;text-transform:uppercase'>{icon} {group}</span>")
                hdr.setStyleSheet("padding:12px 8px 4px 8px;"); lo.addWidget(hdr)
                for label, idx in children:
                    btn = QPushButton(f"  {label}"); btn.setFixedHeight(34)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setStyleSheet(self._btn_style(t, False))
                    btn.clicked.connect(lambda _, i=idx: self._select(i))
                    lo.addWidget(btn); self._btns.append((btn, idx))
        lo.addStretch()

    def _btn_style(self, t, active):
        if active:
            return f"QPushButton{{background:{t['bg2']};color:{t['ac']};border:none;border-radius:8px;text-align:left;padding:0 12px;font-weight:bold;font-size:13px;}}QPushButton:hover{{background:{t['bg3']};}}"
        return f"QPushButton{{background:transparent;color:{t['tx2']};border:none;border-radius:8px;text-align:left;padding:0 12px;font-size:13px;}}QPushButton:hover{{background:{t['bg2']};color:{t['tx']};}}"

    def _select(self, idx):
        """Called by button clicks — updates styles AND emits signal."""
        self._highlight(idx)
        self.sig_page.emit(idx)

    def _highlight(self, idx):
        """Update button styles without emitting signal."""
        t = T()
        for btn, bidx in self._btns:
            btn.setStyleSheet(self._btn_style(t, bidx == idx))

    def select(self, idx):
        """External call — highlight only, no signal (avoids recursion)."""
        self._highlight(idx)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP} v{VERSION}")
        self.setMinimumSize(1200,750); self.resize(1440,900)
        self._hw = HardwareInfo(); self._sw = SoftwareDetector()
        self._dl_queue = DownloadQueue()
        t = T(); cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        # Title bar
        tb = QWidget(); tb.setFixedHeight(52); tb.setStyleSheet(f"background:{t['bg1']};border-bottom:1px solid {t['bd']};")
        tbl = QHBoxLayout(tb); tbl.setContentsMargins(20,0,20,0)
        tbl.addWidget(QLabel("<span style='font-size:22px'>🧭</span>"))
        tbl.addWidget(QLabel(f"<span style='font-size:17px;font-weight:bold'>{APP}</span>"))
        tbl.addWidget(QLabel(f"<span style='color:{t['tx3']};font-size:11px'>v{VERSION}</span>"))
        tbl.addStretch()
        tbl.addWidget(QLabel(f"<span style='color:{t['tx2']};font-size:12px'>Theme:</span>"))
        tc = QComboBox(); tc.addItems(THEMES.keys()); tc.setCurrentText(current_theme); tc.setFixedWidth(140)
        tc.currentTextChanged.connect(self._theme); tbl.addWidget(tc)
        # HW refresh button
        hw_ref = QPushButton("🔄"); hw_ref.setFixedSize(30,30); hw_ref.setToolTip("Refresh hardware detection")
        hw_ref.setStyleSheet(f"QPushButton{{background:transparent;border:none;font-size:14px;}}QPushButton:hover{{background:{t['bg3']};border-radius:4px;}}")
        hw_ref.clicked.connect(self._refresh_hw); tbl.addWidget(hw_ref)
        vr = f"{self._hw.vram_gb}GB" if self._hw.vram_gb>0 else "CPU"
        self._hw_lbl = QLabel(f"<span style='color:{t['tx2']};font-size:12px'>{html_mod.escape(self._hw.gpu_name)} · {vr} · {self._hw.ram_gb}GB RAM</span>")
        tbl.addWidget(self._hw_lbl)
        # Export profile button
        exp_btn = QPushButton("📋"); exp_btn.setFixedSize(30,30); exp_btn.setToolTip("Copy system profile to clipboard")
        exp_btn.setStyleSheet(f"QPushButton{{background:transparent;border:none;font-size:14px;}}QPushButton:hover{{background:{t['bg3']};border-radius:4px;}}")
        exp_btn.clicked.connect(self._export_profile); tbl.addWidget(exp_btn)
        ml.addWidget(tb)
        # Body: Sidebar + Pages
        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        self._sidebar = SidebarNav(); body.addWidget(self._sidebar)
        self._stack = QStackedWidget(); body.addWidget(self._stack, 1)
        bw = QWidget(); bw.setLayout(body); ml.addWidget(bw, 1)
        # Build pages (order matches SidebarNav indices)
        self._pages = {}
        self._pages[0] = HomePage(self._hw, self._sw)
        self._pages[1] = ModelsPage(self._hw)
        self._pages[2] = RecommendPage(self._hw)
        self._pages[3] = PresetsPage(self._hw)
        self._pages[4] = HFSearchPage(self._hw)
        self._pages[5] = DownloadsPage(self._hw, self._sw, self._dl_queue)
        self._pages[6] = FavoritesPage(self._hw)
        self._pages[7] = UpdateTrackerPage()
        self._pages[8] = VRAMCalcPage(self._hw)
        self._pages[9] = BenchmarkPage(self._hw, self._sw)
        self._pages[10] = SoftwarePage(self._sw)
        self._pages[11] = LearnPage()
        self._pages[12] = GlossaryPage()
        for i in range(13):
            self._stack.addWidget(self._pages[i])
        self._sidebar.sig_page.connect(self._go_page)
        self._sidebar.select(0)
        # Connect download signals
        dt = self._pages[5]
        for idx in [1,2,3,4,6]:
            p = self._pages[idx]
            if hasattr(p, 'sig_dl'):
                p.sig_dl.connect(lambda m, d=dt: (self._go_page(5), d.start_download(m)))
        # Status bar
        sb = QWidget(); sb.setFixedHeight(26); sb.setStyleSheet(f"background:{t['bg1']};border-top:1px solid {t['bd']};")
        sbl = QHBoxLayout(sb); sbl.setContentsMargins(16,0,16,0)
        self._status_lbl = QLabel(f"<span style='color:{t['tx3']};font-size:11px'>{len(MODEL_DB)} models · {len(BUILTIN_PRESETS)} packs · HF search · Benchmarks · Favorites</span>")
        sbl.addWidget(self._status_lbl); sbl.addStretch()
        # Download queue indicator in status bar
        self._q_status = QLabel(""); self._q_status.setStyleSheet(f"color:{t['og']};font-size:11px;")
        sbl.addWidget(self._q_status)
        self._dl_queue.sig_queue_changed.connect(self._update_q_status)
        self._dl_queue.sig_finished.connect(lambda m, p: self._update_tray_dl(m))
        ml.addWidget(sb)
        # Toast parent
        ToastManager.inst().set_parent(cw)

    def _go_page(self, idx):
        self._stack.setCurrentIndex(idx)
        self._sidebar.select(idx)

    def _theme(self, n):
        global current_theme; current_theme = n
        QApplication.instance().setStyleSheet(_qss(THEMES[n]))
        cfg = _load_cfg(); cfg["theme"] = n; _save_cfg(cfg)

    def _refresh_hw(self):
        self._hw.__init__()
        t = T(); vr = f"{self._hw.vram_gb}GB" if self._hw.vram_gb>0 else "CPU"
        self._hw_lbl.setText(f"<span style='color:{t['tx2']};font-size:12px'>{html_mod.escape(self._hw.gpu_name)} · {vr} · {self._hw.ram_gb}GB RAM</span>")
        toast("🔄 Hardware refreshed!", T()['gn'])

    def _export_profile(self):
        QApplication.clipboard().setText(self._hw.export_profile())
        toast("📋 System profile copied to clipboard!")

    def _update_q_status(self):
        n = self._dl_queue.count
        if n > 0: self._q_status.setText(f"⬇ {n} download{'s' if n>1 else ''}")
        else: self._q_status.setText("")

    def _update_tray_dl(self, m):
        if hasattr(QApplication.instance(), '_tray') and QApplication.instance()._tray:
            QApplication.instance()._tray.showMessage(APP, f"✅ {m['n']} downloaded!", QSystemTrayIcon.MessageIcon.Information, 5000)
            tray = QApplication.instance()._tray
            tray.setToolTip(f"{APP} v{VERSION}")

    def closeEvent(self, event):
        if hasattr(QApplication.instance(), '_tray') and QApplication.instance()._tray:
            event.ignore(); self.hide()
            QApplication.instance()._tray.showMessage(APP, "Running in background. Downloads continue.", QSystemTrayIcon.MessageIcon.Information, 3000)
        else: event.accept()


def main():
    global current_theme
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    cfg = _load_cfg()
    if cfg.get("theme") and cfg["theme"] in THEMES: current_theme = cfg["theme"]
    app.setStyleSheet(_qss(T()))
    font = app.font(); font.setPointSize(10)
    for fam in ["Segoe UI Variable","Segoe UI","SF Pro Display"]:
        font.setFamily(fam)
        if QFontInfo(font).family().lower().startswith(fam.lower()[:6]): break
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)

    # System tray
    tray = QSystemTrayIcon()
    px = QPixmap(32, 32); px.fill(QColor(T()["ac"]))
    p = QPainter(px); p.setPen(QColor("#fff")); f = p.font(); f.setPixelSize(20); f.setBold(True); p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "🧭"); p.end()
    tray.setIcon(QIcon(px)); tray.setToolTip(f"{APP} v{VERSION}")
    tray_menu = QMenu()
    app._tray = tray

    w = MainWindow()
    tray_menu.addAction("Show", w.show)
    tray_menu.addAction("Quit", lambda: (app._tray.hide(), app.quit()))
    tray.setContextMenu(tray_menu)
    tray.activated.connect(lambda r: w.show() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()

    # First-run wizard
    if not cfg.get("wizard_done"):
        wiz = WizardDialog(w._hw, w); wiz.exec()
        cfg = _load_cfg(); cfg["show_onboarding"] = True; _save_cfg(cfg)

    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
