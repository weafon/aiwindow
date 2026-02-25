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
from google.genai import types
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QBuffer, QIODevice, QTimer
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
							 QLabel, QLineEdit, QScrollArea, QFrame, QPushButton)
from PyQt6.QtMultimedia import QAudioSource, QAudioSink, QMediaDevices, QAudioFormat, QAudio
import struct
import base64
import asyncio
import queue
import nest_asyncio
nest_asyncio.apply()

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

class AudioRecorder(QObject):
	audio_data_ready = pyqtSignal(bytes)

	def __init__(self):
		super().__init__()
		self.format = QAudioFormat()
		self.format.setSampleRate(16000)
		self.format.setChannelCount(1)
		self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
		
		# Auto-select best device
		target_device = QMediaDevices.defaultAudioInput()
		devices = QMediaDevices.audioInputs()
		
		print("DEBUG: Scanning Audio Devices...")
		for dev in devices:
			name = dev.description()
			print(f" - Found: {name}")
			# Prioritize USB Mic or ConferenceCam
			if "Basic" in name or "Conference" in name or "USB" in name:
				print(f"DEBUG: Switching to preferred device: {name}")
				target_device = dev
				
		if target_device.isNull():
			print("ERROR: No valid audio input found.")
		else:
			print(f"DEBUG: Using Audio Input: {target_device.description()}")

		self.source = QAudioSource(target_device, self.format)
		self.io_device = None
		self.log_timer = 0
	
	def start(self):
		print("DEBUG: Starting AudioRecorder...")
		self.io_device = self.source.start()
		if self.source.error() != QAudio.Error.NoError:
			 print(f"ERROR: AudioSource failed to start: {self.source.error()}")
		self.io_device.readyRead.connect(self.read_data)
		
	def stop(self):
		print("DEBUG: Stopping AudioRecorder...")
		self.source.stop()
		if self.io_device:
			self.io_device.readyRead.disconnect(self.read_data)
		self.io_device = None

	def read_data(self):
		if self.io_device:
			data = self.io_device.readAll()
			if data.size() > 0:
				self.log_timer += 1
#                if self.log_timer % 20 == 0: # Log every ~20 chunks (approx 2 sec)
#                    print(f"DEBUG: Audio capturing... ({data.size()} bytes)")
				self.audio_data_ready.emit(data.data())

class AudioPlayer(QObject):
	def __init__(self):
		super().__init__()
		self.format = QAudioFormat()
		self.format.setSampleRate(24000) 
		self.format.setChannelCount(1)
		self.format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
		
		info = QMediaDevices.defaultAudioOutput()
		print(f"DEBUG: Default Output Device: {info.description()}")
		if not info.isFormatSupported(self.format):
			print(f"WARNING: 24000Hz 1ch Int16 not supported. Finding nearest...")
			self.format = info.preferredFormat()
			print(f"DEBUG: Nearest format: {self.format.sampleRate()}Hz, {self.format.channelCount()}ch")
		else:
			print("DEBUG: 24000Hz format supported!")

		self.sink = QAudioSink(info, self.format)
		self.sink.setBufferSize(48000) # Internal HW buffer size
		self.io_device = self.sink.start()
		
		# Managed Jitter Buffer
		self.queue = bytearray()
		self.timer = QTimer()
		self.timer.timeout.connect(self.process_queue)
		self.timer.start(20) # Check every 20ms to push data
		
	def play(self, audio_data: bytes):
		# Accumulate incoming audio blocks
		self.queue.extend(audio_data)
		
		# Latency Capping: If the queue is too long (> 5 seconds)
		# 24000 samples * 2 bytes = 48000 bytes per second
		# 48000 * 5 = 240000 bytes
		if len(self.queue) > 240000:
			# We are falling dangerously behind. Trim the queue to 1.0s of the latest audio 
			# to stay relatively in sync without being totally broken.
			trim_size = len(self.queue) - 48000 
			self.queue = self.queue[trim_size:]
			print(f"DEBUG: Audio Latency Spike! Trimmed {trim_size} bytes to catch up.")

	def process_queue(self):
		if not self.io_device or not self.io_device.isOpen():
			return
			
		# Check how much the hardware buffer can take
		bytes_free = self.sink.bytesFree()
		if bytes_free > 4096 and len(self.queue) > 0: # Write in chunks of at least 4k if possible
			# Write as much as possible, up to what we have in queue
			to_write = min(bytes_free, len(self.queue))
			written = self.io_device.write(self.queue[:to_write])
			if written > 0:
				self.queue = self.queue[written:]
		
		# Periodic Debug
		if len(self.queue) > 0 and not hasattr(self, "_log_tick"): self._log_tick = 0
		if len(self.queue) > 0:
			self._log_tick += 1
			if self._log_tick % 100 == 0: # Every ~2 seconds of playback effort
				print(f"DEBUG: Buffer level: {len(self.queue)/48000:.2f}s")

