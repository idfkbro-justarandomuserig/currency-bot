# bot.py
# Final Version v1.1.9 - Truly Complete Code - Verified Full - Restored Economy Reset Safeguard, Added /pay command.

import disnake
from disnake.ext import commands, tasks
import os
import json
import datetime
import pytz
import random
import asyncio
import time as time_module # Alias to avoid conflict with datetime.time
import logging
from dotenv import load_dotenv
from datetime import time, timedelta, timezone
import uuid # For generating shop item IDs

# --- Logging Setup (Revised - Final Fix) ---
log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log_level = logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s', handlers=[logging.StreamHandler()])
disnake_logger = logging.getLogger('disnake')
disnake_logger.setLevel(log_level)
log_file_handler = logging.FileHandler(filename='discord_bot.log', encoding='utf-8', mode='w')
log_file_handler.setFormatter(log_formatter)
disnake_logger.addHandler(log_file_handler)
disnake_logger.propagate = False
logger = logging.getLogger(__name__)

# --- Configuration ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PLACEHOLDER_IDS_PRESENT = False
_SHOPKEEPER_ROLE_ID_STR = os.getenv("SHOPKEEPER_ROLE_ID", "1368456384886079519")
_ADMIN_CHANNEL_ID_STR = os.getenv("ADMIN_CHANNEL_ID", "1368455333751816213")
SUPPORTER_ROLE_ID = 1368689142363590726
VIP_ROLE_ID = 1368689440045797436
_LOTTERY_ANNOUNCE_CHANNEL_ID_STR = os.getenv("LOTTERY_ANNOUNCE_CHANNEL_ID", _ADMIN_CHANNEL_ID_STR)

try:
    SHOPKEEPER_ROLE_ID = int(_SHOPKEEPER_ROLE_ID_STR)
    ADMIN_CHANNEL_ID = int(_ADMIN_CHANNEL_ID_STR)
    LOTTERY_ANNOUNCE_CHANNEL_ID = int(_LOTTERY_ANNOUNCE_CHANNEL_ID_STR)
    if not isinstance(SUPPORTER_ROLE_ID, int) or SUPPORTER_ROLE_ID <= 0: raise ValueError("Hardcoded SUPPORTER_ROLE_ID invalid.")
    if not isinstance(VIP_ROLE_ID, int) or VIP_ROLE_ID <= 0: raise ValueError("Hardcoded VIP_ROLE_ID invalid.")
except ValueError as e:
    logger.critical(f"FATAL: Invalid ID config: {e}"); exit(1)

original_placeholders = { "SHOPKEEPER_ROLE_ID": 987654321098765432, "ADMIN_CHANNEL_ID": 111222333444555666, "SUPPORTER_ROLE_ID": 101010101010101010, "VIP_ROLE_ID": 202020202020202020, "LOTTERY_ANNOUNCE_CHANNEL_ID": 111222333444555666 if _LOTTERY_ANNOUNCE_CHANNEL_ID_STR == "111222333444555666" else None }
current_ids = { "SHOPKEEPER_ROLE_ID": SHOPKEEPER_ROLE_ID, "ADMIN_CHANNEL_ID": ADMIN_CHANNEL_ID, "SUPPORTER_ROLE_ID": SUPPORTER_ROLE_ID, "VIP_ROLE_ID": VIP_ROLE_ID, "LOTTERY_ANNOUNCE_CHANNEL_ID": LOTTERY_ANNOUNCE_CHANNEL_ID if original_placeholders["LOTTERY_ANNOUNCE_CHANNEL_ID"] else None }
for name, placeholder_id in original_placeholders.items():
    if placeholder_id is not None and current_ids.get(name) == placeholder_id:
         logger.warning(f"Config Warning: {name} still placeholder ({placeholder_id})."); PLACEHOLDER_IDS_PRESENT = True

# Economy Settings
INITIAL_STARTING_BALANCE = int(os.getenv("INITIAL_STARTING_BALANCE", 1000)) # Default 1k starting
ECONOMY_RESET_THRESHOLD = float(os.getenv("ECONOMY_RESET_THRESHOLD", 1.0e15)) # Default: 1 Quadrillion

try: LOTTERY_TICKET_PRICE = int(os.getenv("LOTTERY_TICKET_PRICE", 10))
except ValueError: LOTTERY_TICKET_PRICE = 10
try: LOTTERY_INTERVAL_HOURS = float(os.getenv("LOTTERY_INTERVAL_HOURS", 2.0))
except ValueError: LOTTERY_INTERVAL_HOURS = 2.0
SHOP_TIMEZONE_STR = os.getenv("SHOP_TIMEZONE", 'America/Chicago')
try: SHOP_TIMEZONE = pytz.timezone(SHOP_TIMEZONE_STR)
except pytz.UnknownTimeZoneError: SHOP_TIMEZONE = pytz.utc
SHOP_OPEN_HOUR = int(os.getenv("SHOP_OPEN_HOUR", 10)); SHOP_OPEN_MINUTE = int(os.getenv("SHOP_OPEN_MINUTE", 0))
SHOP_CLOSE_HOUR = int(os.getenv("SHOP_CLOSE_HOUR", 21)); SHOP_CLOSE_MINUTE = int(os.getenv("SHOP_CLOSE_MINUTE", 0))
SHOP_OPEN_TIME = time(SHOP_OPEN_HOUR, SHOP_OPEN_MINUTE); SHOP_CLOSE_TIME = time(SHOP_CLOSE_HOUR, SHOP_CLOSE_MINUTE)
SLOT_EMOJIS = ["🍎", "🍊", "🍋", "🍉", "🍇", "🍓", "🍒", "⭐", "💎"]; SLOT_JACKPOT_EMOJI = "💎"
DEFAULT_SLOT_JACKPOT_CONTRIBUTION = 0.10
DEFAULT_SLOT_JACKPOT_OVERRIDE_CHANCE = 0.0
DICE_WIN_MULTIPLIER = 5; REDBLACK_WIN_MULTIPLIER = 1.9; REDBLACK_COOLDOWN_SECONDS = 5
BIG_WIN_THRESHOLD = 100000
SCAN_MESSAGE_LIMIT_PER_CHANNEL = int(os.getenv("SCAN_MESSAGE_LIMIT", 10000))
DATA_DIR = "data"; USER_DATA_FILE = os.path.join(DATA_DIR, "user_balances.json")
SHOP_ITEMS_FILE = os.path.join(DATA_DIR, "shop_items.json"); BOT_DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")
if not DISCORD_BOT_TOKEN: logger.critical("FATAL: Token missing."); exit(1)
os.makedirs(DATA_DIR, exist_ok=True)

# --- Data Persistence ---
user_data = {}; shop_items = {}; bot_data = {}
def load_user_data():
    global user_data
    try:
        with open(USER_DATA_FILE, 'r') as f: loaded_data = json.load(f)
        migrated_data = {}; migration_needed = False
        for user_id_str, data in loaded_data.items():
            try:
                user_id = int(user_id_str)
                if isinstance(data, int): migrated_data[user_id] = {"balance": data, "savings": 0, "pin": None}; migration_needed = True
                elif isinstance(data, dict):
                    migrated_data[user_id] = {"balance": data.get("balance", 0), "savings": data.get("savings", 0), "pin": data.get("pin", None)}
                    if migrated_data[user_id]["pin"] is not None and not isinstance(migrated_data[user_id]["pin"], str): migrated_data[user_id]["pin"] = None
                else: logger.warning(f"Skipping invalid data for user {user_id_str}"); continue
            except ValueError: logger.warning(f"Skipping invalid user ID key '{user_id_str}'"); continue
        user_data = migrated_data
        if migration_needed: logger.info(f"Migrated user data."); save_user_data()
        elif USER_DATA_FILE and os.path.exists(USER_DATA_FILE): logger.info(f"Loaded user data.")
    except FileNotFoundError: logger.warning(f"{USER_DATA_FILE} not found."); user_data = {}
    except json.JSONDecodeError: logger.error(f"Error decoding {USER_DATA_FILE}."); user_data = {}
    except Exception as e: logger.error(f"Error loading user data: {e}"); user_data = {}
def save_user_data():
    try:
        data_to_save = {str(k): v for k, v in user_data.items()}
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=4)
    except Exception as e: logger.error(f"Error saving user data: {e}")
def get_user_data(user_id: int) -> dict:
    user_id = int(user_id)
    if user_id not in user_data:
        user_data[user_id] = {"balance": INITIAL_STARTING_BALANCE, "savings": 0, "pin": None}
        logger.info(f"Initialized new user {user_id} with {INITIAL_STARTING_BALANCE} balance.")
    ud = user_data[user_id]
    if "balance" not in ud or not isinstance(ud["balance"], (int, float)): ud["balance"] = 0
    if "savings" not in ud or not isinstance(ud["savings"], (int, float)): ud["savings"] = 0
    if "pin" not in ud or (ud["pin"] is not None and not isinstance(ud["pin"], str)): ud["pin"] = None
    return user_data[user_id]
def load_shop_items():
    global shop_items
    try:
        with open(SHOP_ITEMS_FILE, 'r') as f: shop_items = json.load(f)
        logger.info(f"Loaded shop items.")
    except FileNotFoundError: logger.warning(f"{SHOP_ITEMS_FILE} not found."); shop_items = {}
    except json.JSONDecodeError: logger.error(f"Error decoding {SHOP_ITEMS_FILE}."); shop_items = {}
    except Exception as e: logger.error(f"Error loading shop items: {e}"); shop_items = {}
def save_shop_items():
    try:
        with open(SHOP_ITEMS_FILE, 'w') as f: json.dump(shop_items, f, indent=4)
    except Exception as e: logger.error(f"Error saving shop items: {e}")
