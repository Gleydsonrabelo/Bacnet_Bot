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
    print(f"Testing binary write to {target_addr_str}...")
    try:
        addr = Address(target_addr_str)
        obj_id = ObjectIdentifier("binary-value,9") # Power
        
        # 1. Read current power status
        power = await app.read_property(addr, obj_id, "present-value")
        print(f"Current power: {power}, type={type(power)}, repr={repr(power)}")
        
        # In bacpypes3, Binary values are returned as an Enumerated subclass.
        # Let's try writing the same value back.
        # We can write it as its string representation, or as a boolean, or as the raw object.
        # Let's try writing it as a string ("active" or "inactive")
        val_to_write = str(power) # "active" or "inactive"
        print(f"Writing same value back as string: '{val_to_write}'...")
        await app.write_property(addr, obj_id, "present-value", val_to_write, priority=8)
        print("Write as string succeeded!")
        
        # Also let's try to write it as an integer/boolean
        # "active" -> 1 (or True), "inactive" -> 0 (or False)
        val_bool = True if val_to_write == "active" else False
        print(f"Writing same value back as boolean: {val_bool}...")
        await app.write_property(addr, obj_id, "present-value", val_bool, priority=8)
        print("Write as boolean succeeded!")
        
    except Exception as e:
        print(f"Failed during binary write test: {e}")

if __name__ == "__main__":
    asyncio.run(main())
