import os
import sys
import logging

# 【终极杀招】强制静音 pywebview 和 pythonnet 的底层日志，彻底屏蔽反射循环报错
logging.getLogger('pywebview').setLevel(logging.CRITICAL)

# 禁用辅助功能特性，降低底层触发概率
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-features=AccessibilityLayout'
os.environ['WEBVIEW2_DISABLE_ACCESSIBILITY'] = '1'

import webview
import threading
import time
import json
import base64
import io
import keyboard
from PIL import ImageGrab
from google import genai

# 修复 Windows 高分屏 DPI 缩放导致的截屏不全问题
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".screen_ai_config.json")
LOG_FILE = os.path.join(os.path.expanduser("~"), "screen_ai_history.md")
DEFAULT_PROMPT = "描述当前屏幕内容，如果是视频/动画请说明画面情节。"

class ScreenAIApi:
    def __init__(self):
        self.window = None
        self.config = self._load_config()
        self.history = []
        self._log_lock = threading.Lock()
        
        self.api_key = self.config.get("api_key", "")
        self.hotkey = self.config.get("hotkey", "ctrl+shift+a")
        self.client = None
        
        if self.api_key:
            self._init_client()
            
        self._register_hotkey()

    def set_window(self, window):
        self.window = window

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_FILE, "r") as f: return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"api_key": self.api_key, "hotkey": self.hotkey}, f)

    def _init_client(self):
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            print(f"API 初始化失败: {e}")

    def check_setup(self):
        return {"has_key": bool(self.api_key), "hotkey": self.hotkey}

    def save_settings(self, new_key, new_hotkey):
        self.api_key = new_key.strip()
        self.hotkey = new_hotkey.strip()
        self._save_config()
        self._init_client()
        self._register_hotkey()
        return True

    def clear_history(self):
        self.history.clear()
        return True

    def trigger_from_hotkey(self):
        if self.window:
            self.window.evaluate_js("window.startAnalysisFromHotkey()")

    def _register_hotkey(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        if self.hotkey:
            try:
                keyboard.add_hotkey(self.hotkey, self.trigger_from_hotkey)
            except Exception as e:
                print(f"热键注册失败: {e}")

    def _capture_screen(self) -> bytes:
        img = ImageGrab.grab(all_screens=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

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
            pass # 静默处理文件写入错误

    def run_analysis(self, prompt):
        if not self.client:
            return "❌ 请先点击右上角【设置】配置有效的 Gemini API Key！"
            
        try:
            if self.window:
                self.window.hide()
            time.sleep(0.3)
            
            image_bytes = self._capture_screen()
            
            if self.window:
                self.window.show()

            contents = []
            for role, text in self.history:
                contents.append({"role": role, "parts": [{"text": text}]})
                
            contents.append({
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
                    {"text": prompt}
                ]
            })

            response = self.client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=contents,
            )
            
            result = response.text
            self.history.append(("user", prompt))
            self.history.append(("model", result))
            self._append_to_log(prompt, result)
            
            return result
        except Exception as e:
            if self.window:
                self.window.show()
            return f"❌ 识别失败: {str(e)}"