def load_bot_data():
    global bot_data
    default_data = { "slot_jackpot_pool": 0.0, "lottery_pot": 0.0, "lottery_tickets": [], "slot_jackpot_contribution": DEFAULT_SLOT_JACKPOT_CONTRIBUTION, "slot_jackpot_override_chance": DEFAULT_SLOT_JACKPOT_OVERRIDE_CHANCE, "initial_balance_check_done": False }
    try:
        with open(BOT_DATA_FILE, 'r') as f: loaded_data = json.load(f)
        bot_data["slot_jackpot_pool"] = float(loaded_data.get("slot_jackpot_pool", default_data["slot_jackpot_pool"]))
        bot_data["lottery_pot"] = float(loaded_data.get("lottery_pot", default_data["lottery_pot"]))
        bot_data["lottery_tickets"] = loaded_data.get("lottery_tickets", default_data["lottery_tickets"])
        contrib = float(loaded_data.get("slot_jackpot_contribution", default_data["slot_jackpot_contribution"]))
        override = float(loaded_data.get("slot_jackpot_override_chance", default_data["slot_jackpot_override_chance"]))
        bot_data["slot_jackpot_contribution"] = max(0.0, min(1.0, contrib))
        bot_data["slot_jackpot_override_chance"] = max(0.0, min(1.0, override))
        bot_data["initial_balance_check_done"] = loaded_data.get("initial_balance_check_done", default_data["initial_balance_check_done"])
        if not isinstance(bot_data["slot_jackpot_pool"], float): bot_data["slot_jackpot_pool"] = 0.0
        if not isinstance(bot_data["lottery_pot"], float): bot_data["lottery_pot"] = 0.0
        if not isinstance(bot_data["lottery_tickets"], list): bot_data["lottery_tickets"] = []
        if not isinstance(bot_data["initial_balance_check_done"], bool): bot_data["initial_balance_check_done"] = False
        logger.info(f"Loaded bot data (JP Contrib: {bot_data['slot_jackpot_contribution']:.1%}, JP Override: {bot_data['slot_jackpot_override_chance']:.1%}).")
    except FileNotFoundError: logger.warning(f"{BOT_DATA_FILE} not found."); bot_data = default_data.copy()
    except json.JSONDecodeError: logger.error(f"Error decoding {BOT_DATA_FILE}."); bot_data = default_data.copy()
    except Exception as e: logger.error(f"Error loading bot data: {e}"); bot_data = default_data.copy()
def save_bot_data():
    try:
        with open(BOT_DATA_FILE, 'w') as f: json.dump(bot_data, f, indent=4)
    except Exception as e: logger.error(f"Error saving bot data: {e}")

# --- Bot Initialization ---
intents = disnake.Intents.default()
intents.message_content = True; intents.members = True; intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None, sync_commands_debug=True)
bot.retroactive_scan_done = False

# --- Helper Functions ---
async def perform_economy_reset(triggered_by: str = "Automatic Threshold"): # RESTORED
    """Resets balances, pools, and notifies admins."""
    logger.warning(f"ECONOMY RESET TRIGGERED! Reason: {triggered_by}")
    print(f"!!! ECONOMY RESET TRIGGERED: {triggered_by} !!!")
    load_user_data(); load_bot_data() # Reload data just before reset
    users_reset = 0
    for user_id_str in list(user_data.keys()):
        try:
            user_id = int(user_id_str)
            udata = user_data[user_id]
            udata["balance"] = INITIAL_STARTING_BALANCE # Reset to starting balance
            udata["savings"] = 0
            users_reset += 1
        except (ValueError, KeyError) as e: logger.warning(f"Skipping invalid user ID {user_id_str} during reset: {e}")
    bot_data["slot_jackpot_pool"] = 0.0
    bot_data["lottery_pot"] = 0.0
    bot_data["lottery_tickets"] = []
    logger.warning(f"Economy Reset Complete. Reset {users_reset} users. Reset pools.")
    save_user_data(); save_bot_data() # Save reset state
    try:
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID) or await bot.fetch_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send(f"🚨 **ECONOMY RESET TRIGGERED** 🚨\nReason: {triggered_by}\nBalances reset to **{INITIAL_STARTING_BALANCE:,}**, savings/pools cleared.")
            logger.info(f"Sent economy reset notification to admin channel {ADMIN_CHANNEL_ID}.")
        else: logger.error("Could not find admin channel for reset notification.")
    except Exception as e: logger.error(f"Failed to send economy reset notification: {e}")

async def announce_big_win(interaction: disnake.ApplicationCommandInteraction, user: disnake.Member, winnings: float, game_name: str):
    if winnings < BIG_WIN_THRESHOLD: return
    channel = interaction.channel
    if not channel or not isinstance(channel, disnake.TextChannel): logger.warning(f"Cannot announce big win - invalid channel."); return
    if not interaction.guild: return # Need guild context for permissions
    perms = channel.permissions_for(interaction.guild.me)
    if not perms.send_messages: logger.warning(f"Cannot announce big win - missing Send Messages perm."); return
    everyone_ping_allowed = perms.mention_everyone
    mention_str = f"@everyone {user.mention}" if everyone_ping_allowed else f"{user.mention}"
    winnings_display = f"{int(winnings):,}" if winnings == int(winnings) else f"{winnings:,.2f}"
    message = f"🎉 **BIG WIN!** {mention_str} just won **{winnings_display} coins** playing {game_name}! 🎉"
    try:
        await channel.send(message, allowed_mentions=disnake.AllowedMentions(everyone=everyone_ping_allowed, users=[user]))
        logger.info(f"Announced big win for {user.name} ({user.id}) in #{channel.name}. Pinged everyone: {everyone_ping_allowed}")
    except Exception as e: logger.error(f"Failed to send big win announcement: {e}", exc_info=True)

# --- Background Tasks ---
@tasks.loop(minutes=5)
async def autosave_data(): # RESTORED Economy Reset Check
    logger.debug("Autosaving...")
    try:
        load_user_data(); load_bot_data() # Load fresh data for check
        total_user_currency = sum(d.get('balance', 0) + d.get('savings', 0) for d in user_data.values() if isinstance(d, dict))
        total_pool_currency = bot_data.get('slot_jackpot_pool', 0.0) + bot_data.get('lottery_pot', 0.0)
        if not isinstance(total_pool_currency, (int, float)): total_pool_currency = 0.0
        total_currency = total_user_currency + total_pool_currency
        logger.debug(f"Total currency check: {total_currency:,.2f} / {ECONOMY_RESET_THRESHOLD:,.0f}")
        if total_currency >= ECONOMY_RESET_THRESHOLD:
            await perform_economy_reset(triggered_by=f"Automatic Threshold ({total_currency:,.0f})")
            logger.debug("Autosave cycle finished after economy reset.")
            return # Skip normal saving if reset occurred
    except Exception as e: logger.error(f"Error during economy reset check: {e}", exc_info=True)
    try: save_user_data()
    except Exception as e: logger.error(f"Autosave user data fail: {e}", exc_info=True)
    try: save_shop_items()
    except Exception as e: logger.error(f"Autosave shop items fail: {e}", exc_info=True)
    try: save_bot_data()
    except Exception as e: logger.error(f"Autosave bot data fail: {e}", exc_info=True)
    logger.debug("Autosave cycle finished.")
@autosave_data.before_loop
async def before_autosave(): await bot.wait_until_ready(); logger.info("Starting autosave.")
@tasks.loop(hours=LOTTERY_INTERVAL_HOURS)
async def lottery_drawing():
    logger.info("Attempting lottery drawing...")
    load_bot_data(); load_user_data()
    if not bot_data.get("lottery_tickets"): return logger.info("No lottery tickets sold.")
    if not isinstance(bot_data.get("lottery_pot", 0.0), (int, float)): bot_data["lottery_pot"] = 0.0
    if bot_data["lottery_pot"] <= 0: logger.info("Lottery pot zero."); bot_data["lottery_tickets"] = []; save_bot_data(); return
    try:
        winner_id = random.choice(bot_data["lottery_tickets"]); prize_amount = bot_data["lottery_pot"]
        winner_data = get_user_data(winner_id)
        if not isinstance(winner_data["balance"], (int, float)): winner_data["balance"] = 0
        winner_data["balance"] += prize_amount
        logger.info(f"Lottery winner: {winner_id}, Prize: {prize_amount:.2f}")
        original_pot = bot_data["lottery_pot"]
        bot_data["lottery_pot"] = 0.0; bot_data["lottery_tickets"] = []
        save_user_data(); save_bot_data()
        announce_channel = bot.get_channel(LOTTERY_ANNOUNCE_CHANNEL_ID) or await bot.fetch_channel(LOTTERY_ANNOUNCE_CHANNEL_ID)
        winner_user = bot.get_user(winner_id) or await bot.fetch_user(winner_id)
        winner_mention = winner_user.mention if winner_user else f"User ID `{winner_id}`"
        embed = disnake.Embed(title="🎉 Lottery Winner! 🎉", color=disnake.Color.gold(), timestamp=datetime.datetime.now(timezone.utc), description=f"Congrats to {winner_mention}!")
        prize_display = f"{int(original_pot):,}" if original_pot == int(original_pot) else f"{original_pot:,.2f}"
        embed.add_field(name="Prize Won", value=f"{prize_display} coins! 💰")
        embed.set_footer(text=f"Next draw in {LOTTERY_INTERVAL_HOURS} hours.")
        await announce_channel.send(content=winner_mention if winner_user else None, embed=embed, allowed_mentions=disnake.AllowedMentions(users=True if winner_user else False))
        logger.info(f"Lottery winner announced.")
    except (disnake.NotFound, disnake.Forbidden) as e: logger.error(f"Error finding/accessing lottery channel/user: {e}")
    except IndexError: logger.info("Lottery tickets empty during draw.")
    except Exception as e: logger.error(f"Error during lottery drawing: {e}", exc_info=True)
