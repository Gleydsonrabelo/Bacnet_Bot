import asyncio
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import IPv4Address, Address
from bacpypes3.primitivedata import ObjectIdentifier

def get_bacnet_address(excel_address, dms_ip="192.168.10.140", dnet=9):
    parts = list(map(int, excel_address.split('.')))
    if len(parts) != 3:
        raise ValueError("Invalid address format")
    aa, bb, cc = parts
    mac_hex = f"800000{aa:02x}{bb:02x}{cc:02x}"
    return f"{dnet}:0x{mac_hex}@{dms_ip}:47808"

async def read_unit_data(app, name, excel_addr):
    addr_str = get_bacnet_address(excel_addr)
    print(f"\n--- Reading unit {name} ({excel_addr}) via {addr_str} ---")
    try:
        addr = Address(addr_str)
        # Read Room Temp (analog-input, 1)
        room_temp = await app.read_property(addr, ObjectIdentifier("analog-input,1"), "present-value")
        # Read Setpoint Temp (analog-value, 2)
        set_temp = await app.read_property(addr, ObjectIdentifier("analog-value,2"), "present-value")
        # Read Power (binary-value, 9)
        power = await app.read_property(addr, ObjectIdentifier("binary-value,9"), "present-value")
        
        print(f"  Room Temp: {room_temp} °C")
        print(f"  Set Temp:  {set_temp} °C")
        print(f"  Power:     {power} ({'ON' if power == 1 or power == 'active' or str(power).lower() == 'on' else 'OFF'})")
    except Exception as e:
        print(f"  Failed to read: {e}")

async def main():
    local_device = DeviceObject(
        objectIdentifier=("device", 99999),
        objectName="TelegramBotTest",
        vendorIdentifier=999,
    )
    
    local_addr = IPv4Address("192.168.10.111/24")
    app = NormalApplication(local_device, local_addr)
    
    # Test units
    test_units = [
        ("EV-1P-2.1", "12.00.03"),
        ("EV-1P-2.2", "12.00.04"),
        ("EV-1P-1.1", "12.01.03"),
    ]
    
    for name, addr in test_units:
        await read_unit_data(app, name, addr)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
