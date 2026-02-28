import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8676951864:AAFre_ZY7CI85TKvfoI3yxqRWowoj5daO0s"
ADMIN_ID = 1208378923  # Замените на ваш Telegram ID

# Реквизиты
CRYPTO_ADDRESS = "UQDUUFncBcWC4eH3wN_4G3N9Yaf6nBFlcumDP8daYAQHNSOc"
CARD_NUMBER = "2200702051809809"
CARD_PHONE = "+79242143705"
STARS_PRICE_RUB = 1.3  # 1 звезда = 1.3₽

# Состояния
(WAIT_STARS_COUNT, WAIT_TARGET_USERNAME, WAIT_CURRENCY,
 WAIT_DEPOSIT_AMOUNT, WAIT_DEPOSIT_CURRENCY, WAIT_DEPOSIT_PROOF,
 WAIT_WITHDRAW_AMOUNT, WAIT_WITHDRAW_CURRENCY, WAIT_WITHDRAW_DETAILS) = range(9)

# Хранилище (в памяти, для продакшна используйте БД)
user_balances = {}  # {user_id: balance_in_rub}
user_referrals = {}  # {user_id: referrer_id}
referral_earnings = {}  # {user_id: total_earned}
pending_payments = {}  # {user_id: {stars, username, currency, amount}}
pending_deposits = {}  # {user_id: {amount, currency}}
pending_withdrawals = {}  # {user_id: {amount, currency, details}}


def get_balance(user_id):
    return user_balances.get(user_id, 0.0)