@lottery_drawing.before_loop
async def before_lottery_drawing(): await bot.wait_until_ready(); logger.info(f"Starting lottery drawing loop.")

# --- Event Handlers ---
@bot.event
async def on_ready(): # Restored one-time balance check flag logic
    logger.info(f'{bot.user} ready. Version: {disnake.__version__}')
    if PLACEHOLDER_IDS_PRESENT: logger.warning("!!! Placeholder IDs might be active.")
    load_user_data(); load_shop_items(); load_bot_data()
    if not bot_data.get("initial_balance_check_done", False):
        logger.info(f"Performing one-time check/top-up for users below {INITIAL_STARTING_BALANCE} balance...")
        updated_count = 0
        load_user_data()
        for user_id_str in list(user_data.keys()):
            try:
                user_id = int(user_id_str)
                udata = user_data[user_id]
                current_bal = udata.get("balance")
                if not isinstance(current_bal, (int, float)) or current_bal < INITIAL_STARTING_BALANCE:
                    logger.debug(f"Topping up user {user_id} from {current_bal} to {INITIAL_STARTING_BALANCE}.")
                    udata["balance"] = INITIAL_STARTING_BALANCE
                    updated_count += 1
            except (ValueError, KeyError) as e: logger.warning(f"Error processing user {user_id_str} during initial balance check: {e}")
        if updated_count > 0: logger.info(f"Topped up {updated_count} existing users to {INITIAL_STARTING_BALANCE} balance."); save_user_data()
        bot_data["initial_balance_check_done"] = True
        save_bot_data()
        logger.info("Initial balance check complete.")
    else: logger.info("Initial balance check already performed previously.")
    if not autosave_data.is_running(): autosave_data.start()
    if not lottery_drawing.is_running(): lottery_drawing.start()
    if not bot.retroactive_scan_done:
        logger.info("Starting retro scan...")
        bot.retroactive_scan_done = True; start_scan_time = time_module.time()
        total_messages_scanned = 0; user_message_counts = {}
        for guild in bot.guilds:
            logger.info(f"Scanning guild: {guild.name}")
            guild_message_count = 0; channel_scan_count = 0; skipped_channels = 0
            for channel in guild.text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.read_message_history and permissions.view_channel:
                    try:
                        async for message in channel.history(limit=SCAN_MESSAGE_LIMIT_PER_CHANNEL):
                            total_messages_scanned += 1; guild_message_count += 1
                            if not message.author.bot and message.author.id != bot.user.id:
                                user_message_counts[message.author.id] = user_message_counts.get(message.author.id, 0) + 1
                        channel_scan_count += 1
                    except Exception as e: logger.warning(f" Error scanning #{channel.name}: {e}"); skipped_channels += 1
                else: skipped_channels += 1
            logger.info(f" Scanned {guild_message_count} msgs ({channel_scan_count} channels). Skipped {skipped_channels}.")
        logger.info("Applying retroactive counts...")
        updated_user_count = 0; total_coins_added = 0
        load_user_data()
        for user_id, count in user_message_counts.items():
            if count > 0:
                udata = get_user_data(user_id)
                if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
                udata["balance"] += count; updated_user_count += 1; total_coins_added += count
        scan_duration = time_module.time() - start_scan_time
        logger.info(f"--- Retro Scan Summary ---"); logger.info(f" Duration: {scan_duration:.2f}s, Total Scanned: {total_messages_scanned}"); logger.info(f" Users Awarded: {updated_user_count}, Total Coins: {total_coins_added}"); logger.info(f"--------------------------")
        save_user_data()
    else: logger.info("Retro scan done.")
    logger.info("Bot ready.")
@bot.event
async def on_message(message: disnake.Message):
    if message.author.bot or not message.guild: return
    udata = get_user_data(message.author.id)
    if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
    udata["balance"] += 1

# --- Shop Helper Functions ---
def is_shop_open() -> bool:
    try:
        now_local = datetime.datetime.now(SHOP_TIMEZONE); current_time = now_local.time()
        if SHOP_OPEN_TIME > SHOP_CLOSE_TIME: return current_time >= SHOP_OPEN_TIME or current_time < SHOP_CLOSE_TIME
        else: return SHOP_OPEN_TIME <= current_time < SHOP_CLOSE_TIME
    except Exception as e: logger.error(f"Error checking shop open: {e}"); return False
def time_until_shop_opens() -> str:
    try:
        now_local = datetime.datetime.now(SHOP_TIMEZONE); now_time = now_local.time()
        today_open_dt = now_local.replace(hour=SHOP_OPEN_TIME.hour, minute=SHOP_OPEN_TIME.minute, second=0, microsecond=0)
        if SHOP_OPEN_TIME > SHOP_CLOSE_TIME:
            if now_time < SHOP_CLOSE_TIME: target_open_dt = today_open_dt
            elif now_time >= SHOP_OPEN_TIME: target_open_dt = today_open_dt + timedelta(days=1)
            else: target_open_dt = today_open_dt
        else:
            if now_time < SHOP_OPEN_TIME: target_open_dt = today_open_dt
            else: target_open_dt = today_open_dt + timedelta(days=1)
        delta = target_open_dt - now_local; total_seconds = int(delta.total_seconds())
        if total_seconds <= 0: return "now"
        hours, rem = divmod(total_seconds, 3600); minutes, secs = divmod(rem, 60)
        parts = [f"{x}{u[0]}" for x, u in zip([hours, minutes, secs], ['h','m','s']) if x > 0]
        if not parts: return "imminently"
        return " ".join(parts)
    except Exception as e: logger.error(f"Error calc shop time: {e}"); return "?"
async def notify_shopkeepers(interaction: disnake.Interaction, item_data: dict, payment_method: str) -> bool:
    if not interaction.guild: logger.error("notify_shopkeepers no guild context."); return False
    shopkeeper_role = interaction.guild.get_role(SHOPKEEPER_ROLE_ID)
    if not shopkeeper_role: logger.error(f"Shopkeeper role {SHOPKEEPER_ROLE_ID} not found."); await interaction.followup.send(f"Shopkeeper role not found.", ephemeral=True); return False
    buyer = interaction.user; buyer_data = get_user_data(buyer.id)
    current_balance = buyer_data.get("balance", 0);
    if not isinstance(current_balance, (int, float)): current_balance = 0
    embed = disnake.Embed(title="🛒 Shop Purchase Notification 🛒", color=disnake.Color.blue(), timestamp=datetime.datetime.now(timezone.utc), description=f"User initiated purchase in **{interaction.guild.name}**.")
    embed.add_field(name="Buyer", value=f"{buyer.mention} ({buyer.name})", inline=False)
    embed.add_field(name="Buyer ID", value=f"`{buyer.id}`", inline=False)
    embed.add_field(name="Item", value=f"{item_data.get('name','Unknown')} (ID: `{item_data.get('id','N/A')}`)", inline=False)
    embed.add_field(name="Payment Method", value=payment_method, inline=True)
    if payment_method == "Credits": embed.add_field(name="Credit Cost", value=f"{item_data.get('credit_cost', 0):,} coins", inline=True)
    elif payment_method == "USD/Other":
        usd_price = item_data.get('usd_price'); price_str = f"${usd_price:.2f}" if isinstance(usd_price, (int, float)) and usd_price > 0 else "N/A"
        embed.add_field(name="USD Price", value=price_str, inline=True)
    embed.add_field(name="Buyer's Balance", value=f"{int(current_balance):,} coins", inline=False)
    embed.set_footer(text="Coordinate with buyer.")
    success_count = 0; fail_count = 0
    shopkeepers_to_notify = [m for m in interaction.guild.members if shopkeeper_role in m.roles and not m.bot]
    if not shopkeepers_to_notify: logger.warning(f"No shopkeepers found."); await interaction.followup.send("No shopkeepers found.", ephemeral=True); return False
    logger.info(f"Notifying {len(shopkeepers_to_notify)} shopkeepers...")
    tasks = [member.send(embed=embed) for member in shopkeepers_to_notify]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception): logger.warning(f"Failed DM to {shopkeepers_to_notify[i].id}: {result}"); fail_count += 1
        else: success_count += 1
    if success_count > 0:
        logger.info(f"Notified {success_count} shopkeepers ({fail_count} failed).");
        await interaction.followup.send(f"✅ Purchase initiated for **{item_data.get('name','?')}**! {success_count} shopkeeper(s) notified.", ephemeral=False) # Public confirmation
        return True
    else:
        logger.error(f"Failed to notify any shopkeepers.");
        await interaction.followup.send("❌ Failed to notify any shopkeepers.", ephemeral=True) # Ephemeral error
        return False

