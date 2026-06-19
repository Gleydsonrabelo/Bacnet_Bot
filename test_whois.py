import asyncio
import sys
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address

async def main():
    # Define local device object
    local_device = DeviceObject(
        objectIdentifier=("device", 99999),
        objectName="TelegramBotTest",
        vendorIdentifier=999,
    )
    
    # Initialize the BACnet/IP application on our local IP
    # Local IP is 192.168.10.111, subnet mask 24
    local_addr = IPv4Address("192.168.10.111/24")
    print(f"Starting BACnet application on {local_addr}...")
    app = NormalApplication(local_device, local_addr)
    
    print("Application started. Sending Who-Is broadcast...")
    # Send broadcast Who-Is
    await app.who_is()
    
    print("Who-Is sent. Waiting 5 seconds for responses...")
    await asyncio.sleep(5)
    
    print("\n--- Inspecting DeviceInfoCache ---")
    cache = app.device_info_cache
    print("Cache class:", type(cache))
    print("Cache directory attributes:")
    for attr in dir(cache):
        if not attr.startswith("_"):
            print(f"  {attr}")
            
    # Let's try to print the internal cache dict if it exists (usually _cache or similar)
    internal_cache = None
    for attr in dir(cache):
        if attr == "cache" or attr == "_cache" or attr == "devices" or attr == "_devices":
            internal_cache = getattr(cache, attr)
            print(f"Found internal cache attribute '{attr}':", type(internal_cache))
            break
            
    if internal_cache:
        print("Internal cache size:", len(internal_cache))
        # If it's a dict, print the keys/values
        if isinstance(internal_cache, dict):
            for k, v in list(internal_cache.items())[:20]:
                print(f"  Key: {k} -> Value: {v}")
        else:
            print("Internal cache is not a dict:", internal_cache)
    else:
        print("Could not find an internal cache dictionary directly. Let's try searching for device 959203.")
        try:
            # Try getting device info for 959203
            dev_info = await cache.get_device_info(959203)
            print("Device 959203 info:", dev_info)
        except Exception as e:
            print("Failed to get device 959203 info directly:", e)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
