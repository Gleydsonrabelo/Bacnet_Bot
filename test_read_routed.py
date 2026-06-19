import asyncio
import sys
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address, Address
from bacpypes3.primitivedata import ObjectIdentifier

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
    
    # 9:0x8000000c0003@192.168.10.140:47808
    # Let's try to read Room Temperature (analog-input, 1, present-value)
    target_addr_str = "9:0x8000000c0003@192.168.10.140:47808"
    print(f"Reading room temperature from {target_addr_str}...")
    
    try:
        addr = Address(target_addr_str)
        obj_id = ObjectIdentifier("analog-input,1")
        
        value = await app.read_property(addr, obj_id, "present-value")
        print(f"SUCCESS! Room temperature: {value} °C")
    except Exception as e:
        print(f"Failed to read property: {e}")
        
    # Also let's try to read target temperature limit or other basic info from the router itself (device 990064)
    router_addr_str = "192.168.10.140"
    print(f"\nReading objectName from DMS Router itself at {router_addr_str}...")
    try:
        addr = Address(router_addr_str)
        obj_id = ObjectIdentifier("device,990064")
        value = await app.read_property(addr, obj_id, "object-name")
        print(f"SUCCESS! DMS Router name: {value}")
    except Exception as e:
        print(f"Failed to read DMS Router property: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
