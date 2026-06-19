# DMS 2.5 BACnet <-> Telegram Integration Bot ❄️🤖

Esta solução integra o gateway **DMS 2.5** (utilizando o protocolo **BACnet/IP** sobre UDP 47808) com um **Bot do Telegram**, permitindo controlar e monitorar evaporadoras de ar condicionado remotamente de forma segura e prática.

---

## 🛠️ Requisitos de Infraestrutura e Rede

1. **Rede Local:** O servidor ou computador rodando o bot deve estar na mesma sub-rede do DMS 2.5 (Ex: Subnet `192.168.1.0/24`).
2. **Porta UDP 47808:** A comunicação BACnet/IP ocorre na porta UDP `47808`. Certifique-se de que o Firewall do Windows do computador do bot e do DMS permite tráfego nesta porta.
3. **Python 3.12+ (Recomendado 3.14+):** Instalado e configurado no PATH do Windows.
4. **Mapeamento de Dispositivos:** Um arquivo `devices.json` contendo o mapeamento de endereços das evaporadoras obtido a partir da planilha de comissionamento do DMS.

---

## ⚙️ Instalação e Configuração

### 1. Clonar ou Copiar os Arquivos
Certifique-se de que os seguintes arquivos estejam no mesmo diretório no Windows:
* `bot.py` (Script principal do Telegram)
* `bacnet_client.py` (Módulo de controle BACnet)
* `generate_devices.py` (Script gerador de banco de dados)
* `diagnostico.py` (Ferramenta de testes rápidos por terminal)
* `requirements.txt` (Lista de dependências Python)
* `.env` (Arquivo de configurações de variáveis de ambiente)
* `bacnet configuration.xlsx` (A planilha de configuração fornecida)

### 2. Gerar a Base de Evaporadoras (`devices.json`)
O mapeamento das evaporadoras é extraído automaticamente da sua planilha. Com a planilha `bacnet configuration.xlsx` na pasta, execute no terminal (PowerShell/CMD):
```powershell
python generate_devices.py
```
Isso criará o arquivo `devices.json` com todas as evaporadoras da sua instalação mapeadas de forma determinística com seus respectivos BACnet Device IDs e rotas virtuais.

### 3. Configurar Variáveis de Ambiente no `.env`
Abra o arquivo `.env` com um editor de texto (como Notepad) e ajuste as opções:

```ini
# Token do seu Bot do Telegram (obtenha conversando com o @BotFather no Telegram)
TELEGRAM_BOT_TOKEN=SEU_TOKEN_TELEGRAM_AQUI

# IDs dos usuários do Telegram autorizados a interagir com o bot (separados por vírgula)
# Obtenha seu ID enviando uma mensagem para o @userinfobot no Telegram
ALLOWED_USERS=12345678,87654321

# IP do Gateway DMS 2.5
DMS_IP=192.168.1.200

# IP local e máscara de sub-rede da placa deste computador (servidor do bot)
LOCAL_IP_MASK=192.168.1.100/24

# Rede BACnet Virtual do DMS (Padrão: 9)
DNET=9

# Identificação BACnet do próprio Bot (Padrão: 99999)
LOCAL_DEVICE_ID=99999
LOCAL_DEVICE_NAME=TelegramBACnetBot

# Modo Simulação (Defina como True para testar a lógica do Telegram offline)
SIMULATION_MODE=False
```

> [!IMPORTANT]
> **Segurança Whitelist:** Deixar a variável `ALLOWED_USERS` em branco liberará temporariamente o acesso a qualquer usuário do Telegram que conversar com o bot (modo onboarding). Defina os IDs permitidos antes de colocar em produção para evitar que usuários não autorizados controlem os aparelhos.

---

## 🧪 Teste de Conexão Rápido (Via Terminal)

Para garantir que a comunicação de rede BACnet com o DMS está funcionando 100% antes de iniciar o bot do Telegram, você pode utilizar o utilitário de diagnóstico interativo:

```powershell
python diagnostico.py
```

O menu interativo permite:
1. Listar todas as evaporadoras carregadas.
2. Ler a temperatura ambiente e estado atual de uma evaporadora específica em tempo real.
3. Testar comandos de Ligar/Desligar e setpoint de temperatura.
4. Ler as primeiras 5 unidades em lote para verificar a velocidade da rede.

