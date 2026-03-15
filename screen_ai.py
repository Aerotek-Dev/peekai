#!/usr/bin/env python3
import threading
import time
import io
import os
import json
import sys
import base64
import tkinter as tk
from tkinter import simpledialog
from PIL import ImageGrab
from google import genai
import keyboard

# 修复 Windows 高分屏 DPI 缩放导致的截屏不全问题
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

DEFAULT_PROMPT = "描述当前屏幕内容，如果是视频/动画请说明画面情节。"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".screen_ai_config.json")
LOG_FILE = os.path.join(os.path.expanduser("~"), "screen_ai_history.md")
GEMINI_API_KEY = ""

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def capture_screen() -> bytes:
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def analyze(history: list, image_bytes: bytes, prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    contents = []
    
    # 历史记录仅保留文本上下文（控制成本）
    for role, text in history[:-1]:
        contents.append({"role": role, "parts": [{"text": text}]})
        
    contents.append({
        "role": "user",
        "parts": [
            {"inline_data": {"mime_type": "image/png",
                             "data": base64.b64encode(image_bytes).decode()}},
            {"text": prompt}
        ]
    })
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )
    return response.text

class BubbleFrame(tk.Frame):
    def __init__(self, parent, text, is_user=True, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        align = "e" if is_user else "w"
        bubble_bg = "#0078d4" if is_user else "#2d2d2d"
        fg = "#ffffff"

        label = tk.Label(
            self, text=text, bg=bubble_bg, fg=fg,
            font=("微软雅黑", 10), wraplength=260,
            justify="left", padx=10, pady=6
        )
        label.pack(anchor=align, padx=10, pady=3)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("屏幕AI")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.geometry("380x600+50+50")
        self.root.resizable(True, True)
        self.root.configure(bg="#1e1e1e")

        self.history = []
        self.config = load_config()
        self._log_lock = threading.Lock()

        self._build_ui()
        self._register_hotkey()

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#1e1e1e")
        top.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(top, text="屏幕AI", bg="#1e1e1e", fg="#ffffff",
                 font=("微软雅黑", 12, "bold")).pack(side="left")

        tk.Button(top, text="新对话", command=self.new_chat,
                  bg="#3a3a3a", fg="#ffffff", relief="flat",
                  font=("微软雅黑", 9), padx=8, cursor="hand2").pack(side="right")

        tk.Button(top, text="快捷键", command=self.set_hotkey,
                  bg="#3a3a3a", fg="#ffffff", relief="flat",
                  font=("微软雅黑", 9), padx=8, cursor="hand2").pack(side="right", padx=4)

        self.hotkey_var = tk.StringVar(value=self.config.get("hotkey", "ctrl+shift+a"))
        tk.Label(top, textvariable=self.hotkey_var,
                 bg="#1e1e1e", fg="#888888",
                 font=("微软雅黑", 9)).pack(side="right", padx=4)

        self.canvas = tk.Canvas(self.root, bg="#1e1e1e", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True, padx=(10, 0))

        self.chat_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")

        self.chat_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        bottom = tk.Frame(self.root, bg="#1e1e1e")
        bottom.pack(fill="x", padx=10, pady=8)

        self.prompt_var = tk.StringVar(value=DEFAULT_PROMPT)
        self.prompt_entry = tk.Entry(
            bottom, textvariable=self.prompt_var,
            bg="#2d2d2d", fg="#ffffff", insertbackground="white",
            relief="flat", font=("微软雅黑", 10), bd=6
        )
        self.prompt_entry.pack(fill="x", pady=(0, 4))

        self.btn = tk.Button(
            bottom, text="📷 截图并分析", command=self.trigger,
            bg="#0078d4", fg="white", activebackground="#005fa3",
            relief="flat", font=("微软雅黑", 11, "bold"),
            pady=6, cursor="hand2"
        )
        self.btn.pack(fill="x")

        self.status = tk.Label(self.root, text="就绪", bg="#1e1e1e", fg="#888888", font=("微软雅黑", 9))
        self.status.pack(pady=(0, 6))

    def _register_hotkey(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        hotkey = self.config.get("hotkey", "ctrl+shift+a")
        try:
            keyboard.add_hotkey(hotkey, self.trigger)
            self.hotkey_var.set(hotkey)
        except Exception:
            if sys.platform != "win32":
                self.hotkey_var.set("平台不支持或无Root")
                self.status.config(text="快捷键注册失败(需特权)")
            else:
                self.hotkey_var.set("热键冲突")

    def set_hotkey(self):
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        new_key = simpledialog.askstring(
            "设置快捷键", "输入新快捷键（如 ctrl+shift+a）：",
            initialvalue=self.config.get("hotkey", "ctrl+shift+a"))
        root_tmp.destroy()
        
        if new_key:
            self.config["hotkey"] = new_key
            save_config(self.config)
            self._register_hotkey()

    def new_chat(self):
        self.history.clear()
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        self.status.config(text="新对话已开始")

    def add_bubble(self, text, is_user=True):
        bubble = BubbleFrame(self.chat_frame, text, is_user=is_user)
        bubble.pack(fill="x", pady=2)
        self.root.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _append_to_log(self, prompt, response):
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with self._log_lock:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"### {timestamp}\n")
                    f.write(f"**用户:** {prompt}\n\n")
                    f.write(f"**AI:** {response}\n\n")
                    f.write("---\n\n")
        except Exception as e:
            print(f"日志保存失败: {e}")

    def trigger(self):
        if self.btn["state"] == "disabled":
            return
        
        prompt_text = self.prompt_var.get().strip() or DEFAULT_PROMPT
        
        self.btn.config(state="disabled", text="分析中...")
        self.status.config(text="截图中...")
        self.root.withdraw()
        
        threading.Thread(target=self.run, args=(prompt_text,), daemon=True).start()

    def run(self, prompt_text):
        try:
            time.sleep(0.3)
            image_bytes = capture_screen()
            
            self.root.after(0, self.root.deiconify)
            self.root.after(0, lambda: self.status.config(text="发送中..."))
            self.root.after(0, lambda: self.add_bubble(prompt_text, is_user=True))
            
            self.history.append(("user", prompt_text))
            result = analyze(self.history, image_bytes, prompt_text)
            self.history.append(("model", result))

            self.root.after(0, lambda: self.add_bubble(result, is_user=False))
            self.root.after(0, lambda: self.status.config(text="完成"))
            
            self._append_to_log(prompt_text, result)
            
        except Exception as e:
            self.root.after(0, self.root.deiconify)
            self.root.after(0, lambda: self.add_bubble(f"错误: {str(e)}", is_user=False))
            self.root.after(0, lambda: self.status.config(text="出错"))
        finally:
            self.root.after(0, lambda: self.btn.config(state="normal", text="📷 截图并分析"))

def main():
    global GEMINI_API_KEY
    config = load_config()
    key = config.get("api_key", "")

    if not key:
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        key = simpledialog.askstring("设置API Key", "请输入你的Gemini API Key：", show="*")
        root_tmp.destroy()
        if not key:
            return
        config["api_key"] = key
        save_config(config)

    GEMINI_API_KEY = key
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
