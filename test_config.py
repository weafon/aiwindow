from google.genai import types
import json

def test_config():
    print("Testing config validation...")
    
    # 1. Test full config
    try:
        config_dict = {
            "response_modalities": ["AUDIO", "TEXT"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Zephyr"
                    }
                }
            }
        }
        config = types.LiveConnectConfig(**config_dict)
        print("Full config dict OK")
    except Exception as e:
        print(f"Full config dict FAIL: {e}")

    # 2. Test without Zephyr (standard voices)
    try:
        config_dict = {
            "response_modalities": ["AUDIO", "TEXT"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Puck" 
                    }
                }
            }
        }
        config = types.LiveConnectConfig(**config_dict)
        print("Standard voice (Puck) config OK")
    except Exception as e:
        print(f"Standard voice FAIL: {e}")

    # 3. Test without TEXT modality
    try:
        config_dict = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Zephyr"
                    }
                }
            }
        }
        config = types.LiveConnectConfig(**config_dict)
        print("Only AUDIO modality OK")
    except Exception as e:
        print(f"Only AUDIO FAIL: {e}")

if __name__ == "__main__":
    test_config()
