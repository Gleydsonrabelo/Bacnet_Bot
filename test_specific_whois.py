import asyncio
import sys
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address, Address

async def main():
    local_device = DeviceObject(
        objectIdentifier=("device", 99999),
        objectName="TelegramBotTest",
        vendorIdentifier=999,
    )
    
    local_addr = IPv4Address("192.168.10.111/24")
    print(f"Starting BACnet application on {local_addr}...")
    app = NormalApplication(local_device, local_addr)
    
    print("Application started.")
    
    dms_addr = Address("192.168.10.140")
    target_device_id = 959203
    print(f"Sending unicast Who-Is for Device {target_device_id} to DMS at {dms_addr}...")
    await app.who_is(low_limit=target_device_id, high_limit=target_device_id, address=dms_addr)
    
    print("Waiting 5 seconds for responses...")
    await asyncio.sleep(5)
    
    cache = app.device_info_cache
    print("\n--- Checking cache for target device ---")
    try:
        dev_info = await cache.get_device_info(target_device_id)
        if dev_info:
            print(f"SUCCESS! Found Device {target_device_id} in cache:")
            print(f"  Address: {dev_info.device_address}")
            print(f"  Max APDU: {dev_info.max_apdu_length_accepted}")
            print(f"  Segmentation: {dev_info.segmentation_supported}")
            print(f"  Vendor ID: {dev_info.vendor_identifier}")
        else:
            print(f"Device {target_device_id} not found in cache (returned None).")
    except Exception as e:
        print(f"Error checking cache: {e}")
        
    print("\n--- Current instance_cache keys ---")
    print(list(cache.instance_cache.keys()))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
