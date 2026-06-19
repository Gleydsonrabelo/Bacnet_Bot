import asyncio
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
    app = NormalApplication(local_device, local_addr)
    
    target_addr_str = "9:0x8000000c0003@192.168.10.140:47808"
    print(f"Reading Mode and Fan Speed from {target_addr_str}...")
    try:
        addr = Address(target_addr_str)
        
        # Read Mode (multi-state-value, 14)
        mode = await app.read_property(addr, ObjectIdentifier("multi-state-value,14"), "present-value")
        print(f"Mode: raw={mode}, type={type(mode)}, str={str(mode)}, repr={repr(mode)}")
        
        # Read Fan Speed (multi-state-value, 15)
        fan = await app.read_property(addr, ObjectIdentifier("multi-state-value,15"), "present-value")
        print(f"Fan Speed: raw={fan}, type={type(fan)}, str={str(fan)}, repr={repr(fan)}")
    except Exception as e:
        print(f"Failed to read properties: {e}")

if __name__ == "__main__":
    asyncio.run(main())