class LiveSession(QThread):
	finished = pyqtSignal()
	text_received = pyqtSignal(str)
	audio_received = pyqtSignal(bytes)
	status_changed = pyqtSignal(str)
	on_exec_cmd = pyqtSignal(str)
	def __init__(self, current_volume=100):
		super().__init__()
		self.input_queue = queue.Queue()
		self.running = False
		self.model = "gemini-2.5-flash-native-audio-preview-12-2025"
		self.client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
		self.current_volume = current_volume

	def add_audio_input(self, data):
		self.input_queue.put(data)

	def stop(self):
		self.running = False
		
	def run(self):
		self.running = True
		asyncio.run(self.aio_run())
		self.finished.emit()

	async def aio_run(self):
		self.status_changed.emit("正在連接 Gemini Live...")
		try:
			config = {
				"response_modalities": ["AUDIO"],
				"tools": [
					{
						'function_declarations': [
							{
								'name': 'change_scene',
								'description': '切換窗景，指定搜尋關鍵字。',
								'parameters': {
									'type': 'OBJECT',
									'properties': {
										'keyword': {
											'type': 'STRING',
											'description': "搜尋關鍵字，例如 '瑞士'、'雨聲'、'爵士樂'"
										}
									},
									'required': ['keyword']
								}
							},
							{
								'name': 'direct_youtube_search',
								'description': '播放影片或聽音樂，指定搜尋關鍵字。',
								'parameters': {
									'type': 'OBJECT',
									'properties': {
										'keyword': {
											'type': 'STRING',
											'description': "搜尋關鍵字，例如 '古典吉他'、'鋼琴獨奏'、'爵士樂'"
										}
									},
									'required': ['keyword']
								}
							},
							{
								'name': 'set_volume',
								'description': '調整窗景背景音量。',
								'parameters': {
									'type': 'OBJECT',
									'properties': {
										'volume': {
											'type': 'INTEGER',
											'description': '音量大小 (0-100)'
										}
									},
									'required': ['volume']
								}
							},
							{
								'name': 'quit_talk',
								'description': '結束對話。',
								'parameters': {
									'type': 'OBJECT',
									'properties': {}
								}
							}
						]
					},
					{"google_search": {}}
				],
				"input_audio_transcription": {},
				"output_audio_transcription": {}
			}
			async with self.client.aio.live.connect(model=self.model, config=config) as session:
				self.status_changed.emit("連線成功！正在叫醒助理...")
				
				# Send initial instruction as the first turn to bypass config issues
				instruction_text = (
					"SYSTEM INSTRUCTION: 你是一位會使用工具的視窗助理。"
					"當使用者想要改變窗景,你必須回覆表示處理中,並呼叫change_scene工具切換窗景。"
					"當使用者說要聽音樂或看甚麼特定影片時,你呼叫direct_youtube_search工具,並根據使用者的描述來決定搜尋關鍵字。"
					"當使用者要求調整音量時,請呼叫set_volume工具來調整音量。"
					f"目前背景窗景的音量是 {self.current_volume}%。如果使用者說調大一點或調小一點，請根據此數值調整。"
					"當使用者要進行其他跟窗景無關的搜尋時, 例如股票或天氣時, 請直接調用google search獲取資料, 並用溫暖且具描述性語音回覆。"
					"當使用者表示沒有要進行對話了,例如沒事或掰掰等,你就呼叫quit_talk工具,結束對話。"
					"請全程使用繁體中文。\n"
					"Now, please say something like '你好, 甚麼事呢?'"
				)
				await session.send_client_content(
					turns=types.Content(
						role="user",
						parts=[types.Part(text=instruction_text)]
					),
					turn_complete=True
				)
				
				async def sender():
					buffer = b""
					while self.running:
						try:
							# Non-blocking get from queue
							try:
								data = self.input_queue.get_nowait()
								buffer += data
							except queue.Empty:
								# If queue is empty but we have meaningful leftover, send it
								if len(buffer) > 0:
									await session.send_realtime_input(audio={"data": buffer, "mime_type": "audio/pcm;rate=16000"})
									buffer = b""
								await asyncio.sleep(0.01)
								continue
							
							# Send only when we have enough data (simulating ~128ms chunk)
							# 16000 * 2 bytes * 0.128 ~ 4096 bytes
							if len(buffer) >= 4096:
								await session.send_realtime_input(audio={"data": buffer, "mime_type": "audio/pcm;rate=16000"})
								buffer = b"" # Clear buffer
								
						except Exception as e:
							print(f"Send Error: {e}")
							break
					print("DEBUG: Sender loop finished.")
				
				async def receiver():
					try:
						while self.running:
							async for response in session.receive():
								if not self.running: break
								if response.server_content:
									model_turn = response.server_content.model_turn
									if model_turn:
										for part in model_turn.parts:
											if part.text:
												# Ensure we're only emitting text that is clearly model output
												print(f"DEBUG: Received Model Text Chunks: {part.text}")
												self.text_received.emit(part.text)
											if part.inline_data:
												self.audio_received.emit(part.inline_data.data)
												continue
								#print(f"DEBUG: Received Response: {response}")
								if response.tool_call:
									f_responses = []
									for fc in response.tool_call.function_calls:
										print(f"DEBUG: Tool Call Received: {fc.name} with {fc.args}")
										if fc.name == "change_scene":
											keyword = fc.args.get("keyword")
											if keyword:
												#self.change_scene(keyword)
												self.on_exec_cmd.emit(f"change_scene:[[{keyword}]]")
												#self.emit(keyword)
										elif fc.name == "direct_youtube_search":
											keyword = fc.args.get("keyword")
											if keyword:
												#self.direct_youtube_search(keyword)
												self.on_exec_cmd.emit(f"direct_youtube_search:[[{keyword}]]")
										elif fc.name == "set_volume":
											vol = fc.args.get("volume")
											if vol is not None:
												self.current_volume = int(vol)
												#self.set_volume(self.current_volume)
												self.on_exec_cmd.emit(f"set_volume:[[{self.current_volume}]]")
										elif fc.name == "quit_talk":
											self.on_exec_cmd.emit("quit_talk")
											self.stop() # Stop the session loop
											# We can also break here, but stop() will signal both loops to end gracefully
											#break
										f_responses.append(
											types.FunctionResponse(
												name=fc.name,
												id=fc.id,
												response={"status": "success"}
											)
										)

									if f_responses:
										await session.send(
											input=types.LiveClientToolResponse(
												function_responses=f_responses
											)
										)
					except Exception as e:
						if self.running: # Only log if it wasn't a planned stop
							print(f"Receive Error: {e}")
					print("DEBUG: Receiver loop finished.")

				await asyncio.gather(sender(), receiver())
				
		except Exception as e:
			if self.running:
				self.status_changed.emit(f"連線錯誤: {e}")
				print(f"Live Session Error: {e}")
			else:
				print("DEBUG: Live session closed gracefully.")

