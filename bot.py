import asyncio
import os
import sys
import logging
import json
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatAction
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

# Importa o cliente BACnet
from bacnet_client import BACnetClient

# Configuração de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurações do Bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [
    int(x.strip())
    for x in os.getenv("ALLOWED_USERS", "").split(",")
    if x.strip().isdigit()
]
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "MinhaSenhaSuperSegura123")
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "False").lower() == "true"

# Usuários autorizados dinamicamente por senha
AUTHORIZED_USERS_FILE = "authorized_users.json"
authorized_users = set()

def load_authorized_users():
    global authorized_users
    authorized_users = set()
    if os.path.exists(AUTHORIZED_USERS_FILE):
        try:
            with open(AUTHORIZED_USERS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    authorized_users = set(data)
            logger.info(f"{len(authorized_users)} usuários autorizados dinamicamente carregados.")
        except Exception as e:
            logger.error(f"Erro ao carregar authorized_users.json: {e}")

def save_authorized_user(user_id):
    global authorized_users
    authorized_users.add(user_id)
    try:
        with open(AUTHORIZED_USERS_FILE, "w") as f:
            json.dump(list(authorized_users), f)
        logger.info(f"Usuário {user_id} adicionado a authorized_users.json.")
    except Exception as e:
        logger.error(f"Erro ao salvar authorized_users.json: {e}")

def is_user_authorized(user_id):
    return user_id in ALLOWED_USERS or user_id in authorized_users

# Inicializa o cliente BACnet tardiamente (dentro do event loop do Telegram)
bacnet = None

async def post_init(application: Application) -> None:
    global bacnet
    try:
        logger.info("Inicializando o cliente BACnet...")
        bacnet = BACnetClient()
        logger.info("Cliente BACnet inicializado com sucesso!")
    except Exception as e:
        logger.critical(f"Erro ao inicializar o cliente BACnet no post_init: {e}")
        # Encerra o loop caso ocorra erro crítico de inicialização
        loop = asyncio.get_running_loop()
        loop.stop()

def restricted(func):
    """Decorator para restringir acesso aos usuários autorizados (por whitelist ou senha)"""
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_user_authorized(user_id):
            # Define estado aguardando senha e solicita a senha
            context.user_data["state"] = "AWAITING_PASSWORD"
            await update.message.reply_text(
                "🔒 *Acesso Restrito.*\n"
                "Para interagir com este bot, por favor digite a senha de acesso:",
                parse_mode="Markdown"
            )
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- CLASSIFICADOR DE ANDAR ---

def classify_floor(device):
    """Classifica com 100% de sucesso o andar do equipamento baseado no nome/endereço"""
    name = device.get("name", "").upper()
    long_name = device.get("long_name", "").upper()
    
    # 1. Regex search no nome do dispositivo
    match = re.search(r'[.-](TE|[1-4]P|[1-2]S)[.-]', name)
    if match:
        return match.group(1)
    
    # 2. Início do nome do dispositivo
    match_start = re.match(r'^(EV|RE)[.-](TE|[1-4]P|[1-2]S)', name)
    if match_start:
        return match_start.group(2)
        
    # 3. Nomes específicos e keywords
    if "GUARITA" in name or "GUARITA" in long_name:
        return "TE"
    if "AUTOMACAO" in name or "AUTOMACAO" in long_name:
        return "TE"
        
    # 4. Faixas de endereços físicas
    addr = device.get("address", "")
    if addr.startswith("12.11.") or addr.startswith("12.12."):
        return "1S"
        
    return "TE"

def update_time():
    return datetime.now().strftime("%H:%M:%S")

# --- COMANDOS DO TELEGRAM ---

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o Wizard do Bot perguntando se tem o endereço/nome"""
    context.user_data.clear()
    
    keyboard = [
        [
            InlineKeyboardButton("Sim, eu tenho 👍", callback_data="has_address_yes"),
            InlineKeyboardButton("Não, prefiro buscar 🔍", callback_data="has_address_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❄️ *Samsung DMS 2.5 BACnet Bot* ❄️\n\n"
        "Bem-vindo! Este assistente ajudará você a monitorar e controlar os equipamentos Samsung.\n\n"
        "❓ *Você tem o nome ou endereço do equipamento?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@restricted
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista as evaporadoras (legado)"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if not bacnet.devices:
        await update.message.reply_text("❌ Nenhum equipamento cadastrado no devices.json.")
        return
        
    devices_list = list(bacnet.devices.values())
    total_devices = len(devices_list)
    limit = 50
    lines = [f"❄️ *Lista de Equipamentos (Mostrando as primeiras {limit} de {total_devices}):*"]
    
    for dev in devices_list[:limit]:
        is_erv = bacnet.is_erv(dev)
        type_str = "ERV" if is_erv else "AC"
        lines.append(f"• `{dev['name']}` ({type_str}) - Endereço: `{dev['address']}`")
        
    lines.append("\n_Para iniciar o assistente interativo por botões, envie:_ `/start`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta o status de um equipamento (atalho direto via comando)"""
    if not context.args:
        await update.message.reply_text("ℹ️ *Uso correto:* `/status <nome_do_equipamento>`", parse_mode="Markdown")
        return
        
    query = " ".join(context.args)
    dev = bacnet.find_device(query)
    
    if not dev:
        await update.message.reply_text(f"❌ Equipamento *{query}* não foi encontrado.", parse_mode="Markdown")
        return
        
    await show_device_status_panel(update.message, context, dev, new_message=True)

@restricted
async def power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comandos directos de atalho `/ligar` e `/desligar`"""
    cmd = update.message.text.split()[0].lower()
    turn_on = "ligar" in cmd
    
    if not context.args:
        action_word = "ligar" if turn_on else "desligar"
        await update.message.reply_text(f"ℹ️ *Uso correto:* `/{action_word} <nome_do_equipamento>`", parse_mode="Markdown")
        return
        
    query = " ".join(context.args)
    dev = bacnet.find_device(query)
    if not dev:
        await update.message.reply_text(f"❌ Equipamento *{query}* não encontrado.", parse_mode="Markdown")
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    success = await bacnet.write_power(dev, turn_on)
    state_str = "LIGADO(A)" if turn_on else "DESLIGADO(A)"
    if success:
        await update.message.reply_text(f"✅ Sucesso! Equipamento *{dev['name']}* foi *{state_str}*.")
    else:
        await update.message.reply_text(f"❌ Falha ao enviar comando para *{dev['name']}*.")

@restricted
async def temp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando atalho direto `/temp <unidade> <valor>`"""
    if len(context.args) < 2:
        await update.message.reply_text("ℹ️ *Uso correto:* `/temp <nome_da_evaporadora> <graus_celsius>`", parse_mode="Markdown")
        return
        
    setpoint_str = context.args[-1]
    query = " ".join(context.args[:-1])
    
    try:
        setpoint = float(setpoint_str.replace(",", "."))
        if setpoint < 16.0 or setpoint > 30.0:
            await update.message.reply_text("⚠️ A temperatura alvo deve estar entre *16°C* e *30°C*.", parse_mode="Markdown")
            return
    except ValueError:
        await update.message.reply_text("⚠️ A temperatura informada deve ser um número válido.", parse_mode="Markdown")
        return
        
    dev = bacnet.find_device(query)
    if not dev:
        await update.message.reply_text(f"❌ Equipamento *{query}* não encontrado.", parse_mode="Markdown")
        return
        
    if bacnet.is_erv(dev):
        await update.message.reply_text(f"⚠️ O equipamento *{dev['name']}* é um ERV e não suporta controle de temperatura.", parse_mode="Markdown")
        return
        
    success = await bacnet.write_temp(dev, setpoint)
    if success:
        await update.message.reply_text(f"✅ Sucesso! Temperatura de *{dev['name']}* ajustada para *{setpoint}°C*.")
    else:
        await update.message.reply_text(f"❌ Falha ao ajustar temperatura de *{dev['name']}*.")

@restricted
async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando atalho direto `/modo <unidade> <modo>`"""
    if len(context.args) < 2:
        is_erv_help = False
        if len(context.args) == 1:
            test_dev = bacnet.find_device(context.args[0])
            if test_dev and bacnet.is_erv(test_dev):
                is_erv_help = True
        if is_erv_help:
            await update.message.reply_text("ℹ️ *Uso correto:* `/modo <nome_do_erv> <modo>`\nModos: `auto`, `heatex` (troca calor), `bypass`, `sleep`", parse_mode="Markdown")
        else:
            await update.message.reply_text("ℹ️ *Uso correto:* `/modo <nome_da_evaporadora> <modo>`\nModos: `auto`, `cool`, `heat`, `fan`, `dry`", parse_mode="Markdown")
        return
        
    mode_str = context.args[-1].lower()
    query = " ".join(context.args[:-1])
    dev = bacnet.find_device(query)
    if not dev:
        await update.message.reply_text(f"❌ Equipamento *{query}* não encontrado.", parse_mode="Markdown")
        return
        
    try:
        success = await bacnet.write_mode(dev, mode_str)
        if success:
            await update.message.reply_text(f"✅ Sucesso! Modo de *{dev['name']}* alterado para *{mode_str.upper()}*.")
        else:
            await update.message.reply_text(f"❌ Falha ao alterar modo de *{dev['name']}*.")
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ {ve}", parse_mode="Markdown")

@restricted
async def fan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando atalho direto `/vel <unidade> <velocidade>`"""
    if len(context.args) < 2:
        is_erv_help = False
        if len(context.args) == 1:
            test_dev = bacnet.find_device(context.args[0])
            if test_dev and bacnet.is_erv(test_dev):
                is_erv_help = True
        if is_erv_help:
            await update.message.reply_text("ℹ️ *Uso correto:* `/vel <nome_do_erv> <velocidade>`\nVelocidades: `low`, `high`, `turbo`", parse_mode="Markdown")
        else:
            await update.message.reply_text("ℹ️ *Uso correto:* `/vel <nome_da_evaporadora> <velocidade>`\nVelocidades: `auto`, `low`, `mid`, `high`, `turbo`", parse_mode="Markdown")
        return
        
    speed_str = context.args[-1].lower()
    query = " ".join(context.args[:-1])
    dev = bacnet.find_device(query)
    if not dev:
        await update.message.reply_text(f"❌ Equipamento *{query}* não encontrado.", parse_mode="Markdown")
        return
        
    try:
        success = await bacnet.write_fan_speed(dev, speed_str)
        if success:
            await update.message.reply_text(f"✅ Sucesso! Velocidade de *{dev['name']}* alterada para *{speed_str.upper()}*.")
        else:
            await update.message.reply_text(f"❌ Falha ao alterar velocidade de *{dev['name']}*.")
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ {ve}", parse_mode="Markdown")

# --- CONVERSATIONAL TEXT MESSAGE ROUTER & AUTHENTICATION ---

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia todas as mensagens de texto e atalhos rápidos"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # 1. Se o usuário NÃO está autenticado
    if not is_user_authorized(user_id):
        if context.user_data.get("state") == "AWAITING_PASSWORD":
            if text == ACCESS_PASSWORD:
                save_authorized_user(user_id)
                context.user_data.clear()
                await update.message.reply_text(
                    "✅ *Senha Correta!*\n"
                    "Acesso liberado com sucesso. Digite `/start` para iniciar o fluxo interativo.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ *Senha Incorreta.*\n"
                    "Por favor, tente novamente ou insira a senha fornecida pelo administrador:",
                    parse_mode="Markdown"
                )
        else:
            context.user_data["state"] = "AWAITING_PASSWORD"
            await update.message.reply_text(
                "🔒 *Acesso Restrito.*\n"
                "Para utilizar este bot, por favor digite a senha de acesso:",
                parse_mode="Markdown"
            )
        return

    # 2. Usuário AUTENTICADO
    state = context.user_data.get("state")
    if state == "WAITING_FOR_DIRECT_QUERY":
        await process_direct_query(update, context, text)
    else:
        # Se digitar um texto qualquer (ex: "RE-4P-05") sem barra de comando, trata como busca direta!
        await process_direct_query(update, context, text)

# --- DIRECT TEXT QUERY SEARCH ---

async def process_direct_query(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    dev = bacnet.find_device(text)
    if not dev:
        keyboard = [
            [InlineKeyboardButton("🔍 Buscar por Andar", callback_data="has_address_no")],
            [InlineKeyboardButton("🔙 Menu Inicial", callback_data="back_to_start")]
        ]
        await update.message.reply_text(
            f"❌ O equipamento *{text}* não foi encontrado.\n\n"
            "Verifique a grafia ou utilize a busca assistida abaixo:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
        
    await show_device_status_panel(update.message, context, dev, new_message=True)

# --- WIZARD STEPS ---

async def show_floor_selection(query, context):
    floors_map = [
        ("Térreo", "TE"),
        ("1º Andar", "1P"),
        ("2º Andar", "2P"),
        ("3º Andar", "3P"),
        ("4º Andar", "4P"),
        ("1º Subsolo", "1S")
    ]
    keyboard = []
    for i in range(0, len(floors_map), 2):
        row = [InlineKeyboardButton(floors_map[i][0], callback_data=f"floor_{floors_map[i][1]}")]
        if i + 1 < len(floors_map):
            row.append(InlineKeyboardButton(floors_map[i+1][0], callback_data=f"floor_{floors_map[i+1][1]}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="back_to_start")])
    
    await query.message.edit_text(
        "🏢 *Selecionar Andar*\n\n"
        "Em qual andar fica o equipamento que você deseja consultar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_system_selection(query, context):
    floor_code = context.user_data.get("selected_floor")
    floor_names = {
        "TE": "Térreo", "1P": "1º Andar", "2P": "2º Andar",
        "3P": "3º Andar", "4P": "4º Andar", "1S": "1º Subsolo"
    }
    floor_name = floor_names.get(floor_code, floor_code)
    
    keyboard = [
        [
            InlineKeyboardButton("❄️ Evaporadora (AC)", callback_data="system_AC"),
            InlineKeyboardButton("🌀 ERV (Ventilador)", callback_data="system_ERV")
        ],
        [
            InlineKeyboardButton("🔙 Voltar", callback_data="has_address_no")
        ]
    ]
    
    await query.message.edit_text(
        f"🏢 *Andar:* {floor_name}\n\n"
        "⚡ *Qual o tipo de sistema que deseja buscar?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_devices_list(query, context):
    floor_code = context.user_data.get("selected_floor")
    system_type = context.user_data.get("selected_system")
    page = context.user_data.get("page", 0)
    
    floor_names = {
        "TE": "Térreo", "1P": "1º Andar", "2P": "2º Andar",
        "3P": "3º Andar", "4P": "4º Andar", "1S": "1º Subsolo"
    }
    floor_name = floor_names.get(floor_code, floor_code)
    system_name = "Evaporadora (AC)" if system_type == "AC" else "ERV (Ventilador)"
    
    # Filtra e ordena
    filtered_devs = []
    for dev in bacnet.devices.values():
        dev_floor = classify_floor(dev)
        is_erv_dev = bacnet.is_erv(dev)
        if dev_floor == floor_code:
            if (system_type == "ERV" and is_erv_dev) or (system_type == "AC" and not is_erv_dev):
                filtered_devs.append(dev)
                
    filtered_devs.sort(key=lambda d: d["name"])
    
    total = len(filtered_devs)
    if total == 0:
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data=f"floor_{floor_code}")]]
        await query.message.edit_text(
            f"🏢 *Andar:* {floor_name} | *Tipo:* {system_name}\n\n"
            "❌ Nenhum equipamento encontrado nesta categoria.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
        
    start_idx = page * 10
    end_idx = min(start_idx + 10, total)
    page_devs = filtered_devs[start_idx:end_idx]
    
    # Monta texto em Markdown amigável (V1)
    lines = [
        f"🏢 *Andar:* {floor_name} | *Tipo:* {system_name}",
        f"📋 Encontrados: *{total}* (Mostrando {start_idx + 1} a {end_idx}):\n"
    ]
    for idx, dev in enumerate(page_devs, 1):
        lines.append(f"*{idx}.* `{dev['name']}` - Endereço: `{dev['address']}`")
    lines.append("\n👉 *Escolha o número correspondente abaixo:*")
    
    # Cria botões numéricos
    keyboard = []
    num_row = []
    for idx, dev in enumerate(page_devs, 1):
        num_row.append(InlineKeyboardButton(str(idx), callback_data=f"select_dev_{dev['name']}"))
        if len(num_row) == 5:
            keyboard.append(num_row)
            num_row = []
    if num_row:
        keyboard.append(num_row)
        
    # Navegação
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"page_{page - 1}"))
    if end_idx < total:
        nav_row.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([
        InlineKeyboardButton("🔙 Voltar para Sistemas", callback_data=f"floor_{floor_code}")
    ])
    
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- INTERACTIVE CONTROL PANEL & STATUS ---

async def show_device_status_panel(message, context, dev, new_message=False):
    chat_id = message.chat_id
    if new_message:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        status_msg = await message.reply_text(f"🔍 Consultando gateway BACnet para *{dev['name']}*...")
    else:
        status_msg = message
        # Atualiza sem mandar nova mensagem
        
    status = await bacnet.read_status(dev)
    if not status:
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="back_to_list")]]
        await status_msg.edit_text(
            f"❌ Erro ao ler dados do equipamento *{dev['name']}* via BACnet. Verifique a conexão.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    power_icon = "🟢" if status["power"] == "LIGADO" else "🔴"
    error_status = "✅ Normal (0)" if status["error"] == 0 else f"⚠️ Erro: {status['error']}"
    is_erv = status.get("is_erv")
    
    # Formatação do painel
    if is_erv:
        status_text = (
            f"🌀 *Status da Unidade ERV: {status['name']}*\n"
            f"📍 Endereço Canal: `{status['address']}`\n"
            f"🏷️ Descrição: _{dev['long_name']}_\n"
            "-------------------------------------\n"
            f"{power_icon} *Energia:* {status['power']}\n"
            f"🔄 *Modo:* {status['mode']}\n"
            f"💨 *Ventilador:* {status['fan_speed']}\n"
            f"🩺 *Status Técnico:* {error_status}\n"
            f"🕒 Atualizado em: {update_time()}"
        )
    else:
        status_text = (
            f"📊 *Status da Unidade AC: {status['name']}*\n"
            f"📍 Endereço Canal: `{status['address']}`\n"
            f"🏷️ Descrição: _{dev['long_name']}_\n"
            "-------------------------------------\n"
            f"{power_icon} *Energia:* {status['power']}\n"
            f"🌡️ *Temp. Ambiente:* {status['room_temp']} °C\n"
            f"🎯 *Temp. Alvo:* {status['setpoint']} °C\n"
            f"🔄 *Modo:* {status['mode']}\n"
            f"💨 *Ventilador:* {status['fan_speed']}\n"
            f"🩺 *Status Técnico:* {error_status}\n"
            f"🕒 Atualizado em: {update_time()}"
        )
        
    # Teclado Inline de Ações
    keyboard = []
    
    # 1. Botão Power
    if status["power"] == "LIGADO":
        power_btn = InlineKeyboardButton("🔴 Desligar", callback_data=f"control_power_{dev['name']}_off")
    else:
        power_btn = InlineKeyboardButton("🟢 Ligar", callback_data=f"control_power_{dev['name']}_on")
    keyboard.append([power_btn])
    
    # 2. Modos e Ventilação
    keyboard.append([
        InlineKeyboardButton("🔄 Mudar Modo", callback_data=f"control_modeshow_{dev['name']}"),
        InlineKeyboardButton("💨 Ventilador", callback_data=f"control_fanshow_{dev['name']}")
    ])
    
    # 3. Temperatura (apenas AC)
    if not is_erv:
        keyboard.append([
            InlineKeyboardButton("🌡️ Ajustar Temperatura", callback_data=f"control_tempshow_{dev['name']}")
        ])
        
    # 4. Atualizar e Voltar
    keyboard.append([
        InlineKeyboardButton("🔄 Atualizar", callback_data=f"select_dev_{dev['name']}"),
        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_list")
    ])
    
    await status_msg.edit_text(
        status_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- SUBMENUS CONTROLS ---

async def show_mode_submenu(query, dev):
    is_erv = bacnet.is_erv(dev)
    keyboard = []
    if is_erv:
        modes = [
            ("Auto 🔄", "auto"),
            ("HeatEx (Troca) 🌡️", "heatex"),
            ("Bypass ➡️", "bypass"),
            ("Sleep 💤", "sleep")
        ]
    else:
        modes = [
            ("Auto 🔄", "auto"),
            ("Cool (Frio) ❄️", "cool"),
            ("Heat (Quente) ☀️", "heat"),
            ("Fan (Ventilar) 💨", "fan"),
            ("Dry (Desumidificar) 💧", "dry")
        ]
        
    for i in range(0, len(modes), 2):
        row = [InlineKeyboardButton(modes[i][0], callback_data=f"control_modeexec_{dev['name']}_{modes[i][1]}")]
        if i + 1 < len(modes):
            row.append(InlineKeyboardButton(modes[i+1][0], callback_data=f"control_modeexec_{dev['name']}_{modes[i+1][1]}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"select_dev_{dev['name']}")])
    
    await query.message.edit_text(
        f"🔄 *Mudar Modo de {dev['name']}*\n"
        "Selecione o modo de operação desejado:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_fan_submenu(query, dev):
    is_erv = bacnet.is_erv(dev)
    keyboard = []
    if is_erv:
        speeds = [
            ("Baixo (Low) 🔈", "low"),
            ("Alto (High) 🔊", "high"),
            ("Turbo ⚡", "turbo")
        ]
    else:
        speeds = [
            ("Auto 🔄", "auto"),
            ("Baixo (Low) 🔈", "low"),
            ("Médio (Mid) 🔉", "mid"),
            ("Alto (High) 🔊", "high"),
            ("Turbo ⚡", "turbo")
        ]
        
    for i in range(0, len(speeds), 2):
        row = [InlineKeyboardButton(speeds[i][0], callback_data=f"control_fanexec_{dev['name']}_{speeds[i][1]}")]
        if i + 1 < len(speeds):
            row.append(InlineKeyboardButton(speeds[i+1][0], callback_data=f"control_fanexec_{dev['name']}_{speeds[i+1][1]}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"select_dev_{dev['name']}")])
    
    await query.message.edit_text(
        f"💨 *Velocidade do Ventilador de {dev['name']}*\n"
        "Selecione a velocidade desejada:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_temp_submenu(query, dev):
    keyboard = []
    temp_row = []
    # Grid compacto de 16°C a 30°C
    for t in range(16, 31):
        temp_row.append(InlineKeyboardButton(f"{t}°", callback_data=f"control_tempexec_{dev['name']}_{t}"))
        if len(temp_row) == 5:
            keyboard.append(temp_row)
            temp_row = []
    if temp_row:
        keyboard.append(temp_row)
        
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data=f"select_dev_{dev['name']}")])
    
    await query.message.edit_text(
        f"🌡️ *Ajustar Temperatura de {dev['name']}*\n"
        "Escolha a temperatura alvo desejada:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- EXECUTING DEVICE CONTROLS ---

async def handle_device_control_callback(query, context, dev, action, extra_args):
    is_erv = bacnet.is_erv(dev)
    dev_type = "ERV" if is_erv else "evaporadora"
    
    if action == "power":
        power_state = extra_args[0]
        turn_on = power_state == "on"
        action_text = "LIGAR" if turn_on else "DESLIGAR"
        await query.message.edit_text(f"⚙️ Enviando comando para *{action_text}* o(a) {dev_type} *{dev['name']}*...")
        success = await bacnet.write_power(dev, turn_on)
        if success:
            state_text = "LIGADO(A)" if turn_on else "DESLIGADO(A)"
            await query.message.edit_text(f"✅ Sucesso! {dev_type.capitalize()} *{dev['name']}* foi *{state_text}*.")
        else:
            await query.message.edit_text(f"❌ Falha ao enviar comando para *{dev['name']}*.")
        await asyncio.sleep(1.5)
        await show_device_status_panel(query.message, context, dev)
        
    elif action == "modeshow":
        await show_mode_submenu(query, dev)
        
    elif action == "modeexec":
        mode_val = extra_args[0]
        await query.message.edit_text(f"⚙️ Alterando modo para *{mode_val.upper()}* em *{dev['name']}*...")
        success = await bacnet.write_mode(dev, mode_val)
        if success:
            await query.message.edit_text(f"✅ Sucesso! Modo alterado para *{mode_val.upper()}*.")
        else:
            await query.message.edit_text(f"❌ Falha ao alterar modo de *{dev['name']}*.")
        await asyncio.sleep(1.5)
        await show_device_status_panel(query.message, context, dev)
        
    elif action == "fanshow":
        await show_fan_submenu(query, dev)
        
    elif action == "fanexec":
        speed_val = extra_args[0]
        await query.message.edit_text(f"⚙️ Alterando velocidade para *{speed_val.upper()}* em *{dev['name']}*...")
        success = await bacnet.write_fan_speed(dev, speed_val)
        if success:
            await query.message.edit_text(f"✅ Sucesso! Velocidade alterada para *{speed_val.upper()}*.")
        else:
            await query.message.edit_text(f"❌ Falha ao alterar velocidade de *{dev['name']}*.")
        await asyncio.sleep(1.5)
        await show_device_status_panel(query.message, context, dev)
        
    elif action == "tempshow":
        await show_temp_submenu(query, dev)
        
    elif action == "tempexec":
        temp_val = float(extra_args[0])
        await query.message.edit_text(f"⚙️ Ajustando temperatura para *{temp_val}°C* em *{dev['name']}*...")
        success = await bacnet.write_temp(dev, temp_val)
        if success:
            await query.message.edit_text(f"✅ Sucesso! Temperatura ajustada para *{temp_val}°C*.")
        else:
            await query.message.edit_text(f"❌ Falha ao ajustar temperatura de *{dev['name']}*.")
        await asyncio.sleep(1.5)
        await show_device_status_panel(query.message, context, dev)

# --- WIZARD REDIRECTS ---

async def show_start_over(query, context):
    keyboard = [
        [
            InlineKeyboardButton("Sim, eu tenho 👍", callback_data="has_address_yes"),
            InlineKeyboardButton("Não, prefiro buscar 🔍", callback_data="has_address_no")
        ]
    ]
    await query.message.edit_text(
        "❓ *Você tem o nome ou endereço do equipamento?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- GLOBAL CALLBACKS HANDLER ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await query.answer("🔒 Acesso Restrito. Digite a senha primeiro.", show_alert=True)
        return
        
    await query.answer()
    data = query.data
    
    if data == "back_to_start":
        context.user_data.clear()
        await show_start_over(query, context)
        
    elif data == "has_address_yes":
        context.user_data["state"] = "WAITING_FOR_DIRECT_QUERY"
        await query.message.edit_text(
            "📝 *Busca Direta*\n\n"
            "Por favor, digite o nome ou endereço do equipamento:\n"
            "👉 Exemplos: `EV-1P-2.1`, `RE-4P-05`, `12.00.03`, `15.00.01`",
            parse_mode="Markdown"
        )
        
    elif data == "has_address_no":
        await show_floor_selection(query, context)
        
    elif data.startswith("floor_"):
        floor_code = data.split("_")[1]
        context.user_data["selected_floor"] = floor_code
        await show_system_selection(query, context)
        
    elif data.startswith("system_"):
        system_type = data.split("_")[1]
        context.user_data["selected_system"] = system_type
        context.user_data["page"] = 0
        await show_devices_list(query, context)
        
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        context.user_data["page"] = page
        await show_devices_list(query, context)
        
    elif data.startswith("select_dev_"):
        dev_name = data.split("_")[2]
        dev = bacnet.find_device(dev_name)
        if dev:
            await show_device_status_panel(query.message, context, dev)
            
    elif data == "back_to_list":
        floor_code = context.user_data.get("selected_floor")
        system_type = context.user_data.get("selected_system")
        if floor_code and system_type:
            await show_devices_list(query, context)
        else:
            context.user_data.clear()
            await show_start_over(query, context)
            
    elif data.startswith("control_"):
        parts = data.split("_")
        action = parts[1]
        dev_name = parts[2]
        dev = bacnet.find_device(dev_name)
        if dev:
            await handle_device_control_callback(query, context, dev, action, parts[3:])

# --- MAIN EXECUTION ---

def main():
    if not TOKEN or TOKEN == "SEU_TOKEN_TELEGRAM_AQUI":
        logger.critical("Erro: TELEGRAM_BOT_TOKEN não foi configurado corretamente no arquivo `.env`.")
        print("Configure o token do bot do Telegram no arquivo .env antes de iniciar.")
        return
        
    logger.info("Iniciando o Bot do Telegram...")
    if SIMULATION_MODE:
        logger.info("Aviso: Rodando em MODO SIMULAÇÃO (Sem conexão real).")
        
    load_authorized_users()
    
    # Cria o loop de eventos para o thread principal
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Inicializa a aplicação com post_init
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("ligar", power_command))
    app.add_handler(CommandHandler("desligar", power_command))
    app.add_handler(CommandHandler("temp", temp_command))
    app.add_handler(CommandHandler("modo", mode_command))
    app.add_handler(CommandHandler("vel", fan_command))
    
    # Handlers para interação conversacional e inline
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("Bot ativo! Pressione Ctrl+C para encerrar.")
    app.run_polling()

if __name__ == "__main__":
    main()
