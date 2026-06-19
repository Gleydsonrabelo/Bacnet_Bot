import asyncio
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address, Address
from bacpypes3.primitivedata import ObjectIdentifier

async def main():
    # Use different device ID and port 47809 to avoid conflict
    local_device = DeviceObject(
        objectIdentifier=("device", 99998),
        objectName="TelegramBotTestERV",
        vendorIdentifier=999,
    )
    # Bind to port 47809
    local_addr = IPv4Address("192.168.10.111/24", 47809)
    app = NormalApplication(local_device, local_addr)
    
    target_addr_str = "9:0x8000000f0001@192.168.10.140:47808"
    print(f"Reading ERV points from {target_addr_str} on local port 47809...")
    
    try:
        addr = Address(target_addr_str)
        
        # Read Power (binary-value, 1)
        try:
            power = await app.read_property(addr, ObjectIdentifier("binary-value,1"), "present-value")
            print(f"  Power: {power}")
        except Exception as e:
            print(f"  Power read failed: {e}")
            
        # Read Mode (multi-state-value, 4)
        try:
            mode = await app.read_property(addr, ObjectIdentifier("multi-state-value,4"), "present-value")
            print(f"  Mode: {mode}")
        except Exception as e:
            print(f"  Mode read failed: {e}")
            
        # Read Fan Speed (multi-state-value, 5)
        try:
            fan = await app.read_property(addr, ObjectIdentifier("multi-state-value,5"), "present-value")
            print(f"  Fan Speed: {fan}")
        except Exception as e:
            print(f"  Fan Speed read failed: {e}")
            
        # Read Error (analog-input, 7)
        try:
            error = await app.read_property(addr, ObjectIdentifier("analog-input,7"), "present-value")
            print(f"  Error: {error}")
        except Exception as e:
            print(f"  Error read failed: {e}")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
