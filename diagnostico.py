import asyncio
import os
import sys
from dotenv import load_dotenv

# Carrega configurações
load_dotenv()

from bacnet_client import BACnetClient

async def menu_diagnostico():
    print("====================================================")
    # Mostra se está em modo simulação
    sim_mode = os.getenv("SIMULATION_MODE", "False").lower() == "true"
    mode_text = "SIMULAÇÃO" if sim_mode else "REAL"
    print(f"❄️  Diagnóstico BACnet Samsung DMS 2.5 - Modo: {mode_text}  ❄️")
    print("====================================================")
    
    try:
        client = BACnetClient()
    except Exception as e:
        print(f"\n❌ Erro crítico ao conectar no BACnet: {e}")
        return
        
    while True:
        print("\n📋 Menu de Diagnóstico:")
        print("1. Listar todas as evaporadoras configuradas (do devices.json)")
        print("2. Testar leitura de status de uma evaporadora específica")
        print("3. Testar controle de uma evaporadora (Power/Temp)")
        print("4. Testar leitura rápida das primeiras 5 evaporadoras em lote")
        print("5. Sair")
        
        opcao = input("\nEscolha uma opção (1-5): ").strip()
        
        if opcao == "1":
            if not client.devices:
                print("❌ Nenhuma evaporadora cadastrada no devices.json.")
            else:
                print(f"\nTotal: {len(client.devices)} evaporadoras.")
                for idx, (k, d) in enumerate(list(client.devices.items())[:20], 1):
                    print(f"  {idx:02d}. Nome: {d['name']} | Endereço: {d['address']} | ID: {d['device_id']}")
                if len(client.devices) > 20:
                    print(f"  ... e mais {len(client.devices) - 20} evaporadoras.")
                    
        elif opcao == "2":
            query = input("Digite o nome ou endereço da evaporadora (Ex: EV-1P-2.1 ou 12.00.03): ").strip()
            dev = client.find_device(query)
            if not dev:
                print(f"❌ Unidade '{query}' não encontrada no mapeamento.")
                continue
                
            print(f"🔍 Consultando {dev['name']} ({dev['address']})...")
            status = await client.read_status(dev)
            if status:
                print("\n✅ STATUS RETORNADO:")
                for k, v in status.items():
                    print(f"  - {k}: {v}")
            else:
                print("❌ Falha ao ler dados da unidade.")
                
        elif opcao == "3":
            query = input("Digite o nome ou endereço da evaporadora: ").strip()
            dev = client.find_device(query)
            if not dev:
                print(f"❌ Unidade '{query}' não encontrada.")
                continue
                
            print("\nO que deseja alterar?")
            print("1. Ligar")
            print("2. Desligar")
            print("3. Alterar Temperatura Target (Set-temperature)")
            sub_opt = input("Opção: ").strip()
            
            if sub_opt == "1":
                ok = await client.write_power(dev, True)
                print("✅ Comando Ligar enviado!" if ok else "❌ Falha ao enviar comando Ligar.")
            elif sub_opt == "2":
                ok = await client.write_power(dev, False)
                print("✅ Comando Desligar enviado!" if ok else "❌ Falha ao enviar comando Desligar.")
            elif sub_opt == "3":
                temp = input("Digite a temperatura alvo (Ex: 22.5): ").strip()
                try:
                    t_val = float(temp.replace(",", "."))
                    ok = await client.write_temp(dev, t_val)
                    print(f"✅ Temperatura ajustada para {t_val}°C!" if ok else "❌ Falha ao ajustar temperatura.")
                except ValueError:
                    print("❌ Temperatura inválida.")
                    
        elif opcao == "4":
            if not client.devices:
                print("❌ Nenhuma evaporadora cadastrada no devices.json.")
                continue
            first_5 = list(client.devices.values())[:5]
            print(f"\n⚡ Lendo {len(first_5)} unidades em lote...")
            tasks = [client.read_status(d) for d in first_5]
            results = await asyncio.gather(*tasks)
            for r in results:
                if r:
                    print(f"  Unidade: {r['name']} | Temp: {r['room_temp']}°C | Set: {r['setpoint']}°C | Power: {r['power']}")
                else:
                    print("  Falha na leitura de uma unidade.")
                    
        elif opcao == "5":
            print("Saindo do diagnóstico.")
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    try:
        asyncio.run(menu_diagnostico())
    except KeyboardInterrupt:
        print("\nDiagnóstico encerrado pelo usuário.")
    except Exception as e:
        print(f"\nOcorreu um erro no diagnóstico: {e}")