# --- Shop Views ---
class PaymentMethodView(disnake.ui.View):
    def __init__(self, item_data: dict, original_user_id: int):
        super().__init__(timeout=180)
        self.item_data = item_data; self.original_user_id = original_user_id; self.payment_chosen = False
        self.pay_credits_button = disnake.ui.Button(label="Pay with Credits", style=disnake.ButtonStyle.green, custom_id="pay_credits"); self.pay_credits_button.callback = self.pay_credits_callback; self.add_item(self.pay_credits_button)
        self.pay_usd_button = disnake.ui.Button(label="Pay with USD/Other", style=disnake.ButtonStyle.blurple, custom_id="pay_usd"); self.pay_usd_button.callback = self.pay_usd_callback
        usd_price = self.item_data.get("usd_price")
        if not isinstance(usd_price, (int, float)) or usd_price <= 0: self.pay_usd_button.disabled = True; self.pay_usd_button.label = "USD Payment (N/A)"
        self.add_item(self.pay_usd_button)
    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        if interaction.user.id != self.original_user_id: await interaction.response.send_message("Not yours!", ephemeral=True); return False
        if self.payment_chosen: await interaction.response.send_message("Chosen.", ephemeral=True); return False
        return True
    async def disable_buttons(self, interaction: disnake.MessageInteraction):
        self.payment_chosen = True
        for child in self.children:
             if isinstance(child, disnake.ui.Button): child.disabled = True
        try:
             if interaction.response.is_done(): await interaction.edit_original_message(view=self)
             else: await interaction.response.edit_message(view=self)
        except Exception as e: logger.warning(f"Could not disable payment buttons: {e}")
    async def pay_credits_callback(self, interaction: disnake.MessageInteraction):
        if await self.interaction_check(interaction) is False: return
        await interaction.response.defer(ephemeral=True, with_message=False)
        user_id = interaction.user.id; udata = get_user_data(user_id)
        cost = self.item_data.get("credit_cost", 0); current_balance = udata.get("balance", 0)
        if not isinstance(current_balance, (int, float)): current_balance = 0
        if current_balance >= cost:
            logger.info(f"User {user_id} attempting buy '{self.item_data.get('name','?')}' with credits.")
            await notify_shopkeepers(interaction, self.item_data, "Credits")
            await self.disable_buttons(interaction)
        else:
            logger.info(f"User {user_id} failed buy - Insufficient credits.")
            await self.disable_buttons(interaction)
            await interaction.followup.send(f"❌ Insufficient credits ({int(current_balance):,}/{cost:,}).", ephemeral=True)
    async def pay_usd_callback(self, interaction: disnake.MessageInteraction):
        if await self.interaction_check(interaction) is False: return
        await interaction.response.defer(ephemeral=True, with_message=False)
        logger.info(f"User {interaction.user.id} attempting buy '{self.item_data.get('name','?')}' with USD.")
        usd_price = self.item_data.get("usd_price")
        if not isinstance(usd_price, (int, float)) or usd_price <= 0:
            await interaction.followup.send("❌ Item not available for USD.", ephemeral=True); await self.disable_buttons(interaction); return
        await notify_shopkeepers(interaction, self.item_data, "USD/Other")
        await self.disable_buttons(interaction)

class DynamicShopView(disnake.ui.View):
    def __init__(self): super().__init__(timeout=None); self.populate_items()
    def get_active_items(self) -> list[tuple[str, dict]]:
        load_shop_items(); active = []
        now_utc = datetime.datetime.now(timezone.utc)
        for item_id, item in shop_items.items():
             if not isinstance(item, dict) or 'name' not in item or 'credit_cost' not in item: continue
             is_expired = False
             if expires_at_str := item.get("expires_at"):
                 try:
                     expires_at_dt = datetime.datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                     if expires_at_dt.tzinfo is None: expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                     if now_utc >= expires_at_dt: is_expired = True
                 except Exception: logger.error(f"Invalid date for {item_id}")
             if not is_expired: active.append((item_id, item))
        active.sort(key=lambda i: i[1].get('name', '').lower()); return active
    def populate_items(self):
        self.clear_items(); active_items = self.get_active_items(); count = 0
        for i, (item_id, item) in enumerate(active_items, 1):
            if count >= 25: logger.warning("Max 25 shop items reached."); break
            usd_price_str = ""; credit_cost = item.get('credit_cost', 0)
            if usd_price := item.get("usd_price"):
                 if isinstance(usd_price, (int, float)) and usd_price > 0: usd_price_str = f" / ${usd_price:.2f}"
            if not isinstance(credit_cost, (int, float)): credit_cost = 0
            label = f"{i}. {item.get('name', '?')} ({int(credit_cost):,} Cr{usd_price_str})"[:80]
            button = disnake.ui.Button(label=label, style=disnake.ButtonStyle.green, custom_id=f"shop_item_{item_id}")
            button.callback = self.item_button_callback; self.add_item(button); count += 1
    async def item_button_callback(self, interaction: disnake.MessageInteraction):
        custom_id = interaction.component.custom_id
        if not custom_id or not custom_id.startswith("shop_item_"): await interaction.response.send_message("Invalid button.", ephemeral=True); return
        item_id = custom_id.split("shop_item_")[-1]
        load_shop_items(); item_data = shop_items.get(item_id)
        if not item_data: await interaction.response.send_message("Item not found.", ephemeral=True); return
        if not is_shop_open(): await interaction.response.send_message(f"Shop closed.", ephemeral=True); return
        payment_view = PaymentMethodView(item_data, interaction.user.id)
        await interaction.response.send_message(f"Pay for **{item_data.get('name','?')}**:", view=payment_view, ephemeral=True)

# --- Shop Command ---
@bot.slash_command(name="shop", description="Browse items available for purchase.")
async def shop(interaction: disnake.ApplicationCommandInteraction):
    shop_view = DynamicShopView()
    embed = disnake.Embed(title="🛒 Shop 🛒", color=disnake.Color.blurple())
    description_lines = []
    active_items = shop_view.get_active_items()
    for i, (item_id, item) in enumerate(active_items, 1):
        if i > 25: break
        name = item.get('name', '?'); cost = item.get('credit_cost', 0)
        if not isinstance(cost, (int, float)): cost = 0
        usd_price_str = ""
        if usd_price := item.get("usd_price"):
             if isinstance(usd_price, (int, float)) and usd_price > 0: usd_price_str = f" / ${usd_price:.2f}"
        description_lines.append(f"**{i}. {name}** - {int(cost):,} Cr{usd_price_str}")
    shop_status = f"Shop is currently **{'OPEN' if is_shop_open() else 'CLOSED'}**."
    if not is_shop_open(): shop_status += f"\n> Reopens in: {time_until_shop_opens()}."
    embed.description = shop_status + "\n\n" + ("\n".join(description_lines) if description_lines else "*No items available.*")
    await interaction.response.send_message(embed=embed, view=shop_view, ephemeral=False)

# --- Balance Command ---
@bot.slash_command(name="balance", description="Check your current coin balance.")
async def balance(inter: disnake.ApplicationCommandInteraction):
    udata = get_user_data(inter.author.id); current_balance = udata.get("balance", 0)
    if not isinstance(current_balance, (int, float)): current_balance = 0
    await inter.response.send_message(f"💰 Your balance: **{int(current_balance):,}** coins.", ephemeral=True)

# --- Pay Command ---
@bot.slash_command(name="pay", description="Give coins to another user.")
async def pay( inter: disnake.ApplicationCommandInteraction, user: disnake.Member, amount: int = commands.Param(gt=0) ):
    sender = inter.author; recipient = user; amount = abs(amount)
    if sender.id == recipient.id: await inter.response.send_message("❌ Cannot pay yourself!", ephemeral=True); return
    if recipient.bot: await inter.response.send_message("❌ Cannot pay bots!", ephemeral=True); return
    sender_data = get_user_data(sender.id); recipient_data = get_user_data(recipient.id)
    sender_balance = sender_data.get("balance", 0)
    if not isinstance(sender_balance, (int, float)): sender_balance = 0
    if sender_balance < amount: await inter.response.send_message(f"❌ Insufficient funds ({int(sender_balance):,}).", ephemeral=True); return
    sender_data["balance"] -= amount
    if not isinstance(recipient_data.get("balance"), (int, float)): recipient_data["balance"] = 0
    recipient_data["balance"] += amount
    save_user_data() # Save immediately
    logger.info(f"User {sender.id} paid {amount} coins to {recipient.id}.")
    await inter.response.send_message(f"💸 {sender.mention} paid **{amount:,}** coins to {recipient.mention}!", allowed_mentions=disnake.AllowedMentions(users=[sender, recipient]), ephemeral=False) # Public confirmation