def add_balance(user_id, amount):
    user_balances[user_id] = get_balance(user_id) + amount


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⭐ Купить звёзды", callback_data="buy_stars")],
        [InlineKeyboardButton("💰 Пополнение", callback_data="deposit"),
         InlineKeyboardButton("💸 Вывод", callback_data="withdraw")],
        [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # Реферальная система
    if args and args[0].startswith("ref_"):
        referrer_id = int(args[0].split("_")[1])
        if referrer_id != user.id and user.id not in user_referrals:
            user_referrals[user.id] = referrer_id

    text = (
        f"✨ *Добро пожаловать в Stars Bulling!*\n\n"
        f"Привет, {user.first_name}!\n\n"
        f"🌟 Здесь вы можете быстро и безопасно купить Telegram Stars.\n"
        f"💎 Курс: *1 ⭐ = {STARS_PRICE_RUB}₽*\n\n"
        f"Выберите действие:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🏠 *Главное меню*\n\n"
        f"💎 Курс: *1 ⭐ = {STARS_PRICE_RUB}₽*\n"
        f"💰 Ваш баланс: *{get_balance(update.effective_user.id):.2f}₽*\n\n"
        "Выберите действие:"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ==================== ПОКУПКА ЗВЁЗД ====================

async def buy_stars_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
    await query.edit_message_text(
        "⭐ *Покупка звёзд*\n\nВведите количество звёзд, которое хотите купить:\n_(минимум 50 звёзд)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAIT_STARS_COUNT


async def buy_stars_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 50:
            await update.message.reply_text("❌ Минимальное количество — 50 звёзд. Введите снова:")
            return WAIT_STARS_COUNT
        context.user_data["stars_count"] = count
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")]]
        await update.message.reply_text(
            f"👤 Введите *@юзернейм* пользователя, которому нужно отправить звёзды:\n_(например: @username)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAIT_TARGET_USERNAME
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WAIT_STARS_COUNT


async def buy_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    context.user_data["target_username"] = username

    keyboard = [
        [InlineKeyboardButton("🇷🇺 Рубли (₽)", callback_data="currency_rub")],
        [InlineKeyboardButton("💵 Доллары ($)", callback_data="currency_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="currency_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
    ]
    stars = context.user_data["stars_count"]
    rub_amount = stars * STARS_PRICE_RUB
    usd_amount = rub_amount / 90
    ton_amount = rub_amount / 550

    await update.message.reply_text(
        f"💳 *Выберите валюту оплаты:*\n\n"
        f"⭐ Количество: *{stars} звёзд*\n"
        f"👤 Получатель: *{username}*\n\n"
        f"Стоимость:\n"
        f"• ₽ Рубли: *{rub_amount:.2f}₽*\n"
        f"• $ Доллары: *{usd_amount:.2f}$*\n"
        f"• 💎 TON: *{ton_amount:.4f} TON*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAIT_CURRENCY


async def buy_stars_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["currency"] = currency

    stars = context.user_data["stars_count"]
    username = context.user_data["target_username"]
    rub_amount = stars * STARS_PRICE_RUB
    usd_amount = rub_amount / 90
    ton_amount = rub_amount / 550

    if currency == "rub":
        amount_str = f"{rub_amount:.2f}₽"
        requisites = (
            f"💳 *Реквизиты для оплаты:*\n\n"
            f"Номер карты:\n`{CARD_NUMBER}`\n\n"
            f"Номер телефона:\n`{CARD_PHONE}`\n\n"
            f"Банк: *Сбербанк*"
        )
        context.user_data["amount"] = rub_amount
    else:
        if currency == "usd":
            amount_str = f"{usd_amount:.2f}$"
            context.user_data["amount"] = usd_amount
        else:
            amount_str = f"{ton_amount:.4f} TON"
            context.user_data["amount"] = ton_amount

        requisites = (
            f"💎 *Крипто-адрес для оплаты (TON/USDT):*\n\n"
            f"`{CRYPTO_ADDRESS}`"
        )

    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_stars")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
    ]

    await query.edit_message_text(
        f"📋 *Детали заказа:*\n\n"
        f"⭐ Звёзды: *{stars}*\n"
        f"👤 Получатель: *{username}*\n"
        f"💰 Сумма к оплате: *{amount_str}*\n\n"
        f"{requisites}\n\n"
        f"После оплаты нажмите кнопку ниже:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def paid_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    stars = context.user_data.get("stars_count", "?")
    username = context.user_data.get("target_username", "?")
    currency = context.user_data.get("currency", "?")
    amount = context.user_data.get("amount", "?")

    currency_symbols = {"rub": "₽", "usd": "$", "ton": " TON"}
    symbol = currency_symbols.get(currency, "")

    order_id = f"{user.id}_{stars}"
    pending_payments[order_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "stars": stars,
        "target": username,
        "currency": currency,
        "amount": amount,
        "symbol": symbol,
    }

    # Уведомление администратору
    admin_keyboard = [
        [InlineKeyboardButton("✅ Оплата пришла", callback_data=f"confirm_payment_{order_id}")],
        [InlineKeyboardButton("❌ Не пришла", callback_data=f"decline_payment_{order_id}")],
    ]
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Новая заявка на покупку звёзд!*\n\n"
        f"👤 От: {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"⭐ Звёзд: *{stars}*\n"
        f"📨 Получатель: *{username}*\n"
        f"💰 Сумма: *{amount}{symbol}*\n"
        f"💳 Валюта: *{currency.upper()}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )

    await query.edit_message_text(
        "⏳ *Заявка отправлена!*\n\n"
        "Ваш платёж проверяется администратором.\n"
        "Звёзды будут отправлены после подтверждения оплаты.\n\n"
        "Обычно это занимает до 15 минут ⏱",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
    )


async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    action, order_id = query.data.split("_payment_", 1)
    payment = pending_payments.get(order_id)

    if not payment:
        await query.edit_message_text("⚠️ Заявка не найдена (возможно уже обработана)")
        return

    user_id = payment["user_id"]

    if action == "confirm":
        # Начислить рефереру 3%
        if user_id in user_referrals:
            ref_id = user_referrals[user_id]
            ref_bonus = payment["stars"] * STARS_PRICE_RUB * 0.03
            add_balance(ref_id, ref_bonus)
            referral_earnings[ref_id] = referral_earnings.get(ref_id, 0) + ref_bonus
            try:
                await context.bot.send_message(
                    ref_id,
                    f"🎉 *Реферальный бонус!*\n\n"
                    f"Ваш реферал купил звёзды.\n"
                    f"Вам начислено: *+{ref_bonus:.2f}₽*\n"
                    f"Баланс: *{get_balance(ref_id):.2f}₽*",
                    parse_mode="Markdown"
                )
            except:
                pass

        await context.bot.send_message(
            user_id,
            f"✅ *Оплата подтверждена!*\n\n"
            f"⭐ *{payment['stars']} звёзд* будут отправлены на {payment['target']} в ближайшее время.\n\n"
            f"Спасибо за покупку! 🙏",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ Платёж подтверждён!\n"
            f"Пользователь: {payment['username_tg']}\n"
            f"Звёзды: {payment['stars']} → {payment['target']}"
        )
    else:
        await context.bot.send_message(
            user_id,
            "❌ *Оплата не найдена.*\n\n"
            "Ваш платёж не был подтверждён администратором.\n"
            "Пожалуйста, свяжитесь с поддержкой или повторите попытку.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"❌ Платёж отклонён!\nПользователь: {payment['username_tg']}"
        )

    del pending_payments[order_id]


# ==================== ПОПОЛНЕНИЕ ====================

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🇷🇺 Пополнить рублями (₽)", callback_data="deposit_rub")],
        [InlineKeyboardButton("💵 Пополнить долларами ($)", callback_data="deposit_usd")],
        [InlineKeyboardButton("💎 Пополнить TON", callback_data="deposit_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ]

    balance = get_balance(update.effective_user.id)
    await query.edit_message_text(
        f"💰 *Пополнение баланса*\n\n"
        f"Ваш текущий баланс: *{balance:.2f}₽*\n\n"
        f"*Реквизиты для пополнения:*\n\n"
        f"💳 Карта (₽):\n`{CARD_NUMBER}`\n"
        f"📱 Телефон: `{CARD_PHONE}`\n\n"
        f"💎 TON/USDT адрес:\n`{CRYPTO_ADDRESS}`\n\n"
        f"Выберите валюту пополнения:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def deposit_currency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["deposit_currency"] = currency

    symbols = {"rub": "₽", "usd": "$", "ton": "TON"}
    symbol = symbols[currency]

    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="deposit")]]
    await query.edit_message_text(
        f"💰 Введите сумму пополнения в *{symbol}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAIT_DEPOSIT_AMOUNT


async def deposit_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
        context.user_data["deposit_amount"] = amount
        currency = context.user_data["deposit_currency"]
        symbols = {"rub": "₽", "usd": "$", "ton": "TON"}
        symbol = symbols[currency]

        keyboard = [
            [InlineKeyboardButton("✅ Я пополнил", callback_data="confirm_deposit")],
            [InlineKeyboardButton("◀️ Отмена", callback_data="deposit")],
        ]

        if currency == "rub":
            req_text = f"Перевод на карту:\n`{CARD_NUMBER}`\nТел: `{CARD_PHONE}`"
        else:
            req_text = f"TON/USDT адрес:\n`{CRYPTO_ADDRESS}`"

        await update.message.reply_text(
            f"📋 *Детали пополнения:*\n\n"
            f"💰 Сумма: *{amount}{symbol}*\n\n"
            f"{req_text}\n\n"
            f"После перевода нажмите кнопку:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму:")
        return WAIT_DEPOSIT_AMOUNT


async def confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    amount = context.user_data.get("deposit_amount", "?")
    currency = context.user_data.get("deposit_currency", "?")
    symbols = {"rub": "₽", "usd": "$", "ton": " TON"}
    symbol = symbols.get(currency, "")

    dep_id = f"dep_{user.id}_{int(amount*100)}"
    pending_deposits[dep_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "amount": amount,
        "currency": currency,
        "symbol": symbol,
    }

    # Конвертируем в рубли для зачисления
    rates = {"rub": 1, "usd": 90, "ton": 550}
    amount_rub = amount * rates.get(currency, 1)

    pending_deposits[dep_id]["amount_rub"] = amount_rub

    admin_keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_dep_{dep_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_dep_{dep_id}")],
    ]
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Заявка на пополнение!*\n\n"
        f"👤 От: {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{symbol}*\n"
        f"💵 В рублях: *≈{amount_rub:.2f}₽*\n"
        f"💳 Валюта: *{currency.upper()}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )

    await query.edit_message_text(
        "⏳ *Заявка на пополнение отправлена!*\n\n"
        "Администратор проверит ваш платёж.\n"
        "Баланс будет пополнен после подтверждения.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
    )


async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    parts = query.data.split("_dep_", 1)
    action = parts[0]
    dep_id = parts[1]
    deposit = pending_deposits.get(dep_id)

    if not deposit:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return

    user_id = deposit["user_id"]

    if action == "confirm":
        amount_rub = deposit["amount_rub"]
        add_balance(user_id, amount_rub)
        await context.bot.send_message(
            user_id,
            f"✅ *Пополнение подтверждено!*\n\n"
            f"На ваш баланс зачислено: *+{amount_rub:.2f}₽*\n"
            f"Текущий баланс: *{get_balance(user_id):.2f}₽*",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ Пополнение подтверждено!\n"
            f"Пользователь: {deposit['username_tg']}\n"
            f"Зачислено: {amount_rub:.2f}₽"
        )
    else:
        await context.bot.send_message(
            user_id,
            "❌ *Пополнение отклонено.*\n\n"
            "Платёж не был найден администратором.\n"
            "Свяжитесь с поддержкой.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"❌ Пополнение отклонено!\nПользователь: {deposit['username_tg']}"
        )

    del pending_deposits[dep_id]


# ==================== ВЫВОД ====================

async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    balance = get_balance(user_id)

    if balance < 100:
        await query.edit_message_text(
            f"❌ *Недостаточно средств*\n\n"
            f"Ваш баланс: *{balance:.2f}₽*\n"
            f"Минимальная сумма вывода: *100₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
        )
        return

    keyboard = [
        [InlineKeyboardButton("🇷🇺 Вывести в рублях (₽)", callback_data="withdraw_rub")],
        [InlineKeyboardButton("💵 Вывести в долларах ($)", callback_data="withdraw_usd")],
        [InlineKeyboardButton("💎 Вывести в TON", callback_data="withdraw_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ]

    await query.edit_message_text(
        f"💸 *Вывод средств*\n\n"
        f"Ваш баланс: *{balance:.2f}₽*\n"
        f"Минимальная сумма вывода: 100₽\n\n"
        f"Выберите валюту вывода:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def withdraw_currency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["withdraw_currency"] = currency

    symbols = {"rub": "₽", "usd": "$", "ton": "TON"}
    symbol = symbols[currency]

    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="withdraw")]]
    await query.edit_message_text(
        f"💸 Введите сумму вывода в *{symbol}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAIT_WITHDRAW_AMOUNT


async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        currency = context.user_data["withdraw_currency"]
        rates = {"rub": 1, "usd": 90, "ton": 550}
        amount_rub = amount * rates.get(currency, 1)
        balance = get_balance(update.effective_user.id)

        if amount_rub > balance:
            symbols = {"rub": "₽", "usd": "$", "ton": "TON"}
            await update.message.reply_text(
                f"❌ Недостаточно средств!\n"
                f"Баланс: {balance:.2f}₽, нужно: {amount_rub:.2f}₽\n"
                f"Введите меньшую сумму:"
            )
            return WAIT_WITHDRAW_AMOUNT

        context.user_data["withdraw_amount"] = amount
        context.user_data["withdraw_amount_rub"] = amount_rub

        symbols = {"rub": "₽", "usd": "$", "ton": "TON"}
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="withdraw")]]
        await update.message.reply_text(
            f"💸 Введите реквизиты для вывода *{amount}{symbols[currency]}*:\n\n"
            f"_(Номер карты / адрес кошелька)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAIT_WITHDRAW_DETAILS
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму:")
        return WAIT_WITHDRAW_AMOUNT


async def withdraw_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    context.user_data["withdraw_details"] = details
    user = update.effective_user

    amount = context.user_data["withdraw_amount"]
    amount_rub = context.user_data["withdraw_amount_rub"]
    currency = context.user_data["withdraw_currency"]
    symbols = {"rub": "₽", "usd": "$", "ton": " TON"}
    symbol = symbols[currency]

    wd_id = f"wd_{user.id}_{int(amount*100)}"
    pending_withdrawals[wd_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "amount": amount,
        "amount_rub": amount_rub,
        "currency": currency,
        "symbol": symbol,
        "details": details,
    }

    admin_keyboard = [
        [InlineKeyboardButton("✅ Выплатить", callback_data=f"confirm_wd_{wd_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_wd_{wd_id}")],
    ]
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Заявка на вывод!*\n\n"
        f"👤 От: {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{symbol}*\n"
        f"💵 В рублях: *{amount_rub:.2f}₽*\n"
        f"📋 Реквизиты:\n`{details}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )

    await update.message.reply_text(
        "⏳ *Заявка на вывод отправлена!*\n\n"
        "Администратор обработает вашу заявку.\n"
        "Средства будут переведены в течение 24 часов.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
    )
    return ConversationHandler.END


async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    parts = query.data.split("_wd_", 1)
    action = parts[0]
    wd_id = parts[1]
    wd = pending_withdrawals.get(wd_id)

    if not wd:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return

    user_id = wd["user_id"]

    if action == "confirm":
        add_balance(user_id, -wd["amount_rub"])
        await context.bot.send_message(
            user_id,
            f"✅ *Вывод подтверждён!*\n\n"
            f"Сумма *{wd['amount']}{wd['symbol']}* отправлена на указанные реквизиты.\n"
            f"Остаток баланса: *{get_balance(user_id):.2f}₽*",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ Вывод выплачен!\nПользователь: {wd['username_tg']}\nСумма: {wd['amount']}{wd['symbol']}"
        )
    else:
        await context.bot.send_message(
            user_id,
            "❌ *Вывод отклонён.*\n\nСвяжитесь с поддержкой.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"❌ Вывод отклонён!\nПользователь: {wd['username_tg']}"
        )

    del pending_withdrawals[wd_id]


# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"

    ref_count = sum(1 for v in user_referrals.values() if v == user.id)
    earned = referral_earnings.get(user.id, 0)
    balance = get_balance(user.id)

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]

    await query.edit_message_text(
        f"👥 *Реферальная система*\n\n"
        f"💡 Приглашайте друзей и зарабатывайте *3%* с каждой их покупки!\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{ref_link}`\n\n"
        f"📊 *Ваша статистика:*\n"
        f"• Приглашено друзей: *{ref_count}*\n"
        f"• Заработано всего: *{earned:.2f}₽*\n"
        f"• Текущий баланс: *{balance:.2f}₽*\n\n"
        f"_Ссылка уникальная — вы не можете перейти по ней сами_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================== ИНФОРМАЦИЯ ====================

async def info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]

    await query.edit_message_text(
        "ℹ️ *О боте Stars Bulling*\n\n"
        "🛡️ *БЕЗОПАСНОСТЬ И НАДЁЖНОСТЬ*\n\n"
        "Stars Bulling — это проверенный и надёжный сервис по продаже Telegram Stars. "
        "Мы работаем честно и прозрачно, обеспечивая безопасность каждой транзакции.\n\n"
        "🔐 *Защита ваших данных:*\n"
        "Мы не храним личные данные пользователей. Все транзакции проходят через защищённые каналы. "
        "Ваши реквизиты используются исключительно для проведения выплат.\n\n"
        "⚡ *Скорость обработки:*\n"
        "Все заявки обрабатываются администратором в ручном режиме. Среднее время подтверждения — "
        "от 5 до 30 минут. В ночное время возможна задержка до нескольких часов.\n\n"
        "💎 *Качество сервиса:*\n"
        "Мы гарантируем отправку реальных Telegram Stars на указанный аккаунт. "
        "Если звёзды не были получены после подтверждения оплаты — мы вернём средства или отправим повторно.\n\n"
        "💰 *Реферальная программа:*\n"
        "Зарабатывайте 3% с каждой покупки приглашённого друга. "
        "Бонусы начисляются автоматически на ваш баланс.\n\n"
        "📋 *Гарантии:*\n"
        "• Отправляем только после подтверждения оплаты\n"
        "• В случае спорных ситуаций всегда идём навстречу\n"
        "• Прозрачная система балансов и выплат\n"
        "• Поддержка нескольких валют: ₽, $, TON\n\n"
        "📞 *Поддержка:*\n"
        "По всем вопросам обращайтесь к администратору.\n\n"
        "⭐ *Курс: 1 звезда = 1.3₽*\n"
        "_Актуально на момент написания_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def main():
    app = Application.builder().token(TOKEN).build()

    # ConversationHandler для покупки звёзд
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_stars_start, pattern="^buy_stars$")],
        states={
            WAIT_STARS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_count)],
            WAIT_TARGET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_username)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    # ConversationHandler для пополнения
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_currency_selected, pattern="^deposit_(rub|usd|ton)$")],
        states={
            WAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_received)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    # ConversationHandler для вывода
    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_currency_selected, pattern="^withdraw_(rub|usd|ton)$")],
        states={
            WAIT_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_received)],
            WAIT_WITHDRAW_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_details_received)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(buy_conv)
    app.add_handler(deposit_conv)
    app.add_handler(withdraw_conv)

    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(buy_stars_currency, pattern="^currency_(rub|usd|ton)$"))
    app.add_handler(CallbackQueryHandler(paid_stars, pattern="^paid_stars$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern="^(confirm|decline)_payment_"))
    app.add_handler(CallbackQueryHandler(deposit_menu, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(confirm_deposit, pattern="^confirm_deposit$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_deposit, pattern="^(confirm|decline)_dep_"))
    app.add_handler(CallbackQueryHandler(withdraw_menu, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_withdrawal, pattern="^(confirm|decline)_wd_"))
    app.add_handler(CallbackQueryHandler(referral_menu, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(info_menu, pattern="^info$"))

    print("✅ Stars Bulling Bot запущен!")
    print(f"⚠️  Не забудьте установить ADMIN_ID = ваш Telegram ID (текущий: {ADMIN_ID})")
    app.run_polling()


if __name__ == "__main__":
    main()