---

## 🤖 Executando o Bot do Telegram

Para iniciar o bot e deixá-lo escutando os comandos do Telegram:
```powershell
python bot.py
```

### 📖 Comandos Disponíveis no Telegram

*   `/status <unidade>` - Consulta a temperatura ambiente, setpoint, energia, modo de operação e velocidade do ventilador da evaporadora.
    *   *Exemplo:* `/status EV-1P-2.1` ou `/status 12.00.03`
*   `/ligar <unidade>` - Liga a evaporadora física.
    *   *Exemplo:* `/ligar EV-1P-2.1`
*   `/desligar <unidade>` - Desliga a evaporadora física.
    *   *Exemplo:* `/desligar EV-1P-2.1`
*   `/temp <unidade> <graus>` - Define a temperatura alvo (Set Temperature) da evaporadora (faixa permitida: 16°C a 30°C).
    *   *Exemplo:* `/temp EV-1P-2.1 22.5`
*   `/modo <unidade> <modo>` - Define o modo de operação da unidade.
    *   *Modos:* `auto`, `cool` (frio), `heat` (quente), `fan` (ventilar), `dry` (desumidificar).
    *   *Exemplo:* `/modo EV-1P-2.1 cool`
*   `/vel <unidade> <velocidade>` - Define a velocidade de insuflamento do ventilador.
    *   *Velocidades:* `auto`, `low` (baixo), `mid` (médio), `high` (alto), `turbo`.
    *   *Exemplo:* `/vel EV-1P-2.1 high`
*   `/list` - Exibe uma lista com as evaporadoras cadastradas no banco de dados.
*   `/help` - Exibe a mensagem de ajuda contendo as instruções.

💡 **Busca Inteligente:** Para facilitar o uso, você pode usar tanto o **nome técnico** (`EV-1P-2.1`), quanto o **endereço do canal** (`12.00.03`) ou um **alias customizado** (que pode ser editado diretamente no arquivo `devices.json` no campo `"alias": "sala"`).

---

## 🖥️ Como rodar como Serviço do Windows (24/7 Background)

Para manter o bot rodando em background ininterruptamente mesmo após fechar o terminal ou fazer logout do Windows, escolha um dos métodos abaixo:

### Opção A: Usando o NSSM (Recomendado - Mais Confiável)
1. Faça o download do [NSSM (Non-Sucking Service Manager)](https://nssm.cc/download).
2. Extraia o executável `nssm.exe` (da pasta `win64`) para uma pasta do sistema (ex: `C:\nssm\`).
3. Abra o PowerShell ou Prompt de Comando como **Administrador** e execute:
   ```powershell
    C:\nssm\nssm.exe install "BACnetTelegramBot"
    ```
4. Na interface gráfica que se abrirá:
   * **Path:** Selecione o executável do Python (Ex: `C:\Caminho\Para\Python\python.exe` ou onde o Python estiver instalado).
   * **Startup directory:** Insira a pasta do bot (Ex: `C:\Caminho\Para\Pasta_do_bot`).
   * **Arguments:** Digite `bot.py`.
   * Clique em **Install service**.
5. Para iniciar o serviço, execute:
   ```powershell
   Start-Service "BACnetTelegramBot"
   ```

### Opção B: Agendador de Tarefas do Windows (Task Scheduler)
1. Abra o **Agendador de Tarefas** (`taskschd.msc`).
2. Clique em **Criar Tarefa Básica...** à direita.
3. Nomeie a tarefa como `BACnetTelegramBot` e clique em Avançar.
4. Em disparador, escolha **Ao iniciar o computador** e avance.
5. Em Ação, selecione **Iniciar um programa** e avance.
6. Em **Programa/script**, coloque o caminho do seu `python.exe`.
7. Em **Adicionar argumentos (opcional)**, coloque `bot.py`.
8. Em **Iniciar em (opcional)**, coloque o caminho completo da pasta do bot (`C:\Caminho\Para\Pasta_do_bot`).
9. Ao concluir, marque a caixa **Abrir a caixa de diálogo Propriedades desta tarefa...**.
10. Nas propriedades, na guia **Geral**, selecione **Executar quer o usuário esteja conectado ou não** e marque **Executar com privilégios mais altos**. Clique em OK.