# --- 现代 HTML/CSS/JS 前端 ---
HTML_UI = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --primary: #0078d4; --bg: #121212; --card: #1e1e1e; --text: #e0e0e0; }
        * { box-sizing: border-box; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui; margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        
        .header { background: rgba(30,30,30,0.8); backdrop-filter: blur(10px); padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; z-index: 10; }
        .title { font-weight: 600; font-size: 16px; color: white; display: flex; align-items: center; gap: 8px;}
        .actions { display: flex; gap: 10px; }
        .icon-btn { background: transparent; border: 1px solid #444; color: #aaa; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; transition: 0.2s;}
        .icon-btn:hover { background: #333; color: white; }

        #chat { flex: 1; overflow-y: auto; padding: 20px; scroll-behavior: smooth; }
        .bubble { margin-bottom: 20px; padding: 14px 18px; border-radius: 12px; max-width: 88%; line-height: 1.6; font-size: 14px; animation: slideUp 0.3s ease; }
        .user { background: var(--primary); color: white; margin-left: auto; border-bottom-right-radius: 4px; }
        .ai { background: var(--card); border: 1px solid #333; margin-right: auto; border-bottom-left-radius: 4px; }
        
        .ai pre { background: #000; padding: 12px; border-radius: 8px; overflow-x: auto; font-family: 'Consolas', monospace; border: 1px solid #222;}
        .ai code { font-family: 'Consolas', monospace; background: rgba(255,255,255,0.1); padding: 2px 4px; border-radius: 4px; }
        .ai p { margin: 0 0 10px 0; }
        .ai p:last-child { margin: 0; }

        .footer { padding: 15px 20px; background: #1a1a1a; display: flex; gap: 10px; border-top: 1px solid #333; }
        input { flex: 1; background: #252525; border: 1px solid #444; color: white; padding: 12px 16px; border-radius: 8px; outline: none; transition: border 0.2s;}
        input:focus { border-color: var(--primary); }
        button.primary { background: var(--primary); border: none; color: white; padding: 0 22px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: 0.2s; }
        button.primary:hover { background: #006abc; }
        button.primary:disabled { background: #444; color: #888; cursor: not-allowed; }

        #modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: none; justify-content: center; align-items: center; z-index: 100; backdrop-filter: blur(3px);}
        .modal-content { background: var(--card); padding: 25px; border-radius: 12px; width: 80%; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .modal-content h3 { margin-top: 0; color: white; margin-bottom: 20px;}
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; margin-bottom: 5px; font-size: 13px; color: #aaa; }
        .input-group input { width: 100%; box-sizing: border-box; background: #252525; border: 1px solid #444; color: white; padding: 10px; border-radius: 6px;}
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 25px;}

        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .loading { display: flex; gap: 4px; align-items: center; color: #888; font-style: italic;}
        .dot { width: 6px; height: 6px; background: #888; border-radius: 50%; animation: pulse 1.5s infinite; }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes pulse { 0%, 100% { opacity: 0.4; transform: scale(0.8);} 50% { opacity: 1; transform: scale(1.2);} }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">📷 屏幕 AI Pro</div>
        <div class="actions">
            <button class="icon-btn" onclick="clearChat()">清除对话</button>
            <button class="icon-btn" onclick="openSettings()">设置</button>
        </div>
    </div>

    <div id="chat">
        <div class="bubble ai" id="welcome-msg">正在初始化...</div>
    </div>

    <div class="footer">
        <input id="prompt" type="text" placeholder="输入指令 (默认: 描述屏幕)..." autocomplete="off">
        <button class="primary" id="btn" onclick="startAnalysis()">分析</button>
    </div>

    <div id="modal">
        <div class="modal-content">
            <h3>⚙️ 核心配置</h3>
            <div class="input-group">
                <label>Gemini API Key</label>
                <input type="password" id="api-key-input" placeholder="输入你的 API Key">
            </div>
            <div class="input-group">
                <label>全局快捷键</label>
                <input type="text" id="hotkey-input" placeholder="例如: ctrl+shift+a">
            </div>
            <div class="modal-actions">
                <button class="icon-btn" onclick="document.getElementById('modal').style.display='none'">取消</button>
                <button class="primary" onclick="saveSettings()" style="padding: 8px 20px;">保存配置</button>
            </div>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('prompt');
        const btn = document.getElementById('btn');
        let defaultPrompt = "描述当前屏幕内容，如果是视频/动画请说明画面情节。";
        let currentHotkey = "ctrl+shift+a";

        window.addEventListener('pywebviewready', async function() {
            const setup = await pywebview.api.check_setup();
            currentHotkey = setup.hotkey;
            document.getElementById('hotkey-input').value = currentHotkey;
            
            if (!setup.has_key) {
                document.getElementById('welcome-msg').innerText = "⚠️ 请先点击右上角【设置】配置 API Key。";
                openSettings();
            } else {
                document.getElementById('welcome-msg').innerHTML = `你好！按下快捷键 <code>${currentHotkey}</code> 或点击按钮，我会为你解读屏幕。`;
            }
        });

        function openSettings() {
            document.getElementById('modal').style.display = 'flex';
        }

        async function saveSettings() {
            const key = document.getElementById('api-key-input').value;
            const hk = document.getElementById('hotkey-input').value;
            if(!key && !await pywebview.api.check_setup().then(s=>s.has_key)) {
                alert("API Key 不能为空！"); return;
            }
            await pywebview.api.save_settings(key, hk);
            currentHotkey = hk;
            document.getElementById('modal').style.display = 'none';
            document.getElementById('welcome-msg').innerHTML = `配置已更新！快捷键设为 <code>${hk}</code>。`;
        }

        async function clearChat() {
            await pywebview.api.clear_history();
            chat.innerHTML = `<div class="bubble ai">历史记录已清除。开启新话题吧！</div>`;
        }

        async function typeWriter(text, element) {
            let current = "";
            for (const char of text) {
                current += char;
                element.innerHTML = marked.parse(current);
                chat.scrollTop = chat.scrollHeight;
                await new Promise(r => setTimeout(r, 8));
            }
        }

        async function startAnalysis() {
            if (btn.disabled) return;
            const val = input.value.trim() || defaultPrompt;
            
            input.value = ""; 
            btn.disabled = true; 
            btn.innerText = "截图中...";
            
            const uDiv = document.createElement('div');
            uDiv.className = 'bubble user'; uDiv.innerText = val;
            chat.appendChild(uDiv);
            
            const aiDiv = document.createElement('div');
            aiDiv.className = 'bubble ai'; 
            aiDiv.innerHTML = '<div class="loading">正在分析画面<div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
            chat.appendChild(aiDiv);
            chat.scrollTop = chat.scrollHeight;

            const result = await pywebview.api.run_analysis(val);
            
            aiDiv.innerHTML = "";
            await typeWriter(result, aiDiv);
            
            btn.disabled = false; 
            btn.innerText = "分析";
        }

        input.addEventListener('keypress', (e) => { if(e.key === 'Enter') startAnalysis(); });
        window.startAnalysisFromHotkey = () => { startAnalysis(); };
    </script>
</body>
</html>
"""

def check_webview2():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
        winreg.CloseKey(key)
        return True
    except:
        return False

def main():
    if sys.platform == "win32" and not check_webview2():
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        if messagebox.askyesno("缺少组件", 
            "需要安装 Microsoft Edge WebView2 Runtime\n是否打开下载页面？"):
            import webbrowser
            webbrowser.open("https://developer.microsoft.com/microsoft-edge/webview2/")
        root.destroy()
        sys.exit(0)
    api = ScreenAIApi()
    
    # 【改动】保留 on_top 参数，强制固定 x, y 坐标，跳过居中计算
    window = webview.create_window(
        title='屏幕 AI 助手',
        html=HTML_UI,
        js_api=api,
        width=420,
        height=680,
        x=200, 
        y=100,
        on_top=True,
        background_color='#121212'
    )
    
    api.set_window(window)
    
    # 强制指定 gui 模式
    webview.start(gui='edgechromium')

if __name__ == "__main__":
    main()