# --- Admin Cog ---
class ShopAdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot
    async def cog_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if not inter.guild or not isinstance(inter.author, disnake.Member): raise commands.NoPrivateMessage("Admin needs server context.")
        is_owner = inter.author.id == inter.guild.owner_id; is_admin_channel = inter.channel_id == ADMIN_CHANNEL_ID
        if not (is_owner or is_admin_channel): raise commands.CheckFailure("Owner or Admin Channel required.")
        return True
    async def cog_command_error(self, inter: disnake.ApplicationCommandInteraction, error: commands.CommandError):
        if isinstance(error, (commands.CheckFailure, commands.UserInputError, commands.NoPrivateMessage)): msg = str(error)
        else: logger.error(f"Admin Cog Error: {error}", exc_info=True); msg = "Unexpected admin error.";
        try:
            if not inter.response.is_done(): await inter.response.send_message(msg, ephemeral=True)
            else: await inter.followup.send(msg, ephemeral=True)
        except Exception: pass

    @commands.slash_command(name="shopadmin", description="Manage shop items.")
    async def shopadmin(self, inter: disnake.ApplicationCommandInteraction): pass
    @shopadmin.sub_command(name="list", description="List all shop items.")
    async def shopadmin_list(self, inter: disnake.ApplicationCommandInteraction):
        load_shop_items();
        if not shop_items: await inter.response.send_message("No items.", ephemeral=True); return
        embeds = []; current_desc = ""; items_in_page = 0; max_items = 5
        now_utc = datetime.datetime.now(timezone.utc)
        for item_id, item in sorted(shop_items.items(), key=lambda i: i[1].get('name', '').lower()):
             if items_in_page >= max_items or len(current_desc) > 3800:
                  if current_desc: embeds.append(disnake.Embed(description=current_desc, color=disnake.Color.orange()))
                  current_desc = ""; items_in_page = 0
             if not isinstance(item, dict): line = f"**Invalid:** ID:`{item_id}`\n"; items_in_page+=1; current_desc += line; continue
             name = item.get('name', '?'); cost = item.get('credit_cost', '?'); usd = item.get('usd_price', None)
             cost_str = f"{int(cost):,}" if isinstance(cost, (int, float)) else str(cost)
             usd_str = f" / ${usd:.2f}" if isinstance(usd, (int, float)) and usd > 0 else ""
             by = f" (By:`{item.get('added_by')}`)" if item.get('added_by') else ""
             expires = "Never"; is_expired = False
             if exp_str := item.get("expires_at"):
                 try:
                     exp_dt = datetime.datetime.fromisoformat(exp_str.replace('Z', '+00:00'))
                     if exp_dt.tzinfo is None: exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                     if now_utc >= exp_dt: is_expired = True; expires = f"Expired <t:{int(exp_dt.timestamp())}:R>"
                     else: expires = f"Expires <t:{int(exp_dt.timestamp())}:R>"
                 except Exception: expires = f"Invalid Date ({exp_str})"
             status = " [EXPIRED]" if is_expired else ""
             line = f"**{name}**{status}\n> ID: `{item_id}`\n> Cost: `{cost_str}` Cr{usd_str}\n> Expires: {expires}{by}\n\n"
             current_desc += line; items_in_page += 1
        if current_desc: embeds.append(disnake.Embed(description=current_desc, color=disnake.Color.orange()))
        if not embeds: await inter.response.send_message("No items found.", ephemeral=True); return
        for i, embed in enumerate(embeds): embed.title = f"Shop Items (Page {i+1}/{len(embeds)})"
        await inter.response.send_message(embed=embeds[0], ephemeral=True)
    @shopadmin.sub_command(name="remove", description="Remove an item.")
    async def shopadmin_remove(self, inter: disnake.ApplicationCommandInteraction, item_id: str):
        item_id = item_id.strip(); load_shop_items()
        if item_id in shop_items:
            name = shop_items[item_id].get('name', '?'); del shop_items[item_id]; save_shop_items()
            logger.info(f"Admin {inter.author} removed item '{name}' ({item_id})")
            await inter.response.send_message(f"✅ Removed '{name}'.", ephemeral=True)
        else: await inter.response.send_message(f"❌ ID `{item_id}` not found.", ephemeral=True)
    class ShopAddItemModal(disnake.ui.Modal):
        def __init__(self):
            components = [ disnake.ui.TextInput(label="Name", placeholder="Item Name", custom_id="item_name", max_length=100, required=True),
                           disnake.ui.TextInput(label="Credit Cost", placeholder="e.g., 1000", custom_id="item_credit_cost", max_length=15, required=True),
                           disnake.ui.TextInput(label="USD Price (Optional)", placeholder="e.g., 5.00 (0=none)", custom_id="item_usd_price", required=False),
                           disnake.ui.TextInput(label="Duration (Optional)", placeholder="7d, 24h, 30m, never", custom_id="item_duration", required=False),
                           disnake.ui.TextInput(label="Unique ID (Optional)", placeholder="Auto if blank", custom_id="item_unique_id", required=False) ]
            super().__init__(title="Add Shop Item", components=components, custom_id="shop_add_item_modal")
        async def callback(self, inter: disnake.ModalInteraction):
            await inter.response.defer(ephemeral=True); load_shop_items()
            name = inter.text_values["item_name"].strip(); cost_str = inter.text_values["item_credit_cost"].strip()
            usd_str = inter.text_values["item_usd_price"].strip(); dur_str = inter.text_values["item_duration"].strip().lower()
            custom_id = inter.text_values["item_unique_id"].strip()
            try: cost = int(cost_str); assert cost >= 0
            except Exception: await inter.followup.send("❌ Invalid Credit Cost.", ephemeral=True); return
            usd = None
            if usd_str:
                try: usd = float(usd_str); assert usd >= 0; usd = None if usd == 0 else usd
                except Exception: await inter.followup.send("❌ Invalid USD Price.", ephemeral=True); return
            expires = None
            if dur_str and dur_str != "never":
                try:
                    num_str = "".join(filter(str.isdigit, dur_str)); unit = "".join(filter(str.isalpha, dur_str)).lower()
                    num = int(num_str); assert num > 0
                    if unit == 'd': delta = timedelta(days=num)
                    elif unit == 'h': delta = timedelta(hours=num)
                    elif unit == 'm': delta = timedelta(minutes=num)
                    else: raise ValueError(f"Invalid unit '{unit}'")
                    expires = datetime.datetime.now(timezone.utc) + delta
                except Exception as e: await inter.followup.send(f"❌ Invalid Duration: {e}.", ephemeral=True); return
            if custom_id:
                if not custom_id.isalnum(): await inter.followup.send("❌ Custom ID Alphanum only.", ephemeral=True); return
                if custom_id in shop_items: await inter.followup.send(f"❌ Custom ID exists.", ephemeral=True); return
                uid = custom_id
            else:
                for _ in range(5):
                    uid = uuid.uuid4().hex[:8]
                    if uid not in shop_items: break
                else: await inter.followup.send(f"❌ Auto ID fail.", ephemeral=True); return
            item = {"id": uid, "name": name, "credit_cost": cost, "usd_price": usd,
                    "expires_at": expires.isoformat(timespec='seconds').replace('+00:00', 'Z') if expires else None,
                    "added_by": inter.author.id, "added_at": datetime.datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z') }
            shop_items[uid] = item; save_shop_items()
            logger.info(f"Admin {inter.author} added item '{name}' ({uid})")
            await inter.followup.send(f"✅ Added **{name}** (`{uid}`).", ephemeral=True)
    @shopadmin.sub_command(name="add", description="Add item via modal.")
    async def shopadmin_add(self, inter: disnake.ApplicationCommandInteraction):
        modal = self.ShopAddItemModal(); await inter.response.send_modal(modal)

    @commands.slash_command(name="admincoins", description="Manage coins.")
    async def admincoins(self, inter: disnake.ApplicationCommandInteraction): pass
    @admincoins.sub_command(name="give", description="Give coins.")
    async def admincoins_give(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member, amount: int = commands.Param(ge=1)):
        if user.bot: await inter.response.send_message("❌ Cannot mod bot.", ephemeral=True); return
        udata = get_user_data(user.id);
        if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
        udata["balance"] += amount
        logger.info(f"Admin {inter.author} gave {amount} to {user.id}.")
        save_user_data()
        await inter.response.send_message(f"✅ Gave {amount:,} to {user.mention}. Bal: {int(udata['balance']):,}.", ephemeral=True, allowed_mentions=disnake.AllowedMentions.none())
    @admincoins.sub_command(name="take", description="Take coins.")
    async def admincoins_take(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member, amount: int = commands.Param(ge=1)):
        if user.bot: await inter.response.send_message("❌ Cannot mod bot.", ephemeral=True); return
        udata = get_user_data(user.id);
        if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
        original = udata["balance"]; taken = min(amount, original)
        udata["balance"] -= taken
        logger.info(f"Admin {inter.author} took {taken} from {user.id}.")
        save_user_data()
        await inter.response.send_message(f"✅ Took {taken:,} from {user.mention}. Bal: {int(udata['balance']):,}.", ephemeral=True, allowed_mentions=disnake.AllowedMentions.none())
    @admincoins.sub_command(name="set", description="Set balance.")
    async def admincoins_set(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member, amount: int = commands.Param(ge=0)):
        if user.bot: await inter.response.send_message("❌ Cannot mod bot.", ephemeral=True); return
        udata = get_user_data(user.id); udata["balance"] = amount
        logger.info(f"Admin {inter.author} set {user.id}'s bal to {amount}.")
        save_user_data()
        await inter.response.send_message(f"✅ Set {user.mention}'s bal to {amount:,}.", ephemeral=True, allowed_mentions=disnake.AllowedMentions.none())
    @admincoins.sub_command(name="setjackpot", description="Set jackpot pool amount.")
    async def admincoins_setjackpot(self, inter: disnake.ApplicationCommandInteraction, amount: float = commands.Param(ge=0.0)):
        load_bot_data()
        if 'slot_jackpot_pool' not in bot_data or not isinstance(bot_data['slot_jackpot_pool'], float): bot_data['slot_jackpot_pool'] = 0.0
        bot_data["slot_jackpot_pool"] = float(amount)
        save_bot_data()
        logger.info(f"Admin {inter.author} set jackpot pool to {amount:.2f}.")
        await inter.response.send_message(f"✅ Set jackpot to {amount:,.2f}.", ephemeral=True)
    @admincoins.sub_command(name="setjackpotcontribution", description="Set % of slot loss added to jackpot (0-100).")
    async def admincoins_setjackpotcontribution(self, inter: disnake.ApplicationCommandInteraction, percentage: float = commands.Param(ge=0.0, le=100.0)):
        load_bot_data(); new_rate = percentage / 100.0
        bot_data["slot_jackpot_contribution"] = new_rate; save_bot_data()
        logger.info(f"Admin {inter.author} set jackpot contribution rate to {new_rate:.1%}.")
        await inter.response.send_message(f"✅ Set jackpot contribution rate to **{percentage:.1f}%**.", ephemeral=True)
    @admincoins.sub_command(name="setjackpotchance", description="Set % override chance for jackpot win (0=off).")
    async def admincoins_setjackpotchance(self, inter: disnake.ApplicationCommandInteraction, percentage: float = commands.Param(ge=0.0, le=100.0)):
        load_bot_data(); new_override_rate = percentage / 100.0
        bot_data["slot_jackpot_override_chance"] = new_override_rate; save_bot_data()
        logger.info(f"Admin {inter.author} set jackpot override chance to {new_override_rate:.1%}.")
        if new_override_rate > 0: await inter.response.send_message(f"✅ Set jackpot override chance to **{percentage:.1f}%**.", ephemeral=True)
        else: await inter.response.send_message(f"✅ Disabled jackpot override chance.", ephemeral=True)

    # --- Manual Economy Reset Command ---
    class ConfirmResetView(disnake.ui.View):
        def __init__(self, original_inter: disnake.ApplicationCommandInteraction):
            super().__init__(timeout=60.0)
            self.original_inter = original_inter
            self.confirmed = False
        async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
            if interaction.user.id != self.original_inter.author.id:
                await interaction.response.send_message("Not your button!", ephemeral=True); return False
            return True
        @disnake.ui.button(label="CONFIRM RESET", style=disnake.ButtonStyle.danger, custom_id="confirm_reset")
        async def confirm_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.confirmed = True
            button.disabled = True; self.cancel_button.disabled = True
            await interaction.response.edit_message(content="✅ Reset confirmed. Performing economy reset...", view=self)
            self.stop()
        @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.secondary, custom_id="cancel_reset")
        async def cancel_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            self.confirmed = False
            button.disabled = True; self.confirm_button.disabled = True
            await interaction.response.edit_message(content="❌ Economy reset cancelled.", view=self)
            self.stop()
        async def on_timeout(self):
             try:
                 message = await self.original_inter.original_message()
                 if message:
                    for item in self.children: item.disabled = True
                    await message.edit(content="⌛ Economy reset confirmation timed out.", view=self)
             except (disnake.NotFound, disnake.HTTPException): pass

    @commands.slash_command(name="reseteconomy", description="[DANGEROUS] Reset all user balances/savings and pools.")
    async def reseconomy(self, inter: disnake.ApplicationCommandInteraction):
        view = self.ConfirmResetView(inter)
        await inter.response.send_message(
            "**⚠️ ARE YOU ABSOLUTELY SURE? ⚠️**\n"
            f"Reset ALL user balances to **{INITIAL_STARTING_BALANCE:,}**, clear savings, reset pools.\n"
            "**THIS CANNOT BE UNDONE.** Confirm within 60 seconds.",
            view=view, ephemeral=True
        )
        await view.wait()
        if view.confirmed:
             await perform_economy_reset(triggered_by=f"Manual command by {inter.author}") # Use helper
             await inter.followup.send("✅ Economy reset complete.", ephemeral=True)

