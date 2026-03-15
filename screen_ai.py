#!/usr/bin/env python3
import threading
import io
import os
import json
import tkinter as tk
from tkinter import simpledialog
from PIL import ImageGrab
from google import genai
from google.genai import types

DEFAULT_PROMPT = "描述当前屏幕内容，如果是视频/动画请说明画面情节。"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".screen_ai_config.json")
GEMINI_API_KEY = ""


def load_key() -> str:
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("api_key", "")
    except:
        return ""


def save_key(key: str):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_key": key}, f)


def capture_screen() -> bytes:
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def analyze(image_bytes: bytes, prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            prompt,
        ],
    )
    return response.text


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("屏幕AI")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.geometry("380x500+50+50")
        self.root.resizable(True, True)
        self.root.configure(bg="#1e1e1e")

        self.prompt_var = tk.StringVar(value=DEFAULT_PROMPT)
        self.prompt_entry = tk.Entry(
            root, textvariable=self.prompt_var,
            bg="#2d2d2d", fg="#ffffff", insertbackground="white",
            relief="flat", font=("微软雅黑", 10), bd=6
        )
        self.prompt_entry.pack(fill="x", padx=10, pady=(10, 4))

        self.btn = tk.Button(
            root, text="📷 截图并分析",
            command=self.trigger,
            bg="#0078d4", fg="white", activebackground="#005fa3",
            relief="flat", font=("微软雅黑", 11, "bold"),
            pady=8, cursor="hand2"
        )
        self.btn.pack(fill="x", padx=10, pady=4)

        self.text = tk.Text(
            root, bg="#2d2d2d", fg="#d4d4d4",
            relief="flat", font=("微软雅黑", 10),
            wrap="word", state="disabled",
            padx=8, pady=8
        )
        self.text.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.status = tk.Label(
            root, text="就绪", bg="#1e1e1e", fg="#888888",
            font=("微软雅黑", 9)
        )
        self.status.pack(pady=(0, 6))

    def set_text(self, content):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", content)
        self.text.config(state="disabled")

    def trigger(self):
        self.btn.config(state="disabled", text="分析中...")
        self.status.config(text="截图中...")
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            image_bytes = capture_screen()
            self.root.after(0, lambda: self.status.config(
                text=f"截图完成 ({len(image_bytes)//1024}KB)，发送中..."))
            prompt = self.prompt_var.get().strip() or DEFAULT_PROMPT
            result = analyze(image_bytes, prompt)
            self.root.after(0, lambda: self.set_text(result))
            self.root.after(0, lambda: self.status.config(text="完成"))
        except Exception as e:
            self.root.after(0, lambda: self.set_text(f"错误: {e}"))
            self.root.after(0, lambda: self.status.config(text="出错"))
        finally:
            self.root.after(0, lambda: self.btn.config(
                state="normal", text="📷 截图并分析"))


def main():
    global GEMINI_API_KEY

    key = load_key()
    if not key:
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        key = simpledialog.askstring(
            "设置API Key", "请输入你的Gemini API Key：", show="*")
        root_tmp.destroy()
        if not key:
            return
        save_key(key)

    GEMINI_API_KEY = key

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()