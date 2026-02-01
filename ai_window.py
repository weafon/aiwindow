import sys
import os
import signal
import json
import socket

# 修復編碼問題，確保 stdout 和 stderr 使用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from google import genai
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QScrollArea, QFrame, QPushButton)

# --- 設定區 ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("錯誤：找不到環境變數 GEMINI_API_KEY2")
    sys.exit(1)
if not API_KEY.isascii():
    print("錯誤：GEMINI_API_KEY 必須是有效的 ASCII 字符串")
    sys.exit(1)

client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
IPC_SOCKET = "/tmp/mpvsocket"

# 定義風景庫，讓 Gemini 有參考依據
SCENERY_DB = {
    "京都雨天": "https://www.youtube.com/watch?v=8ELexeiaAwc",
    "瑞士雪山": "https://www.youtube.com/watch?v=B9VRvOKKwfs",
    "夏威夷海邊": "https://www.youtube.com/watch?v=4AtJV7U3DlU",
    "森林小溪": "https://www.youtube.com/watch?v=weOJaCMPvuw",
    "芬蘭極光": "https://www.youtube.com/watch?v=WL9EOfzoSsA"
}

class GeminiWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        try:
            # 建立結構化的 Prompt，確保 AI 遵循指令格式
            scenery_list = "\n".join([f"- {k}: {v}" for k, v in SCENERY_DB.items()])
            prompt = f"""
            你是一個智慧窗戶助理。用戶說："{self.user_text}"
            
            你的任務：
            1. 用溫暖且具描述性的文字回覆用戶。
            2. 如果用戶想更換風景、旅行或看不同的世界，請從下方的「風景庫」選擇一個最適合的。
            3. 若要換風景，請務必在回覆的最後一行加上：[[CHANGE_VIDEO:網址]]。
            
            風景庫：
            {scenery_list}
            
            注意：僅回傳 YouTube 原始網址，不要解析後的長網址。
            """
            
            response = client.models.generate_content(
                #model="gemini-2.0-flash-lite",
                model="gemini-2.5-flash-lite-preview-09-2025",
                contents=prompt
            )
            self.finished.emit(response.text)
        except Exception as e:
            self.finished.emit(f"AI 連線失敗：{str(e)}")

class AIWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 視窗屬性：無邊框、最上層、透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        main_layout = QVBoxLayout()

        # 頂部列：放置關閉按鈕
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(35, 35)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 80, 80, 180);
                color: white;
                font-weight: bold;
                border-radius: 17px;
                border: none;
            }
            QPushButton:hover { background-color: rgba(255, 0, 0, 220); }
        """)
        self.close_btn.clicked.connect(QApplication.quit)
        top_bar.addWidget(self.close_btn)
        main_layout.addLayout(top_bar)

        # 滾動區域文字顯示
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")

        self.label = QLabel("正在為您開啟窗戶...<br>您可以說「我想去瑞士」或「換成京都」。")
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.label.setStyleSheet("""
            color: white; font-size: 20px; 
            background-color: rgba(0, 0, 0, 160); 
            border-radius: 15px; padding: 20px;
            font-family: 'Segoe UI', 'Microsoft JhengHei';
        """)
        self.scroll.setWidget(self.label)
        main_layout.addWidget(self.scroll)

        # 輸入框
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("對助理下指令...")
        self.input_field.setStyleSheet("""
            background-color: rgba(255, 255, 255, 210);
            border-radius: 10px; padding: 12px; font-size: 18px; color: #111;
        """)
        self.input_field.returnPressed.connect(self.handle_input)
        main_layout.addWidget(self.input_field)

        self.setLayout(main_layout)
        self.setGeometry(100, 100, 450, 550)

    def handle_input(self):
        text = self.input_field.text().strip()
        if not text: return
        self.label.setText(f"<b>問：</b>{text}<br><br><i style='color:#ccc;'>正在為您聯繫宇宙...</i>")
        self.input_field.clear()
        
        self.worker = GeminiWorker(text)
        self.worker.finished.connect(self.on_ai_finished)
        self.worker.start()

    def send_to_mpv(self, url):
        """透過 Unix Domain Socket 發送 JSON 指令給 mpv"""
        try:
            # 建立指令字典
            cmd = {"command": ["loadfile", url, "replace"]}
            # 將字典轉為 JSON 字串
            json_data = json.dumps(cmd) 
            
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(IPC_SOCKET)
                # 【關鍵修改】使用 .encode('utf-8') 並確保結尾有換行符號 \n
                s.sendall(json_data.encode('utf-8') + b'\n')
                
        except Exception as e:
            print(f"IPC Error: {e}")

    def on_ai_finished(self, response_text):
        print(f"DEBUG - AI 回傳內容: {repr(response_text)}")  # repr 可以顯示隱藏字元
        # 處理 AI 回覆與指令
        
        if "[[CHANGE_VIDEO:" in response_text:
            parts = response_text.split("[[CHANGE_VIDEO:")
            clean_msg = parts[0].strip()
            video_url = parts[1].split("]]")[0].strip()
            
            self.label.setText(f"{clean_msg}<br><br><b style='color:#00ff00;'>助理：</b>正在切換至風景：{video_url}")
            self.send_to_mpv(video_url)
        else:
            self.label.setText(response_text)
            
        # 滾動到底部
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    win = AIWindow()
    win.show()
    sys.exit(app.exec())