# --- Savings Account Commands ---
@bot.slash_command(name="savings", description="Manage savings.")
async def savings_base(inter: disnake.ApplicationCommandInteraction): pass
@savings_base.sub_command(name="codeset", description="Set/reset 4-digit PIN.")
async def savings_codeset(inter: disnake.ApplicationCommandInteraction, pin: str = commands.Param(min_length=4, max_length=4)):
    pin = pin.strip()
    if not pin.isdigit(): await inter.response.send_message("❌ PIN must be 4 digits.", ephemeral=True); return
    udata = get_user_data(inter.author.id); old = udata.get("pin"); udata["pin"] = pin
    msg = "reset" if old else "set"; logger.info(f"User {inter.author} {msg} PIN.")
    save_user_data(); await inter.response.send_message(f"✅ PIN {msg}.", ephemeral=True)
@savings_base.sub_command(name="balance", description="Check savings balance.")
async def savings_balance(inter: disnake.ApplicationCommandInteraction, pin: str = commands.Param(min_length=4, max_length=4)):
    pin = pin.strip(); udata = get_user_data(inter.author.id)
    if udata.get("pin") is None: await inter.response.send_message("❌ No PIN set.", ephemeral=True); return
    if udata.get("pin") != pin: await inter.response.send_message("❌ Incorrect PIN.", ephemeral=True); return
    bal = udata.get('savings', 0);
    if not isinstance(bal, (int, float)): bal = 0
    await inter.response.send_message(f"💰 Savings: {int(bal):,} coins.", ephemeral=True)
@savings_base.sub_command(name="deposit", description="Deposit to savings.")
async def savings_deposit(inter: disnake.ApplicationCommandInteraction, amount: int = commands.Param(gt=0), pin: str = commands.Param(min_length=4, max_length=4)):
    pin = pin.strip(); udata = get_user_data(inter.author.id)
    if udata.get("pin") is None: await inter.response.send_message("❌ No PIN set.", ephemeral=True); return
    if udata.get("pin") != pin: await inter.response.send_message("❌ Incorrect PIN.", ephemeral=True); return
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if not isinstance(udata.get("savings"), (int, float)): udata["savings"] = 0
    if udata["balance"] < amount: await inter.response.send_message(f"❌ Insufficient funds.", ephemeral=True); return
    udata["balance"] -= amount; udata["savings"] += amount
    logger.info(f"User {inter.author} deposited {amount}.")
    save_user_data(); await inter.response.send_message(f"✅ Deposited {amount:,}.\nSav: {int(udata['savings']):,}, Bal: {int(udata['balance']):,}", ephemeral=True)
@savings_base.sub_command(name="withdraw", description="Withdraw from savings.")
async def savings_withdraw(inter: disnake.ApplicationCommandInteraction, amount: int = commands.Param(gt=0), pin: str = commands.Param(min_length=4, max_length=4)):
    pin = pin.strip(); udata = get_user_data(inter.author.id)
    if udata.get("pin") is None: await inter.response.send_message("❌ No PIN set.", ephemeral=True); return
    if udata.get("pin") != pin: await inter.response.send_message("❌ Incorrect PIN.", ephemeral=True); return
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if not isinstance(udata.get("savings"), (int, float)): udata["savings"] = 0
    if udata["savings"] < amount: await inter.response.send_message(f"❌ Insufficient savings.", ephemeral=True); return
    udata["savings"] -= amount; udata["balance"] += amount
    logger.info(f"User {inter.author} withdrew {amount}.")
    save_user_data(); await inter.response.send_message(f"✅ Withdrew {amount:,}.\nSav: {int(udata['savings']):,}, Bal: {int(udata['balance']):,}", ephemeral=True)

# --- Gambling Commands ---
@bot.slash_command(name="gamble", description="Try your luck!")
async def gamble_base(inter: disnake.ApplicationCommandInteraction): pass
@gamble_base.sub_command(name="slots", description="Spin the slot machine!")
async def gamble_slots(inter: disnake.ApplicationCommandInteraction, amount: int = commands.Param(ge=1)):
    user_id = inter.author.id; udata = get_user_data(user_id)
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if udata["balance"] < amount: await inter.response.send_message(f"❌ Insufficient balance.", ephemeral=True); return
    await inter.response.defer(ephemeral=False)
    load_bot_data(); udata["balance"] -= amount
    initial_embed = disnake.Embed(title=f"🎰 {inter.author.display_name}'s Spin 🎰", description="❓ ❓ ❓", color=disnake.Color.dark_gold()).set_footer(text=f"Bet: {amount:,}")
    try: await inter.edit_original_message(embed=initial_embed)
    except Exception as e: logger.warning(f"Slots init fail: {e}"); udata["balance"] += amount; save_user_data(); await inter.followup.send("Error starting slots.", ephemeral=True); return
    spin_count = random.randint(4, 7); final_reels = [random.choice(SLOT_EMOJIS) for _ in range(3)]
    for i in range(spin_count):
        display_reels = [random.choice(SLOT_EMOJIS) for _ in range(3)] if i < spin_count - 1 else final_reels
        spin_embed = disnake.Embed(title=f"🎰 {inter.author.display_name}'s Spin 🎰", description=" ".join(display_reels), color=disnake.Color.dark_gold()).set_footer(text=f"Bet: {amount:,} | Spinning...")
        try: await inter.edit_original_message(embed=spin_embed); await asyncio.sleep(0.6 - i*0.07)
        except Exception: break
    reels = final_reels; result_embed = disnake.Embed(title=f"🎰 {inter.author.display_name}'s Result 🎰", description=" ".join(reels)).set_footer(text=f"Bet: {amount:,}")
    winnings = 0; payout_desc = ""; jackpot_hit = False; is_loss = False; override_win = False
    if not isinstance(bot_data.get("slot_jackpot_pool"), float): bot_data["slot_jackpot_pool"] = 0.0
    jackpot_pool = bot_data["slot_jackpot_pool"]
    contribution_rate = bot_data.get("slot_jackpot_contribution", DEFAULT_SLOT_JACKPOT_CONTRIBUTION)
    override_chance = bot_data.get("slot_jackpot_override_chance", DEFAULT_SLOT_JACKPOT_OVERRIDE_CHANCE)
    if not isinstance(contribution_rate, float) or not (0.0 <= contribution_rate <= 1.0): contribution_rate = DEFAULT_SLOT_JACKPOT_CONTRIBUTION
    if not isinstance(override_chance, float) or not (0.0 <= override_chance <= 1.0): override_chance = DEFAULT_SLOT_JACKPOT_OVERRIDE_CHANCE
    natural_win = False
    if reels[0] == reels[1] == reels[2]:
        if reels[0] == SLOT_JACKPOT_EMOJI: winnings = amount + (jackpot_pool * 0.50); bot_data["slot_jackpot_pool"] *= 0.50; payout_desc = f"🎉 **JACKPOT!** Won **{winnings:,.2f}**!"; result_embed.color = disnake.Color.gold(); jackpot_hit = True; natural_win = True
        else: winnings = amount * 10; payout_desc = f"💰 3 of a kind! Won **{winnings:,}**!"; result_embed.color = disnake.Color.green(); natural_win = True
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]: winnings = amount * 2; payout_desc = f"👍 Pair! Won **{winnings:,}**!"; result_embed.color = disnake.Color.blue(); natural_win = True
    if not natural_win:
        if override_chance > 0 and random.random() < override_chance: winnings = amount + (jackpot_pool * 0.50); bot_data["slot_jackpot_pool"] *= 0.50; payout_desc = f"🎉 **JACKPOT!** Won **{winnings:,.2f}**!"; result_embed.color = disnake.Color.gold(); jackpot_hit = True; override_win = True
        else: is_loss = True
    if is_loss and not override_win:
        contribution = amount * contribution_rate; bot_data["slot_jackpot_pool"] += contribution
        payout_desc = f"😥 Lost. {contribution:,.2f} ({contribution_rate:.0%}) added to jackpot."; result_embed.color = disnake.Color.red()
    if not isinstance(winnings, (int, float)): winnings = 0
    udata["balance"] += winnings
    if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
    result_embed.add_field(name="Result", value=payout_desc, inline=False)
    result_embed.add_field(name="Your New Balance", value=f"{int(udata['balance']):,} coins", inline=True)
    result_embed.add_field(name="Jackpot Pool", value=f"{bot_data['slot_jackpot_pool']:,.2f} coins", inline=True)
    logger.info(f"User {user_id} slots. Bet:{amount}, Win:{winnings:.2f}, Override:{override_win}")
    save_bot_data(); save_user_data()
    await announce_big_win(inter, inter.author, winnings, "Slots")
    await inter.edit_original_message(embed=result_embed)
