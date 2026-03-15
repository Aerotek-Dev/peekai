# 屏幕AI助手

一个基于 Gemini 视觉能力的桌面截图分析工具，支持多轮对话、全局快捷键和 Markdown 渲染。

## 功能

- 全局快捷键触发截图分析
- 多轮对话，保留文字上下文
- Markdown 格式渲染
- 对话日志自动保存至 `~/screen_ai_history.md`
- API Key 本地存储，首次运行时设置

## 环境要求

- Windows 10/11
- Microsoft Edge WebView2 Runtime（Windows 11 自带，Windows 10 需手动安装）

## 直接使用

前往 [Releases](../../releases) 下载最新版 `屏幕AI.exe`，双击运行即可。

首次运行会弹出设置窗口，输入 Gemini API Key 后即可使用。

## 从源码运行

1. 确保已安装 Python 3.12

2. 克隆仓库
git clone https://github.com/Aerotek-Dev/screen_ai.git
cd screen_ai
3. 创建虚拟环境
py -3.12 -m venv venv
venv\Scripts\activate
4. 安装依赖
pip install pillow keyboard google-genai pywebview
5. 运行
python screen_ai.py
## 获取 Gemini API Key

前往 https://aistudio.google.com/app/apikey 免费申请。

## WebView2 下载

如果运行报错，请先安装：
https://developer.microsoft.com/microsoft-edge/webview2/

## 许可证

MIT License
