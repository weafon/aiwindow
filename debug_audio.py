from PyQt6.QtCore import QCoreApplication
from PyQt6.QtMultimedia import QMediaDevices, QAudioFormat
import sys

app = QCoreApplication(sys.argv)

print("--- PyQt6 Audio Device Check ---")
default_input = QMediaDevices.defaultAudioInput()
print(f"Default Input: {default_input.description()}")
if default_input.isNull():
    print("  -> IS NULL")
else:
    print(f"  -> ID: {default_input.id().data().decode()}")
    print(f"  -> Default Format: {default_input.preferredFormat() if default_input.preferredFormat() else 'None'}")

print("\nAll Inputs:")
for dev in QMediaDevices.audioInputs():
    print(f"- {dev.description()}")
    print(f"  ID: {dev.id().data().decode()}")
    try:
        if dev.isFormatSupported(QAudioFormat()):
            print("  Status: Supported")
        else:
             print("  Status: Maybe not supported default format")
    except:
        pass

print("--------------------------------")