@gamble_base.sub_command(name="dice", description="Guess the roll of a 6-sided die.")
async def gamble_dice(inter: disnake.ApplicationCommandInteraction, guess: int = commands.Param(ge=1, le=6), amount: int = commands.Param(ge=1)):
    user_id = inter.author.id; udata = get_user_data(user_id)
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if udata["balance"] < amount: await inter.response.send_message(f"❌ Insufficient balance.", ephemeral=True); return
    await inter.response.defer(ephemeral=False)
    udata["balance"] -= amount; roll = random.randint(1, 6); dice_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"][roll-1]
    result = disnake.Embed(title=f"🎲 {inter.author.display_name} rolled Dice!", footer=f"Bet:{amount:,}|Guess:{guess}", description=f"Rolled: {dice_emoji}")
    winnings = 0
    if guess == roll: winnings = amount * DICE_WIN_MULTIPLIER; udata["balance"] += winnings; result.add_field(name="Result", value=f"🎉 Correct! Won **{winnings:,}**!", inline=False); result.color = disnake.Color.green()
    else: result.add_field(name="Result", value=f"😥 Incorrect (was {roll}).", inline=False); result.color = disnake.Color.red()
    if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
    result.add_field(name="Your New Balance", value=f"{int(udata['balance']):,} coins", inline=False)
    logger.info(f"User {user_id} dice. Bet:{amount}, Guess:{guess}, Roll:{roll}")
    save_user_data()
    await announce_big_win(inter, inter.author, winnings, "Dice")
    await inter.edit_original_message(embed=result)
@gamble_base.sub_command(name="redblack", description="Bet red (even) or black (odd).")
@commands.cooldown(1, REDBLACK_COOLDOWN_SECONDS, commands.BucketType.user)
async def gamble_redblack(inter: disnake.ApplicationCommandInteraction, choice: str = commands.Param(choices=["red", "black"]), amount: int = commands.Param(ge=1)):
    user_id = inter.author.id; udata = get_user_data(user_id)
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if udata["balance"] < amount: inter.application_command.reset_cooldown(inter); await inter.response.send_message(f"❌ Insufficient balance.", ephemeral=True); return
    await inter.response.defer(ephemeral=False)
    udata["balance"] -= amount; roll = random.randint(1, 36); is_red = (roll % 2 == 0)
    color = "Red" if is_red else "Black"; emoji = "🔴" if is_red else "⚫"
    result = disnake.Embed(title=f"{emoji} {inter.author.display_name} played Red/Black!", footer=f"Bet:{amount:,}|Choice:{choice.capitalize()}", description=f"Rolled: **{roll}** ({color})")
    winnings = 0; match = (choice == "red" and is_red) or (choice == "black" and not is_red)
    if match: winnings = int(amount*REDBLACK_WIN_MULTIPLIER); udata["balance"] += winnings; result.add_field(name="Result", value=f"🎉 Correct! Won **{winnings:,}**!", inline=False); result.color = disnake.Color.red() if is_red else disnake.Color.black()
    else: result.add_field(name="Result", value=f"😥 Incorrect (was {color}).", inline=False); result.color = disnake.Color.dark_grey()
    if not isinstance(udata["balance"], (int, float)): udata["balance"] = 0
    result.add_field(name="Your New Balance", value=f"{int(udata['balance']):,} coins", inline=False)
    logger.info(f"User {user_id} R/B. Bet:{amount}, Choice:{choice}, Roll:{roll}({color})")
    save_user_data()
    await announce_big_win(inter, inter.author, winnings, "Red/Black")
    await inter.edit_original_message(embed=result)
@gamble_redblack.error
async def redblack_error(inter: disnake.ApplicationCommandInteraction, error):
    msg = None
    if isinstance(error, commands.CommandOnCooldown): msg = f"⏳ Cooldown {error.retry_after:.1f}s."
    elif isinstance(error, commands.UserInputError): msg = f"Invalid input: {error}"
    else: logger.error(f"Error in redblack: {error}", exc_info=True); msg = "Unexpected error."
    try:
        if not inter.response.is_done(): await inter.response.send_message(msg, ephemeral=True)
        else: await inter.followup.send(msg, ephemeral=True)
    except Exception as e: logger.error(f"Failed R/B error response: {e}")

# --- Lottery Commands ---
@bot.slash_command(name="lottery", description="Coin lottery.")
async def lottery_base(inter: disnake.ApplicationCommandInteraction): pass
@lottery_base.sub_command(name="buy", description="Buy lottery tickets.")
async def lottery_buy(inter: disnake.ApplicationCommandInteraction, tickets: int = commands.Param(ge=1, default=1)):
    user_id = inter.author.id; udata = get_user_data(user_id); load_bot_data()
    cost = LOTTERY_TICKET_PRICE * tickets
    if not isinstance(udata.get("balance"), (int, float)): udata["balance"] = 0
    if not isinstance(bot_data.get("lottery_pot"), (int, float)): bot_data["lottery_pot"] = 0.0
    if not isinstance(bot_data.get("lottery_tickets"), list): bot_data["lottery_tickets"] = []
    if udata["balance"] < cost: await inter.response.send_message(f"❌ Need {cost:,}, have {int(udata['balance']):,}.", ephemeral=True); return
    udata["balance"] -= cost; bot_data["lottery_pot"] += cost; bot_data["lottery_tickets"].extend([user_id] * tickets)
    logger.info(f"User {user_id} bought {tickets} tickets for {cost}.")
    save_bot_data(); save_user_data()
    await inter.response.send_message(f"🎟️ Bought {tickets} ticket(s) for {cost:,}!\nBal: {int(udata['balance']):,}, Pot: {bot_data['lottery_pot']:,.2f}", ephemeral=True)
@lottery_base.sub_command(name="info", description="Show lottery info.")
async def lottery_info(inter: disnake.ApplicationCommandInteraction):
    load_bot_data(); pot = bot_data.get('lottery_pot', 0.0); tickets = bot_data.get('lottery_tickets', [])
    if not isinstance(pot, (int, float)): pot = 0.0
    if not isinstance(tickets, list): tickets = []
    count = len(tickets); next_draw = "Not scheduled"
    if lottery_drawing.is_running():
        next_dt = lottery_drawing.next_iteration
        if next_dt:
             if next_dt.tzinfo is None: next_dt = next_dt.replace(tzinfo=timezone.utc)
             now = datetime.datetime.now(timezone.utc); delta = next_dt - now
             if delta.total_seconds() > 0:
                 secs = int(delta.total_seconds()); h, r = divmod(secs, 3600); m, s = divmod(r, 60)
                 parts = [f"{x}{u}" for x, u in zip([h, m, s], ['h', 'm', 's']) if x > 0]
                 next_draw = f"in {' '.join(parts) or 'soon'} (<t:{int(next_dt.timestamp())}:R>)"
             else: next_draw = "Drawing soon!"
        else: next_draw = "Calculating..."
    embed = disnake.Embed(title="🎟️ Lottery Info 🎟️", color=disnake.Color.gold())
    embed.add_field(name="Pot", value=f"{pot:,.2f} 💰", inline=True); embed.add_field(name="Tickets", value=f"{count:,}", inline=True)
    embed.add_field(name="Price", value=f"{LOTTERY_TICKET_PRICE:,}", inline=True); embed.add_field(name="Next Draw", value=next_draw, inline=False)
    await inter.response.send_message(embed=embed, ephemeral=False)

# --- Role Checks ---
def check_role(interaction: disnake.Interaction | disnake.Message, role_id: int) -> bool:
    if isinstance(interaction, disnake.Interaction): guild = interaction.guild; author = interaction.author
    elif isinstance(interaction, disnake.Message): guild = interaction.guild; author = interaction.author
    else: return False
    if not guild or not isinstance(author, disnake.Member): return False
    if role := guild.get_role(role_id): return role in author.roles
    return False
def is_supporter(interaction: disnake.Interaction | disnake.Message) -> bool:
    if not check_role(interaction, SUPPORTER_ROLE_ID): raise commands.CheckFailure(f"Supporter role required.")
    return True
def is_vip(interaction: disnake.Interaction | disnake.Message) -> bool:
    if not check_role(interaction, VIP_ROLE_ID): raise commands.CheckFailure(f"VIP role required.")
    return True

