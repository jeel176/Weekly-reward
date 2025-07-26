import logging
import sqlite3
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- Configuration ---
# Your bot token is now included.
TOKEN = "8430218141:AAH9GdlKMjWm6i9SDb2CHGk300M4pnb8G68" 
# This is your admin chat ID. All notifications will be sent here.
ADMIN_CHAT_ID = "927631582" 

# Plans Configuration (in USD)
FREE_PLAN = {"daily_reward": 0.01}
PREMIUM_PLAN = {"weekly_reward": 10.00, "price": 50.00}
MIN_WITHDRAWAL = 50.00

# Wallet Addresses Dictionary
WALLET_ADDRESSES = {
    "USDT (TRC20)": "THA2vJoCKHdgMV9GW9hJQT9RUvRu7VVfBG",
    "USDT (ERC20)": "0x690F04FF4fEf1b9A5d9224c5FCE56aadc6A9c010",
    "USDT (BEP20)": "0x690F04FF4fEf1b9A5d9224c5FCE56aadc6A9c010",
    "Bitcoin (BTC)": "bc1q2jvgk9q6vdhv3y54qaw8dpgxyz5sjhtr50kwu7",
    "Ethereum (ETH)": "0x690F04FF4fEf1b9A5d9224c5FCE56aadc6A9c010",
    "TRON (TRX)": "THA2vJoCKHdgMV9GW9hJQT9RUvRu7VVfBG",
    "Binance Coin (BNB)": "0x690F04FF4fEf1b9A5d9224c5FCE56aadc6A9c010",
    "Solana (SOL)": "3ZG8MejdPmvuKe2YuiyhwUpkKaA8E1bJXksoUtCszS5f",
}

