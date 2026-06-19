import asyncio
import os
import json
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "False").lower() == "true"

# Se não estiver no modo simulação, importa as bibliotecas BACnet
if not SIMULATION_MODE:
    from bacpypes3.ipv4.app import NormalApplication
    from bacpypes3.local.device import DeviceObject
    from bacpypes3.pdu import IPv4Address, Address
    from bacpypes3.primitivedata import ObjectIdentifier
else:
    NormalApplication = None
    DeviceObject = None
    IPv4Address = None
    Address = None
    ObjectIdentifier = None

class BACnetClient:
    def __init__(self):
        self.dms_ip = os.getenv("DMS_IP", "192.168.1.200")
        self.dnet = int(os.getenv("DNET", "9"))
        self.local_ip = os.getenv("LOCAL_IP_MASK", "192.168.1.100/24")
        self.local_device_id = int(os.getenv("LOCAL_DEVICE_ID", "99999"))
        self.local_device_name = os.getenv("LOCAL_DEVICE_NAME", "TelegramBACnetBot")
        
        self.devices = {}
        self.load_devices()
        
        self.app = None
        self.simulation_db = {}
        
        if SIMULATION_MODE:
            print("[BACnetClient] Iniciando no MODO SIMULAÇÃO (Sem conexão real).")
            self.init_simulation_db()
        else:
            print(f"[BACnetClient] Iniciando no MODO REAL conectado a {self.dms_ip}.")
            self.init_bacnet_app()

    def load_devices(self):
        """Carrega o mapeamento de evaporadoras do arquivo devices.json"""
        try:
            if os.path.exists("devices.json"):
                with open("devices.json", "r", encoding="utf-8") as f:
                    self.devices = json.load(f)
                print(f"[BACnetClient] {len(self.devices)} evaporadoras carregadas de devices.json.")
            else:
                print("[BACnetClient] AVISO: devices.json não encontrado. Use o script de geração.")
        except Exception as e:
            print(f"[BACnetClient] Erro ao carregar devices.json: {e}")

    def init_bacnet_app(self):
        """Inicializa a pilha BACnet/IP do bacpypes3"""
        try:
            local_device = DeviceObject(
                objectIdentifier=("device", self.local_device_id),
                objectName=self.local_device_name,
                vendorIdentifier=999,
            )
            local_addr = IPv4Address(self.local_ip)
            self.app = NormalApplication(local_device, local_addr)
            print(f"[BACnetClient] Pilha BACnet/IP inicializada com sucesso no IP local {self.local_ip}.")
        except Exception as e:
            print(f"[BACnetClient] FALHA crítica ao inicializar pilha BACnet: {e}")
            raise e

    def is_erv(self, device):
        """Retorna True se o dispositivo for um ERV (Energy Recovery Ventilator)"""
        return "(ERV)" in device.get("long_name", "") or str(device.get("name", "")).startswith("RE-")

    def init_simulation_db(self):
        """Inicializa um banco de dados falso para simulação offline"""
        # Para cada dispositivo em devices.json, cria um estado padrão
        for key, dev in self.devices.items():
            if self.is_erv(dev):
                self.simulation_db[key] = {
                    "power": "inactive",
                    "mode": 1,       # 1 = Auto
                    "fan_speed": 2,  # 2 = High
                    "error": 0
                }
            else:
                self.simulation_db[key] = {
                    "room_temp": 23.5,
                    "setpoint": 22.0,
                    "power": "active",  # active = ON, inactive = OFF
                    "mode": 2,          # 2 = Cool
                    "fan_speed": 4,     # 4 = High
                    "error": 0
                }
        # Se estiver vazio, adiciona um padrão
        if not self.simulation_db:
            self.simulation_db["SALA"] = {
                "room_temp": 24.2,
                "setpoint": 23.0,
                "power": "active",
                "mode": 2,
                "fan_speed": 3,
                "error": 0
            }

    def get_bacnet_address(self, excel_addr):
        """Aplica a fórmula matemática para calcular o endereço BACnet roteado através do DMS"""
        # excel_addr ex: "12.00.03" -> AA.BB.CC
        parts = list(map(int, excel_addr.split('.')))
        if len(parts) != 3:
            raise ValueError(f"Formato de endereço inválido: {excel_addr}")
        aa, bb, cc = parts
        mac_hex = f"800000{aa:02x}{bb:02x}{cc:02x}"
        return f"{self.dnet}:0x{mac_hex}@{self.dms_ip}:47808"

    def find_device(self, query):
        """Busca um dispositivo por nome, alias ou endereço de canal"""
        if not query:
            return None
        query_clean = str(query).strip().upper()
        
        # 1. Busca direta pela chave principal (geralmente nome em maiúsculo)
        if query_clean in self.devices:
            return self.devices[query_clean]
            
        # 2. Busca por alias (case-insensitive)
        for dev in self.devices.values():
            if dev.get("alias", "").upper() == query_clean:
                return dev
                
        # 3. Busca por endereço de canal (ex: 12.00.03)
        for dev in self.devices.values():
            if dev.get("address") == query_clean:
                return dev
                
        return None

    # --- MAPEAMENTO DE ENUMS PARA STRINGS ---
    
    MODES = {
        1: "Auto",
        2: "Cool (Frio)",
        3: "Heat (Quente)",
        4: "Fan (Ventilar)",
        5: "Dry (Desumidificar)"
    }
    
    FAN_SPEEDS = {
        1: "Auto",
        2: "Low (Baixo)",
        3: "Mid (Médio)",
        4: "High (Alto)",
        5: "Turbo"
    }

    ERV_MODES = {
        1: "Auto",
        2: "HeatEx (Troca Calor)",
        3: "Bypass",
        4: "Sleep"
    }

    ERV_FAN_SPEEDS = {
        1: "Low (Baixo)",
        2: "High (Alto)",
        3: "Turbo"
    }

    async def read_status(self, device):
        """Lê todos os pontos importantes de uma evaporadora ou ERV"""
        name = device["name"]
        is_erv_device = self.is_erv(device)
        
        if SIMULATION_MODE:
            await asyncio.sleep(0.2) # Simula latência de rede
            state = self.simulation_db.get(name.upper())
            if not state:
                return None
            if is_erv_device:
                return {
                    "name": device["name"],
                    "address": device["address"],
                    "is_erv": True,
                    "room_temp": "N/A",
                    "setpoint": "N/A",
                    "power": "LIGADO" if state["power"] == "active" else "DESLIGADO",
                    "mode": self.ERV_MODES.get(state["mode"], "Desconhecido"),
                    "fan_speed": self.ERV_FAN_SPEEDS.get(state["fan_speed"], "Desconhecido"),
                    "error": state["error"]
                }
            else:
                return {
                    "name": device["name"],
                    "address": device["address"],
                    "is_erv": False,
                    "room_temp": state["room_temp"],
                    "setpoint": state["setpoint"],
                    "power": "LIGADO" if state["power"] == "active" else "DESLIGADO",
                    "mode": self.MODES.get(state["mode"], "Desconhecido"),
                    "fan_speed": self.FAN_SPEEDS.get(state["fan_speed"], "Desconhecido"),
                    "error": state["error"]
                }
            
        # Modo Real via BACnet/IP
        try:
            addr_str = self.get_bacnet_address(device["address"])
            addr = Address(addr_str)
            
            if is_erv_device:
                # Pontos do ERV
                tasks = [
                    self.app.read_property(addr, ObjectIdentifier("binary-value,1"), "present-value"),      # Power
                    self.app.read_property(addr, ObjectIdentifier("multi-state-value,4"), "present-value"), # Mode
                    self.app.read_property(addr, ObjectIdentifier("multi-state-value,5"), "present-value"), # Fan Speed
                    self.app.read_property(addr, ObjectIdentifier("analog-input,7"), "present-value")      # Error Code
                ]
            else:
                # Pontos da Evaporadora (AC)
                tasks = [
                    self.app.read_property(addr, ObjectIdentifier("analog-input,1"), "present-value"),      # Room Temp
                    self.app.read_property(addr, ObjectIdentifier("analog-value,2"), "present-value"),      # Setpoint
                    self.app.read_property(addr, ObjectIdentifier("binary-value,9"), "present-value"),      # Power
                    self.app.read_property(addr, ObjectIdentifier("multi-state-value,14"), "present-value"), # Mode
                    self.app.read_property(addr, ObjectIdentifier("multi-state-value,15"), "present-value"), # Fan Speed
                    self.app.read_property(addr, ObjectIdentifier("analog-input,19"), "present-value")      # Error Code
                ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Tratamento de erros nas leituras
            processed = []
            for r in results:
                if isinstance(r, BaseException):
                    processed.append(None)
                else:
                    processed.append(r)
            
            if is_erv_device:
                power, mode, fan_speed, error = processed
                
                power_str = "DESLIGADO"
                if power is not None:
                    p_str = str(power).lower()
                    if p_str in ("active", "on", "1"):
                        power_str = "LIGADO"
                        
                mode_str = "Desconhecido"
                if mode is not None:
                    mode_str = self.ERV_MODES.get(int(mode), f"Código {mode}")
                    
                fan_str = "Desconhecido"
                if fan_speed is not None:
                    fan_str = self.ERV_FAN_SPEEDS.get(int(fan_speed), f"Código {fan_speed}")
                    
                return {
                    "name": name,
                    "address": device["address"],
                    "is_erv": True,
                    "room_temp": "N/A",
                    "setpoint": "N/A",
                    "power": power_str,
                    "mode": mode_str,
                    "fan_speed": fan_str,
                    "error": int(error) if error is not None else 0
                }
            else:
                room_temp, setpoint, power, mode, fan_speed, error = processed
                
                power_str = "DESLIGADO"
                if power is not None:
                    p_str = str(power).lower()
                    if p_str in ("active", "on", "1"):
                        power_str = "LIGADO"
                        
                mode_str = "Desconhecido"
                if mode is not None:
                    mode_str = self.MODES.get(int(mode), f"Código {mode}")
                    
                fan_str = "Desconhecido"
                if fan_speed is not None:
                    fan_str = self.FAN_SPEEDS.get(int(fan_speed), f"Código {fan_speed}")
                    
                return {
                    "name": name,
                    "address": device["address"],
                    "is_erv": False,
                    "room_temp": round(float(room_temp), 1) if room_temp is not None else "Erro",
                    "setpoint": round(float(setpoint), 1) if setpoint is not None else "Erro",
                    "power": power_str,
                    "mode": mode_str,
                    "fan_speed": fan_str,
                    "error": int(error) if error is not None else 0
                }
        except Exception as e:
            print(f"[BACnetClient] Erro ao ler status do dispositivo {name}: {e}")
            return None

    async def write_power(self, device, turn_on: bool):
        """Liga ou desliga a evaporadora (BV 9) ou ERV (BV 1)"""
        name = device["name"]
        val_bool = True if turn_on else False
        val_str = "active" if turn_on else "inactive"
        is_erv_device = self.is_erv(device)
        
        if SIMULATION_MODE:
            await asyncio.sleep(0.1)
            state = self.simulation_db.get(name.upper())
            if state:
                state["power"] = val_str
            return True
            
        try:
            addr_str = self.get_bacnet_address(device["address"])
            addr = Address(addr_str)
            obj_id_str = "binary-value,1" if is_erv_device else "binary-value,9"
            obj_id = ObjectIdentifier(obj_id_str)
            await self.app.write_property(addr, obj_id, "present-value", val_bool, priority=8)
            return True
        except Exception as e:
            print(f"[BACnetClient] Erro ao alterar Power de {name}: {e}")
            return False

    async def write_temp(self, device, setpoint: float):
        """Altera a temperatura alvo da evaporadora (AV 2). ERV não suporta."""
        name = device["name"]
        if self.is_erv(device):
            print(f"[BACnetClient] Erro: {name} é um ERV e não possui setpoint de temperatura.")
            return False
            
        if SIMULATION_MODE:
            await asyncio.sleep(0.1)
            state = self.simulation_db.get(name.upper())
            if state:
                state["setpoint"] = float(setpoint)
            return True
            
        try:
            addr_str = self.get_bacnet_address(device["address"])
            addr = Address(addr_str)
            obj_id = ObjectIdentifier("analog-value,2")
            await self.app.write_property(addr, obj_id, "present-value", float(setpoint), priority=8)
            return True
        except Exception as e:
            print(f"[BACnetClient] Erro ao alterar Setpoint de {name}: {e}")
            return False

    async def write_mode(self, device, mode_str: str):
        """Altera o modo de operação (MV 14 para AC, MV 4 para ERV)"""
        name = device["name"]
        mode_str = mode_str.lower().strip()
        is_erv_device = self.is_erv(device)
        
        if is_erv_device:
            modes_map = {
                "auto": 1,
                "heatex": 2, "troca": 2, "calor": 2,
                "bypass": 3,
                "sleep": 4
            }
            if mode_str not in modes_map:
                raise ValueError("Modo ERV inválido. Escolha entre: auto, heatex (troca), bypass ou sleep.")
            code = modes_map[mode_str]
            obj_id_str = "multi-state-value,4"
        else:
            modes_map = {
                "auto": 1,
                "cool": 2, "frio": 2,
                "heat": 3, "quente": 3,
                "fan": 4, "ventilar": 4,
                "dry": 5, "desumidificar": 5
            }
            if mode_str not in modes_map:
                raise ValueError("Modo AC inválido. Escolha entre: auto, cool (frio), heat (quente), fan (ventilar) ou dry (desumidificar).")
            code = modes_map[mode_str]
            obj_id_str = "multi-state-value,14"
        
        if SIMULATION_MODE:
            await asyncio.sleep(0.1)
            state = self.simulation_db.get(name.upper())
            if state:
                state["mode"] = code
            return True
            
        try:
            addr_str = self.get_bacnet_address(device["address"])
            addr = Address(addr_str)
            obj_id = ObjectIdentifier(obj_id_str)
            await self.app.write_property(addr, obj_id, "present-value", code, priority=8)
            return True
        except Exception as e:
            print(f"[BACnetClient] Erro ao alterar Modo de {name}: {e}")
            return False

    async def write_fan_speed(self, device, speed_str: str):
        """Altera a velocidade do ventilador (MV 15 para AC, MV 5 para ERV)"""
        name = device["name"]
        speed_str = speed_str.lower().strip()
        is_erv_device = self.is_erv(device)
        
        if is_erv_device:
            speed_map = {
                "low": 1, "baixo": 1,
                "high": 2, "alto": 2,
                "turbo": 3
            }
            if speed_str not in speed_map:
                raise ValueError("Velocidade ERV inválida. Escolha entre: low (baixo), high (alto) ou turbo.")
            code = speed_map[speed_str]
            obj_id_str = "multi-state-value,5"
        else:
            speed_map = {
                "auto": 1,
                "low": 2, "baixo": 2,
                "mid": 3, "medio": 3, "médio": 3,
                "high": 4, "alto": 4,
                "turbo": 5
            }
            if speed_str not in speed_map:
                raise ValueError("Velocidade AC inválida. Escolha entre: auto, low, mid, high ou turbo.")
            code = speed_map[speed_str]
            obj_id_str = "multi-state-value,15"
        
        if SIMULATION_MODE:
            await asyncio.sleep(0.1)
            state = self.simulation_db.get(name.upper())
            if state:
                state["fan_speed"] = code
            return True
            
        try:
            addr_str = self.get_bacnet_address(device["address"])
            addr = Address(addr_str)
            obj_id = ObjectIdentifier(obj_id_str)
            await self.app.write_property(addr, obj_id, "present-value", code, priority=8)
            return True
        except Exception as e:
            print(f"[BACnetClient] Erro ao alterar Velocidade de {name}: {e}")
            return False