# --- Supporter Commands ---
@bot.slash_command(name="supporter", description="Supporter commands.")
async def supporter_base(inter: disnake.ApplicationCommandInteraction): pass
@supporter_base.sub_command(name="nickname", description="Change nickname (Supporter Perk).")
@commands.check(is_supporter)
async def supporter_nickname(inter: disnake.ApplicationCommandInteraction, new_nickname: str = commands.Param(default=None, max_length=32)):
    if not isinstance(inter.author, disnake.Member): await inter.response.send_message("Error: Member info.", ephemeral=True); return
    if not inter.guild.me.guild_permissions.manage_nicknames: await inter.response.send_message("❌ Bot lacks perm.", ephemeral=True); return
    if inter.author.top_role >= inter.guild.me.top_role: await inter.response.send_message("❌ Bot role too low.", ephemeral=True); return
    try:
        nick = new_nickname.strip() if new_nickname else None
        if nick and len(nick) == 0 : nick = None
        await inter.author.edit(nick=nick, reason=f"Supporter perk")
        if nick: logger.info(f"Supporter {inter.author} set nick."); await inter.response.send_message(f"✅ Nickname changed.", ephemeral=True)
        else: logger.info(f"Supporter {inter.author} reset nick."); await inter.response.send_message("✅ Nickname reset.", ephemeral=True)
    except Exception as e: logger.error(f"Nickname fail: {e}"); await inter.response.send_message(f"❌ Nickname change failed.", ephemeral=True)
@supporter_base.error
async def supporter_error(inter: disnake.ApplicationCommandInteraction, error):
    msg = "Supporter cmd error.";
    if isinstance(error, commands.CheckFailure): msg = str(error)
    else: logger.error(f"Supporter Error: {error}", exc_info=True)
    try:
        if not inter.response.is_done(): await inter.response.send_message(msg, ephemeral=True)
        else: await inter.followup.send(msg, ephemeral=True)
    except Exception: pass

# --- VIP Commands ---
@bot.slash_command(name="vip", description="VIP commands.")
async def vip_base(inter: disnake.ApplicationCommandInteraction): pass
@vip_base.sub_command(name="embed", description="Send message in embed (VIP Perk).")
@commands.check(is_vip)
async def vip_embed(inter: disnake.ApplicationCommandInteraction, message: str = commands.Param(max_length=2000)):
    if not inter.channel.permissions_for(inter.guild.me).send_messages or not inter.channel.permissions_for(inter.guild.me).embed_links:
        await inter.response.send_message("❌ Bot lacks perms here.", ephemeral=True); return
    embed = disnake.Embed(description=message, color=disnake.Color.purple())
    name = inter.author.display_name if isinstance(inter.author, disnake.Member) else inter.author.name
    avatar = inter.author.display_avatar.url if inter.author.display_avatar else None
    embed.set_author(name=f"{name} (VIP)", icon_url=avatar)
    try:
        await inter.channel.send(embed=embed); logger.info(f"VIP {inter.author} sent embed.")
        await inter.response.send_message("✅ Embed sent!", ephemeral=True)
    except Exception as e: logger.error(f"VIP embed fail: {e}"); await inter.response.send_message("❌ Embed send failed.", ephemeral=True)
@vip_base.error
async def vip_error(inter: disnake.ApplicationCommandInteraction, error):
    msg = "VIP cmd error.";
    if isinstance(error, commands.CheckFailure): msg = str(error)
    else: logger.error(f"VIP Error: {error}", exc_info=True)
    try:
        if not inter.response.is_done(): await inter.response.send_message(msg, ephemeral=True)
        else: await inter.followup.send(msg, ephemeral=True)
    except Exception: pass

# --- Custom Help Command ---
@bot.slash_command(name="help", description="Shows available commands.")
async def help_command(inter: disnake.ApplicationCommandInteraction):
    await inter.response.defer(ephemeral=True)
    try:
        embeds = []; base = disnake.Embed(title=f"{bot.user.name} Help", color=disnake.Color.blurple()).set_footer(text="<> required, [] optional.")
        cmap = {}; pgroups = set();
        def fmt_params(opts: list[disnake.Option]) -> str: return " ".join([f"<{o.name}>" if o.required else f"[{o.name}]" for o in sorted(opts, key=lambda o: not o.required)])
        is_server_admin = False
        if inter.guild and isinstance(inter.author, disnake.Member): is_server_admin = inter.author.guild_permissions.administrator
        for cmd in bot.slash_commands:
            name = cmd.name;
            if hasattr(cmd, 'parent') and cmd.parent and name in pgroups: continue
            if name == "help": continue # Skip help itself
            cat = "General"; adm = False; sup = False; vip = False
            if isinstance(cmd.cog, ShopAdminCog): cat = "Admin"; adm = True
            elif name == "shop": cat = "Shop"
            elif name == "savings": cat = "Savings"
            elif name == "gamble": cat = "Gambling"
            elif name == "lottery": cat = "Lottery"
            elif name == "supporter": cat = "Supporter Perks"; sup = True
            elif name == "vip": cat = "VIP Perks"; vip = True
            elif name == "balance": cat = "Money"
            elif name == "pay": cat = "Money"
            else: cat = "Money"
            if cat not in cmap: cmap[cat] = []
            if hasattr(cmd, 'children') and cmd.children:
                pgroups.add(name)
                for sub_cmd in cmd.children.values():
                    if isinstance(sub_cmd, commands.InvokableSlashCommand):
                        ps = fmt_params(sub_cmd.options); s = f"</{name} {sub_cmd.name} {ps}>".strip()
                        sub_cat = cat; sub_adm = adm; sub_sup = sup; sub_vip = vip
                        if sub_cat not in cmap: cmap[sub_cat] = []
                        cmap[sub_cat].append({"cmd_string": s, "description": sub_cmd.description or "...", "admin": sub_adm, "supporter": sub_sup, "vip": sub_vip })
            elif isinstance(cmd, commands.InvokableSlashCommand):
                if hasattr(cmd, 'parent') and cmd.parent and cmd.parent.name in pgroups: continue
                ps = fmt_params(cmd.options); s = f"</{name} {ps}>".strip()
                cmap[cat].append({"cmd_string": s, "description": cmd.description or "...", "admin": adm, "supporter": sup, "vip": vip })
        order = ["Money", "Savings", "Gambling", "Lottery", "Shop", "Supporter Perks", "VIP Perks", "Admin", "General"]
        is_admin_context = False
        if not is_server_admin and inter.guild and isinstance(inter.author, disnake.Member): is_admin_context = (inter.author.id == inter.guild.owner_id or inter.channel_id == ADMIN_CHANNEL_ID)
        is_sup = check_role(inter, SUPPORTER_ROLE_ID); is_vip = check_role(inter, VIP_ROLE_ID); accessible_count = 0
        for cat in order:
            if cat in cmap:
                acc_cmds = []
                for info in sorted(cmap[cat], key=lambda c: c['cmd_string']):
                    can_access = True
                    if not is_server_admin: # Apply checks only if not server admin
                        if info["admin"] and not is_admin_context: can_access = False
                        if info["supporter"] and not is_sup: can_access = False
                        if info["vip"] and not is_vip: can_access = False
                    if can_access: acc_cmds.append(f"`{info['cmd_string']}`\n{info['description']}")
                if acc_cmds:
                    accessible_count += 1; cat_embed = disnake.Embed(title=f"**{cat}**", color=disnake.Color.blurple())
                    val = "\n\n".join(acc_cmds)
                    if len(val) > 4096:
                         parts = [val[i:i+4000] for i in range(0, len(val), 4000)]
                         for i, p in enumerate(parts): embeds.append(disnake.Embed(title=f"**{cat} ({i+1})**", description=p, color=disnake.Color.blurple()))
                    else: cat_embed.description = val; embeds.append(cat_embed)
        if accessible_count == 0: base.description = "No commands accessible."; await inter.followup.send(embed=base, ephemeral=True)
        elif len(embeds) == 1: await inter.followup.send(embed=embeds[0], ephemeral=True)
        elif len(embeds) <= 10:
             embeds[0].title = f"{bot.user.name} Help"; embeds[0].description = ("Categories:\n\n" + embeds[0].description).strip(); embeds[0].set_footer(text="<> req, [] opt.")
             await inter.followup.send(embeds=embeds, ephemeral=True)
        else: embeds[0].title = f"{bot.user.name} Help"; embeds[0].description = ("Categories(1/many):\n\n" + embeds[0].description).strip(); embeds[0].set_footer(text="<> req, [] opt. More cmds.")
        await inter.followup.send(embeds=embeds[:10], ephemeral=True)
    except Exception as e:
        logger.error(f"Error generating help command: {e}", exc_info=True)
        await inter.followup.send("❌ Error generating help message.", ephemeral=True)

# --- Cog Registration ---
try: bot.add_cog(ShopAdminCog(bot)); logger.info("ShopAdminCog loaded.")
except Exception as e: logger.critical(f"Failed to load ShopAdminCog: {e}", exc_info=True)

# --- Final Setup and Run ---
@bot.event
async def on_close():
    logger.info("Shutting down...");
    if autosave_data.is_running(): autosave_data.cancel(); logger.info("Autosave cancelled.")
    if lottery_drawing.is_running(): lottery_drawing.cancel(); logger.info("Lottery cancelled.")
    await asyncio.sleep(1); logger.info("Final save..."); save_user_data(); save_shop_items(); save_bot_data(); logger.info("Save complete.")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN: print("FATAL: Bot token missing.")
    else:
        logger.info("Starting bot (using sync_commands_debug=True)...")
        try: bot.run(DISCORD_BOT_TOKEN)
        except disnake.LoginFailure: logger.critical("Login Failed: Improper token.")
        except Exception as e: logger.critical(f"Bot execution error: {e}", exc_info=True)