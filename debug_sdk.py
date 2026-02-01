import inspect
from google import genai
import asyncio

async def inspect_sdk():
    client = genai.Client(api_key="TEST")
    # We can't easily get an AsyncSession instance without connecting, 
    # but we can look at the class in the module if we can find it.
    
    # Try to find the class
    print("Listing client.aio.live attributes:")
    print(dir(client.aio.live))
    
    # It seems client.aio.live.connect returns an async context manager.
    # Let's try to inspect what it returns.
    
    try:
        # We can't actually connect without a valid key/network, but maybe we can inspect the type hint or similar?
        pass
    except:
        pass

    # Alternative: print help
    print("\nHelp on client.aio.live.connect:")
    help(client.aio.live.connect)

if __name__ == "__main__":
    try:
        asyncio.run(inspect_sdk())
    except Exception as e:
        print(e)
