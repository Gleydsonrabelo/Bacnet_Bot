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
    print(f"Testing write to {target_addr_str}...")
    try:
        addr = Address(target_addr_str)
        obj_id = ObjectIdentifier("analog-value,2") # Setpoint
        
        # 1. Read current setpoint
        old_val = await app.read_property(addr, obj_id, "present-value")
        print(f"Current setpoint: {old_val} °C")
        
        # 2. Toggle value (if 23.0 -> 24.0, otherwise 23.0)
        new_val = 24.0 if float(old_val) == 23.0 else 23.0
        print(f"Writing new setpoint: {new_val} °C...")
        
        # In bacpypes3, we pass the python float directly
        await app.write_property(addr, obj_id, "present-value", new_val, priority=8)
        print("Write request sent.")
        
        # 3. Read it back
        updated_val = await app.read_property(addr, obj_id, "present-value")
        print(f"Updated setpoint: {updated_val} °C")
        
        # 4. Restore original value
        print(f"Restoring original setpoint: {old_val} °C...")
        await app.write_property(addr, obj_id, "present-value", float(old_val), priority=8)
        
        # Read back to confirm restoration
        restored_val = await app.read_property(addr, obj_id, "present-value")
        print(f"Restored setpoint: {restored_val} °C")
        
    except Exception as e:
        print(f"Failed during write test: {e}")

if __name__ == "__main__":
    asyncio.run(main())
