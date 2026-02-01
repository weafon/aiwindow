import sys
import os
import signal
import json
import socket
import subprocess

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



class GeminiWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        try:
            # 讓 Gemini 變成一個聰明的「搜尋關鍵字生成器」
            prompt = f"""
            你是一個智慧窗景助理。用戶說："{self.user_text}"
            
            請執行以下步驟：
            1. 給用戶一個溫暖的回覆。
            2. 如果用戶想更換風景（不論是具體地點或僅是心情描述），請想出一個最適合的英文 YouTube 搜尋關鍵字。
            3. 在回覆最後一行加上：[[SEARCH_KEYWORD:關鍵字]]。
            
            範例：
            用戶：我想看紐約。
            回覆：沒問題，帶您去曼哈頓看看。[[SEARCH_KEYWORD:New York City 4K window view]]
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite-preview-09-2025",
                contents=prompt
            )
            self.finished.emit(response.text)
        except Exception as e:
            self.finished.emit(f"AI 連線失敗：{str(e)}")

class SearchWorker(QThread):
    finished = pyqtSignal(str) # 改回傳 URL，或者 None

    def __init__(self, keyword):
        super().__init__()
        self.keyword = keyword

    def run(self):
        print(f"DEBUG: 開始搜尋 {self.keyword}")
        try:
            # 限制搜尋結果為 1 個，且加上 4K 關鍵字增加品質
            # 使用 --no-warnings 避免將警告訊息當作 ID 抓取
            cmd = ["yt-dlp", "--no-warnings", f"ytsearch1:{self.keyword} 4K window view", "--get-id"]
            # 不使用 stderr=subprocess.STDOUT，避免捕捉錯誤訊息
            video_id = subprocess.check_output(cmd).decode().strip()
            if video_id:
                self.finished.emit(f"https://www.youtube.com/watch?v={video_id}")
            else:
                self.finished.emit("")
        except Exception as e:
            print(f"搜尋失敗: {e}")
            self.finished.emit("")

class AIWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.mpv_process = None

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

        self.label = QLabel("正在為您開啟窗戶...<br>您可以說「我想去瑞士」或「我想看雨景」。")
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
                s.sendall(json_data.encode('utf-8') + b'\n')
                
        except Exception as e:
            print(f"IPC Error: {e}")



    def on_ai_finished(self, response_text):
        if "[[SEARCH_KEYWORD:" in response_text:
            parts = response_text.split("[[SEARCH_KEYWORD:")
            clean_msg = parts[0].strip()
            keyword = parts[1].split("]]")[0].strip()
            
            self.label.setText(f"{clean_msg}<br><br><i style='color:#00ff00;'>正在為您尋找：{keyword}...</i>")
            
            # 使用 SearchWorker 在背景搜尋，避免 UI 卡住
            self.search_worker = SearchWorker(keyword)
            self.search_worker.finished.connect(lambda url: self.on_search_finished(url, clean_msg, keyword))
            self.search_worker.start()

        else:
            self.label.setText(response_text)
            
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def on_search_finished(self, video_url, Clean_msg, keyword):
        print(f"DEBUG: 搜尋結果 {video_url}")
        if video_url:
            self.send_to_mpv(video_url)
        else:
            self.label.setText(f"{Clean_msg}<br><br><b style='color:red;'>搜尋失敗，請再試一次。</b>")
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
