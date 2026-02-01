import inspect
from google import genai
import asyncio

async def inspectdict():
    client = genai.Client(api_key="TEST")
    print("\n--- Help on client.aio.live.connect return type (AsyncSession) methods ---")
    
    # We need to peek at the class returned by connect... 
    # google.genai.live.AsyncSession
    try:
        from google.genai.live import AsyncSession
        print("\nHelp on AsyncSession.send_realtime_input:")
        help(AsyncSession.send_realtime_input)
        print("\nHelp on AsyncSession.send_client_content:")
        help(AsyncSession.send_client_content)
    except ImportError:
        print("Could not import AsyncSession directly. Trying via instance mockery if possible, or just generic help.")
        # fallback
        pass

if __name__ == "__main__":
    asyncio.run(inspectdict())