class SearchWorker(QThread):
	finished = pyqtSignal(str) # 改回傳 URL，或者 None

	def __init__(self, keyword):
		super().__init__()
		self.keyword = keyword

	def run(self):
		print(f"DEBUG: 開始搜尋 {self.keyword} 的 YouTube 影片...")
		try:
			# 限制搜尋結果為 1 個，且加上 4K 關鍵字增加品質
			# 使用 --no-warnings 避免將警告訊息當作 ID 抓取
			cmd = ["yt-dlp", "--no-warnings", "-f", "best[height<=1080][vcodec^=avc]", f"ytsearch1:{self.keyword}", "--get-id"]
			# 不使用 stderr=subprocess.STDOUT，避免捕捉錯誤訊息
			video_id = subprocess.check_output(cmd).decode().strip()
			if video_id:
				print(f"DEBUG: 找到影片 ID: " + f"https://www.youtube.com/watch?v={video_id}")
				self.finished.emit(f"https://www.youtube.com/watch?v={video_id}")
			else:
				print(f"DEBUG: 沒有找到影片，關鍵字: {self.keyword}")
				self.finished.emit("")
		except Exception as e:
			print(f"搜尋失敗: {e}")
			self.finished.emit("")

class AIWindow(QWidget):
	def __init__(self):
		super().__init__()
		# 1. 初始化狀態與組件
		self.is_live = False
		self.is_minimized = False
		self.mpv_process = None
		
		self.recorder = AudioRecorder()
		self.player = AudioPlayer()
		self.live_session = None # Will instantiate per use
		
		# 2. 建立 UI
		self.initUI()

		# 3. 連結訊號
		# Note: live_session signals will be connected when created
		# recorder data signal will also be handled dynamically
		pass

	def initUI(self):
		# 視窗屬性：無邊框、最上層、透明背景
		self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
		self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
		
		self.root_layout = QVBoxLayout()
		self.root_layout.setContentsMargins(0, 0, 0, 0)
		self.setLayout(self.root_layout)

		# --- 1. 泡泡模式 (Minimized) ---
		self.bubble_btn = QPushButton("🎤")
		self.bubble_btn.setFixedSize(60, 60)
		self.bubble_btn.setStyleSheet("""
			QPushButton {
				background-color: rgba(0, 0, 0, 180);
				color: white;
				font-size: 30px;
				border-radius: 30px;
				border: 2px solid rgba(255, 255, 255, 120);
			}
			QPushButton:hover { background-color: rgba(0, 0, 0, 220); border: 2px solid white; }
		""")
		self.bubble_btn.clicked.connect(lambda: self.set_minimized(False))
		self.root_layout.addWidget(self.bubble_btn, alignment=Qt.AlignmentFlag.AlignCenter)

		# --- 2. 完整模式 (Full UI) ---
		self.full_ui_widget = QWidget()
		full_layout = QVBoxLayout(self.full_ui_widget)
		
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
		full_layout.addLayout(top_bar)

		# 滾動區域
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
		full_layout.addWidget(self.scroll)

		# 輸入區域
		input_layout = QHBoxLayout()
		self.input_field = QLineEdit()
		self.input_field.setPlaceholderText("對助理下指令...")
		self.input_field.setStyleSheet("""
			background-color: rgba(255, 255, 255, 210);
			border-radius: 10px; padding: 12px; font-size: 18px; color: #111;
		""")
		self.input_field.returnPressed.connect(self.handle_input)
		input_layout.addWidget(self.input_field)

		self.mic_btn = QPushButton("🎤")
		self.mic_btn.setFixedSize(50, 46)
		self.mic_btn.setStyleSheet("""
			QPushButton {
				background-color: rgba(0, 0, 0, 160);
				color: white;
				font-size: 20px;
				border-radius: 23px;
				border: 2px solid rgba(255, 255, 255, 100);
			}
			QPushButton:hover { background-color: rgba(0, 0, 0, 200); }
		""")
		self.mic_btn.clicked.connect(self.toggle_recording)
		input_layout.addWidget(self.mic_btn)
		full_layout.addLayout(input_layout)

		self.root_layout.addWidget(self.full_ui_widget)
		
		# 初始化為休眠模式
		self.set_minimized(True)

	def set_minimized(self, minimized):
		"""切換縮小/展開狀態"""
		self.is_minimized = minimized
		if minimized:
			self.full_ui_widget.hide()
			self.bubble_btn.show()
			self.setFixedSize(60, 60)
			# 如果還在語音，就關掉
			if self.is_live:
				self.toggle_recording()
		else:
			self.bubble_btn.hide()
			self.full_ui_widget.show()
			self.setFixedSize(450, 550)
			# 自動開始錄音
			if not self.is_live:
				self.toggle_recording()

	def toggle_recording(self):
		if not self.is_live:
			print("DEBUG: Starting new recording session...")
			# Start Live Session
			self.is_live = True
			self.current_response_buffer = "" # Reset buffer for new session
			self.label.setText("<i>正在準備通話...</i>")
			self.mic_btn.setStyleSheet("""
				QPushButton {
					background-color: rgba(0, 255, 0, 180);
					color: white;
					font-size: 20px;
					border-radius: 23px;
					border: 2px solid white;
				}
			""")
			
			# Prepare for fresh session instance
			if self.live_session:
				print("DEBUG: Stopping previous session...")
				self.live_session.stop()
				# DO NOT wait() here! It blocks the UI thread.
				# The thread will exit on its own once asyncio stops.

			current_vol = self.get_mpv_property("volume")
			if current_vol is None: current_vol = 100
			print(f"DEBUG: Current system volume is {current_vol}%")

			self.live_session = LiveSession(current_volume=current_vol)
