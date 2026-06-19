import asyncio
import sys
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address, Address

async def main():
    # Define local device object
    local_device = DeviceObject(
        objectIdentifier=("device", 99999),
        objectName="TelegramBotTest",
        vendorIdentifier=999,
    )
    
    local_addr = IPv4Address("192.168.10.111/24")
    print(f"Starting BACnet application on {local_addr}...")
    app = NormalApplication(local_device, local_addr)
    
    print("Application started.")
    
    # Target address for unicast Who-Is
    dms_addr = Address("192.168.10.140")
    print(f"Sending unicast Who-Is to DMS at {dms_addr}...")
    await app.who_is(address=dms_addr)
    
    print("Who-Is sent. Waiting 5 seconds for responses...")
    await asyncio.sleep(5)
    
    cache = app.device_info_cache
    print("\n--- Inspecting instance_cache ---")
    print("instance_cache type:", type(cache.instance_cache))
    
    # Try converting instance_cache to a dict or listing keys
    try:
        keys = list(cache.instance_cache.keys())
        print(f"Found {len(keys)} devices in instance_cache:")
        for k in keys[:30]:
            info = cache.instance_cache[k]
            print(f"  Device ID: {k} -> Address: {info.device_address}")
    except Exception as e:
        print("Failed to list instance_cache keys:", e)
        
    print("\n--- Inspecting address_cache ---")
    try:
        keys = list(cache.address_cache.keys())
        print(f"Found {len(keys)} entries in address_cache:")
        for k in keys[:30]:
            print(f"  Address: {k}")
    except Exception as e:
        print("Failed to list address_cache keys:", e)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
