#!/usr/bin/env python3
"""
screen_ai.py - 快捷键触发屏幕截图 + 视觉分析
快捷键: Ctrl+Shift+S 截图并分析
快捷键: Ctrl+Shift+Q 退出
"""

import keyboard
import base64
import io
import os
from PIL import ImageGrab
from google import genai
from google.genai import types

# ─── 配置区 ───────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_PROMPT = "描述当前屏幕内容，如果是视频/动画请说明画面情节。"
# ──────────────────────────────────────────────────────────


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


def on_trigger():
    print("\n[*] 截图中...")
    try:
        image_bytes = capture_screen()
        print(f"[*] 截图完成 ({len(image_bytes)//1024}KB)，发送给 Gemini...")
        result = analyze(image_bytes, DEFAULT_PROMPT)
        print(f"\n─── AI 回复 ───\n{result}\n───────────────")
    except Exception as e:
        print(f"[!] 错误: {e}")


def main():
    if not GEMINI_API_KEY:
        print("[!] 未设置 GEMINI_API_KEY")
        return

    print("[*] 已启动，后端: Gemini 2.0 Flash")
    print("[*] Ctrl+Shift+S 截图分析 | Ctrl+Shift+Q 退出")

    keyboard.add_hotkey("ctrl+shift+s", on_trigger)
    keyboard.wait("ctrl+shift+q")
    print("[*] 退出")


if __name__ == "__main__":
    main()