#			self.live_session.text_received.connect(self.on_live_text)
			self.live_session.audio_received.connect(self.player.play)
			self.live_session.status_changed.connect(self.on_live_status)
			self.live_session.on_exec_cmd.connect(self.on_exec_cmd)

			# Reconnect recorder to the NEW session
			try:
				self.recorder.audio_data_ready.disconnect()
			except:
				pass
			self.recorder.audio_data_ready.connect(self.live_session.add_audio_input)
			
			# Use a tiny delay before starting recorder to ensure session state is ready
			self.live_session.start()
			QTimer.singleShot(100, self.recorder.start)
			
			# Pause Background Music
			self.send_mpv_command(["set_property", "pause", True])
			
		else:
			print("DEBUG: Stopping recording session...")
			# Stop Live Session
			self.is_live = False
			self.mic_btn.setStyleSheet("""
				QPushButton {
					background-color: rgba(0, 0, 0, 160);
					color: white;
					font-size: 20px;
					border-radius: 23px;
					border: 2px solid rgba(255, 255, 255, 100);
				}
			""")
			self.recorder.stop()
			if self.live_session:
				self.live_session.stop()
				# We don't necessarily block UI (wait) here unless needed, 
				# but it will be cleaned up on next start or garbage collected.
			self.label.setText("<i>通話結束</i>")
			
			# Resume Background Music
			self.send_mpv_command(["set_property", "pause", False])
			
			# 手動停止後也自動縮小
			if not self.is_minimized:
				self.set_minimized(True)

	def on_live_status(self, status):
		self.label.setText(f"<i>{status}</i>")
	def on_exec_cmd(self, cmd):
		print(f"DEBUG: Executing command from AI: {cmd}")
		if "change_scene:[[" in cmd and "]]" in cmd:
			parts = cmd.split("change_scene:[[")
			keyword = parts[1].split("]]")[0].strip() + " 4K window view"
			self.label.setText(f"{parts[0]}<br><br><b style='color:#00ff00;'>正在為您前往：{keyword}...</b>")
			QTimer.singleShot(2000, lambda: self.set_minimized(True) if self.is_live else None)
			self.search_worker = SearchWorker(keyword)
			self.search_worker.finished.connect(lambda url: self.send_to_mpv(url) if url else print("DEBUG: No URL found for keyword: " + keyword))
			self.search_worker.start()
			# Clear buffer to avoid repeated search
			self.current_response_buffer = ""
		elif "direct_youtube_search:[[" in cmd and "]]" in cmd:
			parts = cmd.split("direct_youtube_search:[[")
			keyword = parts[1].split("]]")[0].strip()
			self.label.setText(f"{parts[0]}<br><br><b style='color:#00ff00;'>正在為您尋找：{keyword}...</b>")
			QTimer.singleShot(2000, lambda: self.set_minimized(True) if self.is_live else None)
			self.search_worker = SearchWorker(keyword)
			self.search_worker.finished.connect(lambda url: self.send_to_mpv(url) if url else print("DEBUG: No URL found for keyword: " + keyword))
			self.search_worker.start()
			# Clear buffer to avoid repeated search
			self.current_response_buffer = ""
		elif "set_volume:[[" in cmd and "]]" in cmd:
			parts = cmd.split("set_volume:[[")
			vol_str = parts[1].split("]]")[0].strip()
			try:
				vol = int(vol_str)
				vol = max(0, min(100, vol))
				self.send_mpv_command(["set_property", "volume", vol])
				print(f"DEBUG: Setting volume to {vol}%")
				self.label.setText(f"{parts[0]}<br><br><b style='color:#00cbff;'>音量已調整為 {vol}%</b>")
				QTimer.singleShot(4000, lambda: self.set_minimized(True) if self.is_live else None)
			except:
				pass
			self.current_response_buffer = ""
		elif "quit_talk" in cmd:
			self.label.setText("<i>助理已結束對話，期待下次見面！</i>")
			QTimer.singleShot(2000, lambda: self.set_minimized(True) if self.is_live else None)
			if self.live_session:
				self.live_session.stop()
			if not self.is_minimized:
				self.set_minimized(True)
		else:
			print(f"DEBUG: Unrecognized command: {cmd}")
			# Here you can parse the cmd and execute corresponding actions
			# For example, if cmd is "change_scene:瑞士", you can call self.change_scene("瑞士")
	def handle_input(self):
		text = self.input_field.text().strip()
		if not text: return
		self.label.setText(f"<b>問：</b>{text}<br><br><i style='color:#ccc;'>正在為您聯繫宇宙...</i>")
		self.input_field.clear()
		
		# 文本輸入也自動展開（如果不小心縮小了）
		if self.is_minimized: self.set_minimized(False)

	def send_mpv_command(self, cmd_list):
		"""通用 MPV 指令發送"""
		try:
			json_data = json.dumps({"command": cmd_list})
			with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
				s.connect(IPC_SOCKET)
				s.sendall(json_data.encode('utf-8') + b'\n')
		except Exception as e:
			print(f"IPC Error: {e}")

	def get_mpv_property(self, property_name):
		"""獲取 MPV 屬性值"""
		try:
			json_data = json.dumps({"command": ["get_property", property_name]})
			with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
				s.connect(IPC_SOCKET)
				s.settimeout(0.5)
				s.sendall(json_data.encode('utf-8') + b'\n')
				response = s.recv(4096)
				if response:
					data = json.loads(response.decode().strip())
					return data.get("data")
		except Exception as e:
			print(f"IPC Get Property Error: {e}")
		return None

	def send_to_mpv(self, url):
		"""(Legacy wrapper) Load URL"""
		self.send_mpv_command(["stop"]) # Clear previous state
		asyncio.sleep(0.5) # Short delay to ensure MPV is ready for next command
		self.send_mpv_command(["loadfile", url, "replace"])



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