# --- Database Setup ---
def setup_database():
    """Initializes the SQLite database and users table."""
    conn = sqlite3.connect('weekly_reward_bot.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            plan TEXT DEFAULT 'free',
            balance REAL DEFAULT 0.0,
            last_reward_claimed TEXT,
            join_date TEXT
        )
    ''')
    conn.commit()
    return conn

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation States ---
UPGRADE, UPGRADE_CONFIRM, WITHDRAW, WITHDRAW_CONFIRM = range(4)

# --- Helper Functions ---
def get_user(user_id):
    """Fetches a user's data from the database."""
    conn = setup_database()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    if user_data:
        # Return as a dictionary for easy access to columns by name
        keys = ["user_id", "username", "plan", "balance", "last_reward_claimed", "join_date"]
        return dict(zip(keys, user_data))
    return None

def can_claim_reward(user):
    """Checks if a user is eligible to claim their reward based on their plan and last claim time."""
    if not user or not user.get('last_reward_claimed'):
        return True  # New users can claim immediately
    
    last_claim_time = datetime.datetime.fromisoformat(user['last_reward_claimed'])
    plan = user['plan']
    now = datetime.datetime.now()

    if plan == 'free':
        return now - last_claim_time >= datetime.timedelta(days=1)
    elif plan == 'premium':
        return now - last_claim_time >= datetime.timedelta(weeks=1)
    return False

# --- Main Menu ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main menu with InlineKeyboardButtons."""
    # IMPORTANT: The URL for "Mining Animation" should point to a real webpage where you host the animation HTML file.
    keyboard = [
        [InlineKeyboardButton("👤 My Profile", callback_data='profile')],
        [InlineKeyboardButton("💰 Claim Reward", callback_data='claim_reward')],
        [InlineKeyboardButton("🚀 Upgrade to Premium", callback_data='upgrade_start')],
        [InlineKeyboardButton("💸 Withdraw Funds", callback_data='withdraw_start')],
        [InlineKeyboardButton("✨ Mining Animation", url="https://t.me/WeeklyRewardBot")], # Replace with your hosted animation URL
        [InlineKeyboardButton("💬 Support", callback_data='support')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    menu_text = "Welcome to the Main Menu! Select an option to continue."
    # If called from a button press (callback_query), edit the message. Otherwise, send a new one.
    if update.callback_query:
        await update.callback_query.edit_message_text(menu_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(menu_text, reply_markup=reply_markup)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command, registers new users, and shows the main menu."""
    user = update.effective_user
    db_user = get_user(user.id)

    if not db_user:
        # If user is new, add them to the database
        conn = setup_database()
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)",
            (user.id, user.username or "N/A", datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        await update.message.reply_html(
            f"🎉 Welcome, {user.mention_html()}!\n\n"
            "You are now on the <b>Free Plan</b>. You can start claiming your daily rewards immediately.\n\n"
            "Explore the menu below to get started."
        )
    else:
        await update.message.reply_html(f"Welcome back, {user.mention_html()}!")

    await show_main_menu(update, context)

# --- Callback Query Handlers (Button Clicks) ---
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes all main menu button clicks to their respective handlers."""
    query = update.callback_query
    await query.answer() # Acknowledge the button press
    
    data = query.data
    if data == 'profile':
        await profile_handler(update, context)
    elif data == 'claim_reward':
        await claim_reward_handler(update, context)
    elif data == 'support':
        await support_handler(update, context)
    elif data == 'main_menu':
        await show_main_menu(update, context)

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's profile information."""
    query = update.callback_query
    user = get_user(query.from_user.id)
    
    if not user:
        await query.edit_message_text("Could not find your profile. Please /start the bot again.")
        return

    plan_name = user['plan'].capitalize()
    balance = user['balance']
    reward_info = f"Daily Reward: ${FREE_PLAN['daily_reward']:.2f}" if user['plan'] == 'free' else f"Weekly Reward: ${PREMIUM_PLAN['weekly_reward']:.2f}"

    text = (
        f"<b>👤 User Profile</b>\n\n"
        f"<b>User ID:</b> <code>{user['user_id']}</code>\n"
        f"<b>Plan:</b> {plan_name}\n"
        f"<b>Balance:</b> ${balance:.2f}\n"
        f"<b>{reward_info}</b>"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def claim_reward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the reward claim logic."""
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)

    if can_claim_reward(user):
        reward_amount = FREE_PLAN['daily_reward'] if user['plan'] == 'free' else PREMIUM_PLAN['weekly_reward']
        new_balance = user['balance'] + reward_amount
        
        conn = setup_database()
        c = conn.cursor()
        c.execute("UPDATE users SET balance = ?, last_reward_claimed = ? WHERE user_id = ?",
                  (new_balance, datetime.datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        
        await query.answer(f"Success! ${reward_amount:.2f} has been added to your balance.", show_alert=True)
        await profile_handler(update, context) # Refresh profile view to show new balance
    else:
        await query.answer("You have already claimed your reward for this period. Please try again later.", show_alert=True)

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays support contact information."""
    query = update.callback_query
    text = (
        "<b>💬 Support</b>\n\n"
        "If you have any questions or need help with a payment, please contact our support team.\n\n"
        "<b>Email:</b> <code>support@weeklyreward.dev</code>\n"
        "<b>Telegram Admin:</b> @WeekleyReward"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)

# --- Upgrade Conversation ---
async def upgrade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the upgrade to premium conversation."""
    query = update.callback_query
    await query.answer()

    text = (
        f"<b>🚀 Upgrade to Premium Plan</b>\n\n"
        f"Unlock higher rewards by upgrading! The premium plan costs <b>${PREMIUM_PLAN['price']:.2f}</b> for a lifetime membership.\n\n"
        f"<b>Benefits:</b>\n"
        f"✅ Weekly Reward of ${PREMIUM_PLAN['weekly_reward']:.2f}\n"
        f"✅ Priority Support\n\n"
        f"Please select a cryptocurrency to pay with:"
    )
    
    # Dynamically create buttons from the wallet dictionary
    keyboard = [[InlineKeyboardButton(currency, callback_data=f"pay_{currency}")] for currency in WALLET_ADDRESSES.keys()]
    keyboard.append([InlineKeyboardButton("⬅️ Cancel", callback_data='cancel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    return UPGRADE

async def upgrade_select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the selected wallet address and instructions."""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace("pay_", "")
    address = WALLET_ADDRESSES.get(currency)
    context.user_data['payment_currency'] = currency # Save currency for the next step
    
    text = (
        f"Please send exactly <b>${PREMIUM_PLAN['price']:.2f}</b> worth of <b>{currency}</b> to the following address:\n\n"
        f"<code>{address}</code>\n\n"
        f"⚠️ <b>Important:</b> After sending the payment, please copy the <b>Transaction ID (TxID/Hash)</b> and send it back to me here for verification."
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Payment Selection", callback_data='upgrade_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    return UPGRADE_CONFIRM

async def upgrade_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the transaction hash, notifies admin, and informs the user."""
    tx_hash = update.message.text
    user = update.effective_user
    currency = context.user_data.get('payment_currency', 'N/A')
    
    # Notify Admin
    admin_text = (
        f"🔔 <b>New Upgrade Request</b>\n\n"
        f"<b>User:</b> {user.mention_html()} (ID: <code>{user.id}</code>)\n"
        f"<b>Currency:</b> {currency}\n"
        f"<b>Transaction Hash:</b>\n<code>{tx_hash}</code>\n\n"
        f"Please verify the payment and upgrade the user's account manually."
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode='HTML')
    
    # Inform User
    user_text = (
        "✅ Thank you! We have received your transaction details.\n\n"
        "Your payment is now being verified. This process usually takes a few hours. "
        "We will notify you once your plan has been upgraded."
    )
    await update.message.reply_text(user_text)
    
    await show_main_menu(update, context) # Return to main menu
    return ConversationHandler.END

# --- Withdraw Conversation ---
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the withdrawal conversation."""
    query = update.callback_query
    user = get_user(query.from_user.id)
    
    if user['balance'] < MIN_WITHDRAWAL:
        await query.answer(f"Your balance is too low. Minimum withdrawal is ${MIN_WITHDRAWAL:.2f}.", show_alert=True)
        return ConversationHandler.END
        
    await query.answer()
    text = (
        f"<b>💸 Withdraw Funds</b>\n\n"
        f"Your current balance is <b>${user['balance']:.2f}</b>.\n"
        f"The minimum withdrawal amount is ${MIN_WITHDRAWAL:.2f}.\n\n"
        f"Please enter the amount (in USD) you wish to withdraw:"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Cancel", callback_data='cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    return WITHDRAW

async def withdraw_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gets withdrawal amount and asks for the address."""
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number (e.g., 55.50).")
        return WITHDRAW

    user = get_user(update.effective_user.id)
    if amount > user['balance']:
        await update.message.reply_text("You cannot withdraw more than your balance. Please try again.")
        return WITHDRAW
    if amount < MIN_WITHDRAWAL:
        await update.message.reply_text(f"Minimum withdrawal is ${MIN_WITHDRAWAL:.2f}. Please enter a higher amount.")
        return WITHDRAW

    context.user_data['withdraw_amount'] = amount
    text = "Great. Now, please send me the wallet address where you want to receive your funds."
    await update.message.reply_text(text)
    return WITHDRAW_CONFIRM

async def withdraw_get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gets wallet address, notifies admin, and debits user balance."""
    address = update.message.text
    user = update.effective_user
    amount = context.user_data.get('withdraw_amount', 0)
    
    # Notify Admin
    admin_text = (
        f"🔔 <b>New Withdrawal Request</b>\n\n"
        f"<b>User:</b> {user.mention_html()} (ID: <code>{user.id}</code>)\n"
        f"<b>Amount:</b> ${amount:.2f}\n"
        f"<b>Recipient Address:</b>\n<code>{address}</code>\n\n"
        f"Please process this withdrawal."
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode='HTML')

    # Debit user's balance immediately to prevent abuse
    conn = setup_database()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
    conn.commit()
    conn.close()

    # Inform User
    user_text = (
        "✅ Your withdrawal request has been submitted!\n\n"
        "It will be processed by our team within 24-48 hours. "
        "The requested amount has been deducted from your balance."
    )
    await update.message.reply_text(user_text)
    
    await show_main_menu(update, context)
    return ConversationHandler.END
    
# --- General Handlers ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any ongoing conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Operation cancelled.")
    await show_main_menu(update, context) # Show the main menu again
    return ConversationHandler.END

def main() -> None:
    """Sets up the application and runs the bot."""
    # Initialize database
    setup_database()

    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for upgrading plan
    upgrade_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(upgrade_start, pattern='^upgrade_start$')],
        states={
            UPGRADE: [CallbackQueryHandler(upgrade_select_payment, pattern='^pay_')],
            UPGRADE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, upgrade_confirm_payment)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$'), CallbackQueryHandler(upgrade_start, pattern='^upgrade_start$')],
    )

    # Conversation handler for withdrawing funds
    withdraw_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_start, pattern='^withdraw_start$')],
        states={
            WITHDRAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_get_amount)],
            WITHDRAW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_get_address)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')],
    )
    
    # Add handlers to the application
    application.add_handler(CommandHandler("start", start))
    application.add_handler(upgrade_conv_handler)
    application.add_handler(withdraw_conv_handler)
    application.add_handler(CallbackQueryHandler(main_menu_handler)) # Main handler for menu buttons

    # Run the bot until you press Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()

