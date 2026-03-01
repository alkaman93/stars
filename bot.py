import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8431606658:AAHBr6IrEkQpEkf8gLQGToUBZ3TPLp-HH_E"
BOT_NAME = "Купить звезды | scronexcy⚡️"
BOT_USERNAME = "@sellstarscron_bot"

# Администраторы (все получают уведомления, все могут управлять)
ADMIN_IDS = [174415647, 7014080193]

SUPPORT_USERNAME = "@Scronexcyyy"

# Реквизиты
CRYPTO_ADDRESS = "UQDUUFncBcWC4eH3wN_4G3N9Yaf6nBFlcumDP8daYAQHNSOc"
CARD_NUMBER = "2200702051809809"
CARD_PHONE = "+79242143705"
STARS_PRICE_RUB = 1.3
TON_PRICE_RUB = 550.0   # 1 TON = ? руб (по умолчанию)

# Конвертация (1 единица = ? рублей)
RATES = {"rub": 1.0, "usd": 90.0, "ton": TON_PRICE_RUB}

# Состояния
(
    WAIT_STARS_COUNT, WAIT_BUY_TYPE, WAIT_TARGET_USERNAME, WAIT_CURRENCY,
    WAIT_TON_AMOUNT, WAIT_TON_ADDRESS,
    WAIT_DEPOSIT_AMOUNT,
    WAIT_WITHDRAW_AMOUNT, WAIT_WITHDRAW_DETAILS,
    WAIT_ADMIN_BROADCAST,
    WAIT_ADMIN_SET_BANNER,
    WAIT_ADMIN_EDIT_PRICE,
    WAIT_ADMIN_EDIT_TON_PRICE,
    WAIT_ADMIN_BALANCE_USER, WAIT_ADMIN_BALANCE_AMOUNT,
    WAIT_ADMIN_MSG_USER_ID, WAIT_ADMIN_MSG_TEXT,
) = range(17)

# Хранилище
user_balances = {}
user_referrals = {}
referral_earnings = {}
pending_payments = {}       # звёзды
pending_ton_orders = {}     # TON
pending_deposits = {}
pending_withdrawals = {}
all_users = set()
last_menu_msg = {}
banner_file_id = None


# ==================== УТИЛИТЫ ====================

def get_balance(uid): return user_balances.get(uid, 0.0)
def add_balance(uid, amt): user_balances[uid] = get_balance(uid) + amt
def is_admin(uid): return uid in ADMIN_IDS


def main_menu_keyboard(uid=None):
    admin = is_admin(uid) if uid else False
    kb = [
        [InlineKeyboardButton("⭐ Купить звёзды", callback_data="buy_stars"),
         InlineKeyboardButton("💎 Купить TON", callback_data="buy_ton")],
        [
            InlineKeyboardButton("💰 Пополнение", callback_data="deposit"),
            InlineKeyboardButton("💸 Вывод", callback_data="withdraw"),
        ],
        [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")],
        [
            InlineKeyboardButton("ℹ️ Информация", callback_data="info"),
            InlineKeyboardButton("🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"),
        ],
    ]
    if admin:
        kb.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


async def notify_admins(context, text, kb=None):
    """Отправить уведомление всем администраторам."""
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=aid, text=text,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception:
            pass


async def _delete_prev(user_id, chat_id, context):
    mid = last_menu_msg.pop(user_id, None)
    if mid:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass


async def send_menu_msg(chat_id, user_id, text, kb, context, photo=None):
    await _delete_prev(user_id, chat_id, context)
    if photo:
        msg = await context.bot.send_photo(
            chat_id=chat_id, photo=photo,
            caption=text, parse_mode="Markdown", reply_markup=kb
        )
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode="Markdown", reply_markup=kb
        )
    last_menu_msg[user_id] = msg.message_id
    return msg


async def cb_send_menu(query, text, kb, context):
    await query.answer()
    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)
    return await send_menu_msg(cid, uid, text, kb, context, photo=banner_file_id)


# ==================== СТАРТ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    if context.args and context.args[0].startswith("ref_"):
        try:
            rid = int(context.args[0].split("_")[1])
            if rid != user.id and user.id not in user_referrals:
                user_referrals[user.id] = rid
        except Exception:
            pass

    text = (
        f"✨ *Добро пожаловать в {BOT_NAME}!*\n\n"
        f"Привет, {user.first_name}! 👋\n\n"
        f"⭐ *Telegram Stars* — быстро, надёжно, выгодно.\n"
        f"💎 *TON* — купить крипту прямо здесь.\n\n"
        f"📈 Курсы:\n"
        f"• 1 ⭐ = *{STARS_PRICE_RUB}₽*\n"
        f"• 1 TON = *{RATES['ton']:.0f}₽*\n\n"
        f"💰 Ваш баланс: *{get_balance(user.id):.2f}₽*\n\n"
        f"Выберите действие:"
    )
    await send_menu_msg(
        update.effective_chat.id, user.id, text,
        main_menu_keyboard(user.id), context, photo=banner_file_id
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    all_users.add(user.id)
    text = (
        f"🏠 *Главное меню — {BOT_NAME}*\n\n"
        f"📈 Курсы:\n"
        f"• 1 ⭐ = *{STARS_PRICE_RUB}₽*\n"
        f"• 1 TON = *{RATES['ton']:.0f}₽*\n\n"
        f"💰 Ваш баланс: *{get_balance(user.id):.2f}₽*\n\n"
        f"Выберите действие:"
    )
    await cb_send_menu(query, text, main_menu_keyboard(user.id), context)


# ==================== ПОКУПКА ЗВЁЗД ====================

async def buy_stars_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
    await cb_send_menu(
        query,
        "⭐ *Покупка звёзд*\n\n"
        "Введите количество звёзд:\n"
        "_(минимум 50 звёзд)_",
        kb, context
    )
    return WAIT_STARS_COUNT


async def buy_stars_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_users.add(update.effective_user.id)
    try:
        count = int(update.message.text.strip())
        if count < 50:
            await update.message.reply_text("❌ Минимум — 50 звёзд. Введите снова:")
            return WAIT_STARS_COUNT
        context.user_data["stars_count"] = count
        rub = count * STARS_PRICE_RUB
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🙋 Купить себе", callback_data="buy_type_self"),
                InlineKeyboardButton("🥷 Купить анонимно", callback_data="buy_type_anon"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
        ])
        await update.message.reply_text(
            f"⭐ *Звёзд: {count}*\n"
            f"💰 Стоимость: *{rub:.2f}₽*\n\n"
            f"Выберите тип покупки:",
            parse_mode="Markdown", reply_markup=kb
        )
        return WAIT_BUY_TYPE
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WAIT_STARS_COUNT


async def buy_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buy_type = query.data.split("_")[2]
    context.user_data["buy_type"] = buy_type

    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)

    if buy_type == "self":
        user = query.from_user
        username = f"@{user.username}" if user.username else f"ID:{user.id}"
        context.user_data["target_username"] = username
        stars = context.user_data["stars_count"]
        rub = stars * STARS_PRICE_RUB
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Рубли (₽)", callback_data="currency_rub")],
            [InlineKeyboardButton("💵 Доллары ($)", callback_data="currency_usd")],
            [InlineKeyboardButton("💎 TON", callback_data="currency_ton")],
            [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
        ])
        await send_menu_msg(
            cid, uid,
            f"💳 *Выберите валюту оплаты:*\n\n"
            f"⭐ Звёзды: *{stars}*\n"
            f"🙋 Получатель: *{username}* (вы)\n\n"
            f"Стоимость:\n"
            f"• ₽ Рубли: *{rub:.2f}₽*\n"
            f"• $ Доллары: *{rub / RATES['usd']:.2f}$*\n"
            f"• 💎 TON: *{rub / RATES['ton']:.4f} TON*",
            kb, context, photo=banner_file_id
        )
        return WAIT_CURRENCY
    else:
        msg = await context.bot.send_message(
            chat_id=cid,
            text="🥷 *Анонимная покупка*\n\n"
                 "Введите *@юзернейм* получателя:\n"
                 "_(получатель не узнает, кто купил)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")]]),
        )
        last_menu_msg[uid] = msg.message_id
        return WAIT_TARGET_USERNAME


async def buy_stars_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    context.user_data["target_username"] = username
    stars = context.user_data["stars_count"]
    buy_type = context.user_data.get("buy_type", "anon")
    rub = stars * STARS_PRICE_RUB
    label = "🥷 Получатель (анонимно)" if buy_type == "anon" else "👤 Получатель"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рубли (₽)", callback_data="currency_rub")],
        [InlineKeyboardButton("💵 Доллары ($)", callback_data="currency_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="currency_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
    ])
    await update.message.reply_text(
        f"💳 *Выберите валюту оплаты:*\n\n"
        f"⭐ Звёзды: *{stars}*\n"
        f"{label}: *{username}*\n\n"
        f"Стоимость:\n"
        f"• ₽ Рубли: *{rub:.2f}₽*\n"
        f"• $ Доллары: *{rub / RATES['usd']:.2f}$*\n"
        f"• 💎 TON: *{rub / RATES['ton']:.4f} TON*",
        parse_mode="Markdown", reply_markup=kb
    )
    return WAIT_CURRENCY


async def buy_stars_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["currency"] = currency
    stars = context.user_data["stars_count"]
    username = context.user_data["target_username"]
    rub = stars * STARS_PRICE_RUB
    fmt = {"rub": f"{rub:.2f}₽", "usd": f"{rub / RATES['usd']:.2f}$", "ton": f"{rub / RATES['ton']:.4f} TON"}
    amounts = {"rub": rub, "usd": rub / RATES["usd"], "ton": rub / RATES["ton"]}
    context.user_data["amount"] = amounts[currency]

    if currency == "rub":
        req = (
            f"💳 *Реквизиты для оплаты:*\n\n"
            f"Номер карты:\n`{CARD_NUMBER}`\n\n"
            f"Телефон:\n`{CARD_PHONE}`\n\n"
            f"Банк: *Сбербанк*"
        )
    else:
        req = f"💎 *Крипто-адрес (TON/USDT):*\n\n`{CRYPTO_ADDRESS}`"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_stars")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
    ])
    text = (
        f"📋 *Детали заказа:*\n\n"
        f"⭐ Звёзды: *{stars}*\n"
        f"👤 Получатель: *{username}*\n"
        f"💰 К оплате: *{fmt[currency]}*\n\n"
        f"{req}\n\n"
        f"После оплаты нажмите кнопку ниже:"
    )
    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)
    await send_menu_msg(cid, uid, text, kb, context, photo=banner_file_id)
    return ConversationHandler.END


async def paid_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    stars = context.user_data.get("stars_count", "?")
    username = context.user_data.get("target_username", "?")
    currency = context.user_data.get("currency", "?")
    amount = context.user_data.get("amount", 0)
    buy_type = context.user_data.get("buy_type", "anon")
    syms = {"rub": "₽", "usd": "$", "ton": " TON"}
    sym = syms.get(currency, "")
    type_label = "🙋 Себе" if buy_type == "self" else "🥷 Анонимно"
    order_id = f"{user.id}_{stars}_{int(float(amount) * 100)}"
    pending_payments[order_id] = {
        "user_id": user.id, "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "stars": stars, "target": username, "currency": currency, "amount": amount, "symbol": sym,
        "buy_type": buy_type,
    }
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Оплата пришла", callback_data=f"confirm_payment_{order_id}")],
        [InlineKeyboardButton("❌ Не пришла", callback_data=f"decline_payment_{order_id}")],
    ])
    await notify_admins(
        context,
        f"🔔 *Новая оплата за звёзды!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"⭐ Звёзд: *{stars}*\n📨 Получатель: *{username}*\n"
        f"🏷 Тип: *{type_label}*\n"
        f"💰 Сумма: *{amount}{sym}*\n💳 Валюта: *{currency.upper()}*",
        admin_kb
    )
    await cb_send_menu(
        query,
        "⏳ *Заявка отправлена!*\n\n"
        "Администратор проверит ваш платёж.\n"
        "Звёзды отправят после подтверждения.\n\n"
        "⏱ Обычно до 15 минут",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context
    )


async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await query.answer()
    action, order_id = query.data.split("_payment_", 1)
    payment = pending_payments.get(order_id)
    if not payment:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return
    uid = payment["user_id"]
    if action == "confirm":
        if uid in user_referrals:
            ref_id = user_referrals[uid]
            bonus = payment["stars"] * STARS_PRICE_RUB * 0.03
            add_balance(ref_id, bonus)
            referral_earnings[ref_id] = referral_earnings.get(ref_id, 0) + bonus
            try:
                await context.bot.send_message(
                    ref_id,
                    f"🎉 *Реферальный бонус!*\n\nВаш реферал купил звёзды.\n"
                    f"Начислено: *+{bonus:.2f}₽*\nБаланс: *{get_balance(ref_id):.2f}₽*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        await context.bot.send_message(
            uid,
            f"✅ *Оплата подтверждена!*\n\n"
            f"⭐ *{payment['stars']} звёзд* будут отправлены на {payment['target']}.\n"
            f"Спасибо за покупку! 🙏",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ Подтверждено!\n{payment['username_tg']} | {payment['stars']}⭐ → {payment['target']}"
        )
    else:
        await context.bot.send_message(
            uid,
            "❌ *Оплата не найдена.*\nОбратитесь в поддержку.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(f"❌ Отклонено!\n{payment['username_tg']}")
    del pending_payments[order_id]


# ==================== ПОКУПКА TON ====================

async def buy_ton_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ton_rate = RATES["ton"]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
    await cb_send_menu(
        query,
        f"💎 *Покупка TON*\n\n"
        f"Текущий курс: *1 TON = {ton_rate:.0f}₽*\n\n"
        f"Введите количество TON, которое хотите купить:\n"
        f"_(например: 5 или 10.5)_",
        kb, context
    )
    return WAIT_TON_AMOUNT


async def buy_ton_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_users.add(update.effective_user.id)
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
        context.user_data["ton_amount"] = amount
        ton_rate = RATES["ton"]
        rub_cost = amount * ton_rate
        usd_cost = rub_cost / RATES["usd"]

        await update.message.reply_text(
            f"💎 *TON: {amount}*\n\n"
            f"Стоимость:\n"
            f"• ₽ Рубли: *{rub_cost:.2f}₽*\n"
            f"• $ Доллары: *{usd_cost:.2f}$*\n\n"
            f"Теперь введите ваш *TON-адрес* для получения:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_ton")]]),
        )
        return WAIT_TON_ADDRESS
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число (например: 5 или 10.5):")
        return WAIT_TON_AMOUNT


async def buy_ton_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    context.user_data["ton_address"] = address
    amount = context.user_data["ton_amount"]
    ton_rate = RATES["ton"]
    rub_cost = amount * ton_rate
    usd_cost = rub_cost / RATES["usd"]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рублями (₽)", callback_data="ton_pay_rub")],
        [InlineKeyboardButton("💵 Долларами (USDT)", callback_data="ton_pay_usdt")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_ton")],
    ])
    await update.message.reply_text(
        f"💎 *Детали покупки TON:*\n\n"
        f"📦 Количество: *{amount} TON*\n"
        f"📬 Адрес получения:\n`{address}`\n\n"
        f"Стоимость:\n"
        f"• ₽ Рубли: *{rub_cost:.2f}₽*\n"
        f"• $ USDT: *{usd_cost:.2f}$*\n\n"
        f"Выберите валюту оплаты:",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def ton_pay_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pay_type = query.data.split("_")[2]   # "rub" or "usdt"
    context.user_data["ton_pay_type"] = pay_type
    amount = context.user_data.get("ton_amount", 0)
    address = context.user_data.get("ton_address", "?")
    ton_rate = RATES["ton"]
    rub_cost = amount * ton_rate
    usd_cost = rub_cost / RATES["usd"]

    if pay_type == "rub":
        pay_str = f"*{rub_cost:.2f}₽*"
        req = (
            f"💳 *Реквизиты для оплаты рублями:*\n\n"
            f"Номер карты:\n`{CARD_NUMBER}`\n\n"
            f"Телефон:\n`{CARD_PHONE}`\n\n"
            f"Банк: *Сбербанк*"
        )
        pay_amount = rub_cost
    else:
        pay_str = f"*{usd_cost:.2f} USDT*"
        req = (
            f"💎 *Адрес для оплаты USDT (TRC20/TON):*\n\n"
            f"`{CRYPTO_ADDRESS}`"
        )
        pay_amount = usd_cost

    context.user_data["ton_pay_amount"] = pay_amount
    context.user_data["ton_pay_currency"] = "rub" if pay_type == "rub" else "usd"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_ton")],
    ])

    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)

    await send_menu_msg(
        cid, uid,
        f"📋 *Финальные детали заказа TON:*\n\n"
        f"💎 Покупаете: *{amount} TON*\n"
        f"📬 Адрес получения:\n`{address}`\n"
        f"💰 К оплате: {pay_str}\n\n"
        f"{req}\n\n"
        f"После оплаты нажмите кнопку:",
        kb, context, photo=banner_file_id
    )


async def paid_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    amount = context.user_data.get("ton_amount", 0)
    address = context.user_data.get("ton_address", "?")
    pay_amount = context.user_data.get("ton_pay_amount", 0)
    pay_currency = context.user_data.get("ton_pay_currency", "rub")
    pay_type = context.user_data.get("ton_pay_type", "rub")
    sym = "₽" if pay_currency == "rub" else " USDT"

    order_id = f"ton_{user.id}_{int(amount * 100)}"
    pending_ton_orders[order_id] = {
        "user_id": user.id, "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "ton_amount": amount, "address": address,
        "pay_amount": pay_amount, "pay_currency": pay_currency, "symbol": sym,
    }
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Оплата пришла", callback_data=f"confirm_ton_{order_id}")],
        [InlineKeyboardButton("❌ Не пришла", callback_data=f"decline_ton_{order_id}")],
    ])
    await notify_admins(
        context,
        f"🔔 *Новая покупка TON!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💎 TON: *{amount}*\n"
        f"📬 Адрес: `{address}`\n"
        f"💰 Сумма: *{pay_amount}{sym}*",
        admin_kb
    )
    await cb_send_menu(
        query,
        "⏳ *Заявка на покупку TON отправлена!*\n\n"
        "Администратор проверит оплату и отправит TON на ваш адрес.\n\n"
        "⏱ Обычно до 30 минут",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context
    )


async def admin_confirm_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await query.answer()
    action, order_id = query.data.split("_ton_", 1)
    order = pending_ton_orders.get(order_id)
    if not order:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return
    uid = order["user_id"]
    if action == "confirm":
        if uid in user_referrals:
            ref_id = user_referrals[uid]
            bonus = order["ton_amount"] * RATES["ton"] * 0.03
            add_balance(ref_id, bonus)
            referral_earnings[ref_id] = referral_earnings.get(ref_id, 0) + bonus
            try:
                await context.bot.send_message(
                    ref_id,
                    f"🎉 *Реферальный бонус!*\n\nВаш реферал купил TON.\n"
                    f"Начислено: *+{bonus:.2f}₽*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        await context.bot.send_message(
            uid,
            f"✅ *Покупка TON подтверждена!*\n\n"
            f"💎 *{order['ton_amount']} TON* будут отправлены на адрес:\n"
            f"`{order['address']}`\n\n"
            f"Спасибо! 🙏",
            parse_mode="Markdown"
        )
        await query.edit_message_text(
            f"✅ TON подтверждён!\n{order['username_tg']} | {order['ton_amount']} TON"
        )
    else:
        await context.bot.send_message(
            uid,
            "❌ *Оплата TON не найдена.*\nОбратитесь в поддержку.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(f"❌ TON отклонён!\n{order['username_tg']}")
    del pending_ton_orders[order_id]


# ==================== ПОПОЛНЕНИЕ ====================

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    balance = get_balance(query.from_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рублями (₽)", callback_data="deposit_rub")],
        [InlineKeyboardButton("💵 Долларами ($)", callback_data="deposit_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="deposit_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])
    await cb_send_menu(
        query,
        f"💰 *Пополнение баланса*\n\n"
        f"Ваш баланс: *{balance:.2f}₽*\n\n"
        f"*Реквизиты:*\n\n"
        f"💳 Карта (₽):\n`{CARD_NUMBER}`\n"
        f"📱 Телефон:\n`{CARD_PHONE}`\n\n"
        f"💎 TON/USDT:\n`{CRYPTO_ADDRESS}`\n\n"
        f"Выберите валюту пополнения:",
        kb, context
    )


async def deposit_currency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["deposit_currency"] = currency
    syms = {"rub": "₽", "usd": "$", "ton": "TON"}
    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)
    msg = await context.bot.send_message(
        chat_id=cid,
        text=f"💰 Введите сумму пополнения в *{syms[currency]}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="deposit")]])
    )
    last_menu_msg[uid] = msg.message_id
    return WAIT_DEPOSIT_AMOUNT


async def deposit_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
        context.user_data["deposit_amount"] = amount
        currency = context.user_data["deposit_currency"]
        syms = {"rub": "₽", "usd": "$", "ton": "TON"}
        sym = syms[currency]
        req = (
            f"💳 Карта:\n`{CARD_NUMBER}`\nТел: `{CARD_PHONE}`"
            if currency == "rub"
            else f"💎 TON/USDT:\n`{CRYPTO_ADDRESS}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Я пополнил", callback_data="confirm_deposit")],
            [InlineKeyboardButton("◀️ Отмена", callback_data="deposit")],
        ])
        await update.message.reply_text(
            f"📋 *Детали пополнения:*\n\n"
            f"💰 Сумма: *{amount}{sym}*\n\n{req}\n\n"
            f"После перевода нажмите кнопку:",
            parse_mode="Markdown", reply_markup=kb
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму:")
        return WAIT_DEPOSIT_AMOUNT


async def confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    amount = context.user_data.get("deposit_amount", 0)
    currency = context.user_data.get("deposit_currency", "rub")
    syms = {"rub": "₽", "usd": "$", "ton": " TON"}
    sym = syms.get(currency, "")
    amount_rub = amount * RATES.get(currency, 1)
    dep_id = f"dep_{user.id}_{int(amount * 100)}"
    pending_deposits[dep_id] = {
        "user_id": user.id, "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "amount": amount, "currency": currency, "symbol": sym, "amount_rub": amount_rub,
    }
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_dep_{dep_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_dep_{dep_id}")],
    ])
    await notify_admins(
        context,
        f"🔔 *Заявка на пополнение!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{sym}*\n💵 В рублях: *≈{amount_rub:.2f}₽*",
        admin_kb
    )
    await cb_send_menu(
        query,
        "⏳ *Заявка на пополнение отправлена!*\n\nАдминистратор проверит платёж.\nБаланс пополнится после подтверждения.",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context
    )


async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await query.answer()
    parts = query.data.split("_dep_", 1)
    action, dep_id = parts[0], parts[1]
    dep = pending_deposits.get(dep_id)
    if not dep:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return
    uid = dep["user_id"]
    if action == "confirm":
        add_balance(uid, dep["amount_rub"])
        await context.bot.send_message(
            uid,
            f"✅ *Баланс пополнен!*\n\n"
            f"Зачислено: *+{dep['amount_rub']:.2f}₽*\n"
            f"Текущий баланс: *{get_balance(uid):.2f}₽*",
            parse_mode="Markdown"
        )
        await query.edit_message_text(f"✅ Подтверждено!\n{dep['username_tg']} +{dep['amount_rub']:.2f}₽")
    else:
        await context.bot.send_message(uid, "❌ *Пополнение отклонено.*\nОбратитесь в поддержку.", parse_mode="Markdown")
        await query.edit_message_text(f"❌ Отклонено!\n{dep['username_tg']}")
    del pending_deposits[dep_id]


# ==================== ВЫВОД ====================

async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    balance = get_balance(uid)
    if balance < 100:
        await cb_send_menu(
            query,
            f"❌ *Недостаточно средств*\n\nБаланс: *{balance:.2f}₽*\nМинимум: *100₽*",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
            context
        )
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рублями (₽)", callback_data="withdraw_rub")],
        [InlineKeyboardButton("💵 Долларами ($)", callback_data="withdraw_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="withdraw_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])
    await cb_send_menu(
        query,
        f"💸 *Вывод средств*\n\nБаланс: *{balance:.2f}₽*\nМинимум: 100₽\n\nВыберите валюту:",
        kb, context
    )


async def withdraw_currency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split("_")[1]
    context.user_data["withdraw_currency"] = currency
    syms = {"rub": "₽", "usd": "$", "ton": "TON"}
    uid = query.from_user.id
    cid = query.message.chat_id
    try:
        await query.message.delete()
    except Exception:
        pass
    last_menu_msg.pop(uid, None)
    msg = await context.bot.send_message(
        chat_id=cid,
        text=f"💸 Введите сумму вывода в *{syms[currency]}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="withdraw")]])
    )
    last_menu_msg[uid] = msg.message_id
    return WAIT_WITHDRAW_AMOUNT


async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        currency = context.user_data["withdraw_currency"]
        amount_rub = amount * RATES.get(currency, 1)
        balance = get_balance(update.effective_user.id)
        syms = {"rub": "₽", "usd": "$", "ton": "TON"}
        if amount_rub > balance:
            await update.message.reply_text(
                f"❌ Недостаточно средств!\nБаланс: {balance:.2f}₽, нужно: {amount_rub:.2f}₽\nВведите меньше:"
            )
            return WAIT_WITHDRAW_AMOUNT
        context.user_data["withdraw_amount"] = amount
        context.user_data["withdraw_amount_rub"] = amount_rub
        await update.message.reply_text(
            f"💸 Введите реквизиты для вывода *{amount}{syms[currency]}*:\n_(номер карты / адрес кошелька)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="withdraw")]])
        )
        return WAIT_WITHDRAW_DETAILS
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму:")
        return WAIT_WITHDRAW_AMOUNT


async def withdraw_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    user = update.effective_user
    amount = context.user_data["withdraw_amount"]
    amount_rub = context.user_data["withdraw_amount_rub"]
    currency = context.user_data["withdraw_currency"]
    syms = {"rub": "₽", "usd": "$", "ton": " TON"}
    sym = syms[currency]
    wd_id = f"wd_{user.id}_{int(amount * 100)}"
    pending_withdrawals[wd_id] = {
        "user_id": user.id, "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "amount": amount, "amount_rub": amount_rub, "currency": currency, "symbol": sym, "details": details,
    }
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выплатить", callback_data=f"confirm_wd_{wd_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_wd_{wd_id}")],
    ])
    await notify_admins(
        context,
        f"🔔 *Заявка на вывод!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{sym}*\n💵 В рублях: *{amount_rub:.2f}₽*\n"
        f"📋 Реквизиты:\n`{details}`",
        admin_kb
    )
    await update.message.reply_text(
        "⏳ *Заявка на вывод отправлена!*\n\nАдмин обработает в течение 24 часов.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
    )
    return ConversationHandler.END


async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await query.answer()
    parts = query.data.split("_wd_", 1)
    action, wd_id = parts[0], parts[1]
    wd = pending_withdrawals.get(wd_id)
    if not wd:
        await query.edit_message_text("⚠️ Заявка не найдена")
        return
    uid = wd["user_id"]
    if action == "confirm":
        add_balance(uid, -wd["amount_rub"])
        await context.bot.send_message(
            uid,
            f"✅ *Вывод выполнен!*\n\n"
            f"*{wd['amount']}{wd['symbol']}* отправлено на ваши реквизиты.\n"
            f"Остаток: *{get_balance(uid):.2f}₽*",
            parse_mode="Markdown"
        )
        await query.edit_message_text(f"✅ Выплачено!\n{wd['username_tg']} {wd['amount']}{wd['symbol']}")
    else:
        await context.bot.send_message(uid, "❌ *Вывод отклонён.*\nОбратитесь в поддержку.", parse_mode="Markdown")
        await query.edit_message_text(f"❌ Отклонено!\n{wd['username_tg']}")
    del pending_withdrawals[wd_id]


# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    bot_username = BOT_USERNAME.lstrip("@")
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    ref_count = sum(1 for v in user_referrals.values() if v == user.id)
    earned = referral_earnings.get(user.id, 0)
    await cb_send_menu(
        query,
        f"👥 *Реферальная система*\n\n"
        f"💡 Зарабатывайте *3%* с каждой покупки вашего реферала!\n"
        f"_(работает для звёзд и TON)_\n\n"
        f"🔗 Ваша ссылка:\n`{ref_link}`\n\n"
        f"📊 *Статистика:*\n"
        f"• Приглашено: *{ref_count}*\n"
        f"• Заработано: *{earned:.2f}₽*\n"
        f"• Баланс: *{get_balance(user.id):.2f}₽*\n\n"
        f"_По своей ссылке перейти нельзя_",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        context
    )


# ==================== ИНФОРМАЦИЯ ====================

async def info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])
    await cb_send_menu(
        query,
        f"ℹ️ *О сервисе {BOT_NAME}*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🏆 *КТО МЫ*\n\n"
        f"{BOT_NAME} — профессиональный и проверенный сервис по покупке "
        "Telegram Stars и TON. Мы обеспечиваем быстрое, безопасное и "
        "честное проведение всех операций. Каждый клиент для нас важен.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ *БЕЗОПАСНОСТЬ И ЗАЩИТА*\n\n"
        "Безопасность ваших средств — наш главный приоритет. "
        "Мы используем ручную проверку каждой транзакции. "
        "Все платёжные данные применяются только для проведения "
        "конкретной операции и не передаются третьим лицам.\n\n"
        "Наша команда работает в круглосуточном режиме, обеспечивая "
        "максимально быструю обработку заявок.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *СКОРОСТЬ РАБОТЫ*\n\n"
        "• Подтверждение оплаты ⭐: 5–30 минут\n"
        "• Отправка звёзд: сразу после подтверждения\n"
        "• Подтверждение оплаты TON: 5–30 минут\n"
        "• Отправка TON: до 30 минут\n"
        "• Пополнение баланса: до 30 минут\n"
        "• Вывод средств: до 24 часов\n"
        "• Ответ поддержки: до 2 часов\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *ГАРАНТИИ КАЧЕСТВА*\n\n"
        "✅ Только реальные Telegram Stars — без накруток\n"
        "✅ Реальный TON — без задержек\n"
        "✅ Гарантия доставки: если не дошло — вернём деньги\n"
        "✅ Прозрачная история операций на балансе\n"
        "✅ Приём 3 валют: ₽, $, TON\n"
        "✅ Реферальная программа: 3% с покупок рефералов\n"
        "✅ Вывод на карту или крипто-кошелёк\n"
        "✅ Поддержка 7 дней в неделю\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 *РЕФЕРАЛЬНАЯ ПРОГРАММА*\n\n"
        "Приглашайте друзей по уникальной ссылке и получайте "
        "*3%* с каждой их покупки автоматически. Работает и для "
        "звёзд, и для TON. Бонусы зачисляются мгновенно.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 *ТАРИФЫ И УСЛОВИЯ*\n\n"
        f"• Курс звёзд: *1 ⭐ = {STARS_PRICE_RUB}₽*\n"
        f"• Курс TON: *1 TON = {RATES['ton']:.0f}₽*\n"
        f"• Минимум покупки ⭐: *50 звёзд*\n"
        f"• Минимум покупки TON: *без ограничений*\n"
        f"• Минимум вывода: *100₽*\n"
        f"• Реферальный бонус: *3%*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 *ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ*\n\n"
        "Мы не собираем, не продаём и не передаём личные данные "
        "третьим лицам. Ваши реквизиты хранятся только до момента "
        "проведения транзакции.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📞 *ПОДДЕРЖКА*\n\n"
        f"По всем вопросам и спорным ситуациям:\n"
        f"👉 {SUPPORT_USERNAME}\n\n"
        f"_{BOT_NAME} — ваш надёжный партнёр_ ⚡",
        kb, context
    )


# ==================== АДМИН-ПАНЕЛЬ ====================

def admin_panel_text():
    total_users = len(all_users)
    total_balance = sum(user_balances.values())
    return (
        f"🔧 *Админ-панель {BOT_NAME}*\n\n"
        f"👥 Пользователей: *{total_users}*\n"
        f"💰 Суммарный баланс: *{total_balance:.2f}₽*\n"
        f"⏳ Ожидают оплаты ⭐: *{len(pending_payments)}*\n"
        f"⏳ Ожидают оплаты TON: *{len(pending_ton_orders)}*\n"
        f"⏳ Ожидают пополнения: *{len(pending_deposits)}*\n"
        f"⏳ Ожидают вывода: *{len(pending_withdrawals)}*\n\n"
        f"🖼️ Баннер: *{'установлен ✅' if banner_file_id else 'не установлен ❌'}*\n"
        f"⭐ Курс звёзд: *1 ⭐ = {STARS_PRICE_RUB}₽*\n"
        f"💎 Курс TON: *1 TON = {RATES['ton']:.0f}₽*\n\n"
        f"👑 Администраторы: {', '.join(str(x) for x in ADMIN_IDS)}"
    )


def admin_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Установить баннер", callback_data="admin_set_banner"),
         InlineKeyboardButton("🗑️ Удалить баннер", callback_data="admin_del_banner")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Курс звёзд ⭐", callback_data="admin_edit_price"),
         InlineKeyboardButton("💎 Курс TON", callback_data="admin_edit_ton_price")],
        [InlineKeyboardButton("👤 Изменить баланс", callback_data="admin_edit_balance")],
        [InlineKeyboardButton("✉️ Написать пользователю", callback_data="admin_msg_user")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(query, admin_panel_text(), admin_panel_kb(), context)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    await send_menu_msg(
        update.effective_chat.id, update.effective_user.id,
        admin_panel_text(), admin_panel_kb(), context
    )


# --- Установить баннер ---

async def admin_set_banner_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "🖼️ *Установка баннера*\n\nОтправьте фото-баннер.\nОн будет показан во всех сообщениях.",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_SET_BANNER


async def admin_set_banner_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global banner_file_id
    if not is_admin(update.effective_user.id):
        return
    if update.message.photo:
        banner_file_id = update.message.photo[-1].file_id
        await update.message.reply_text(
            "✅ *Баннер установлен!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Отправьте именно фото:")
        return WAIT_ADMIN_SET_BANNER


async def admin_del_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global banner_file_id
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await query.answer()
    banner_file_id = None
    try:
        await query.message.delete()
    except Exception:
        pass
    msg = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="🗑️ *Баннер удалён.*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
    )
    last_menu_msg[query.from_user.id] = msg.message_id


# --- Рассылка ---

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "📢 *Рассылка*\n\nОтправьте сообщение (текст или фото с подписью):",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_BROADCAST


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    success, fail = 0, 0
    photo = update.message.photo
    caption = update.message.caption or ""
    text = update.message.text or ""
    for uid in list(all_users):
        try:
            if photo:
                await context.bot.send_photo(chat_id=uid, photo=photo[-1].file_id, caption=caption, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
            success += 1
        except Exception:
            fail += 1
    await update.message.reply_text(
        f"📢 *Рассылка завершена!*\n\n✅ Доставлено: {success}\n❌ Ошибок: {fail}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
    )
    return ConversationHandler.END


# --- Изменить курс звёзд ---

async def admin_edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        f"⭐ *Изменение курса звёзд*\n\nТекущий курс: *1 ⭐ = {STARS_PRICE_RUB}₽*\n\nВведите новый курс:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_EDIT_PRICE


async def admin_edit_price_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STARS_PRICE_RUB
    if not is_admin(update.effective_user.id):
        return
    try:
        new_price = float(update.message.text.strip().replace(",", "."))
        if new_price <= 0:
            raise ValueError
        STARS_PRICE_RUB = new_price
        await update.message.reply_text(
            f"✅ Курс звёзд обновлён!\n*1 ⭐ = {STARS_PRICE_RUB}₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WAIT_ADMIN_EDIT_PRICE


# --- Изменить курс TON ---

async def admin_edit_ton_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        f"💎 *Изменение курса TON*\n\nТекущий курс: *1 TON = {RATES['ton']:.0f}₽*\n\nВведите новый курс:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_EDIT_TON_PRICE


async def admin_edit_ton_price_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        new_price = float(update.message.text.strip().replace(",", "."))
        if new_price <= 0:
            raise ValueError
        RATES["ton"] = new_price
        await update.message.reply_text(
            f"✅ Курс TON обновлён!\n*1 TON = {RATES['ton']:.0f}₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WAIT_ADMIN_EDIT_TON_PRICE


# --- Изменить баланс пользователя ---

async def admin_edit_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "👤 *Изменение баланса*\n\nВведите Telegram ID пользователя:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_BALANCE_USER


async def admin_balance_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_uid"] = uid
        current = get_balance(uid)
        await update.message.reply_text(
            f"💰 Баланс пользователя *{uid}*: *{current:.2f}₽*\n\n"
            f"Введите:\n• `+100` — добавить\n• `-50` — вычесть\n• `500` — установить",
            parse_mode="Markdown"
        )
        return WAIT_ADMIN_BALANCE_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введите корректный числовой ID:")
        return WAIT_ADMIN_BALANCE_USER


async def admin_balance_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = context.user_data.get("admin_target_uid")
    text = update.message.text.strip()
    try:
        if text.startswith("+"):
            amt = float(text[1:])
            add_balance(uid, amt)
            action = f"+{amt:.2f}₽"
        elif text.startswith("-"):
            amt = float(text[1:])
            add_balance(uid, -amt)
            action = f"-{amt:.2f}₽"
        else:
            amt = float(text)
            user_balances[uid] = amt
            action = f"установлен {amt:.2f}₽"
        try:
            await context.bot.send_message(
                uid,
                f"💰 *Ваш баланс изменён администратором!*\nНовый баланс: *{get_balance(uid):.2f}₽*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text(
            f"✅ Баланс *{uid}* {action}\nНовый: *{get_balance(uid):.2f}₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму:")
        return WAIT_ADMIN_BALANCE_AMOUNT


# --- Написать пользователю ---

async def admin_msg_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "✉️ *Сообщение пользователю*\n\nВведите Telegram ID:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_MSG_USER_ID


async def admin_msg_user_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_msg_uid"] = uid
        await update.message.reply_text(f"✉️ Введите текст для *{uid}*:", parse_mode="Markdown")
        return WAIT_ADMIN_MSG_TEXT
    except ValueError:
        await update.message.reply_text("❌ Введите корректный ID:")
        return WAIT_ADMIN_MSG_USER_ID


async def admin_msg_user_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = context.user_data.get("admin_msg_uid")
    try:
        await context.bot.send_message(
            uid,
            f"📩 *Сообщение от администратора:*\n\n{update.message.text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"✅ Отправлено пользователю *{uid}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    return ConversationHandler.END


# --- Статистика ---

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    top = sorted(user_balances.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = "\n".join([f"  `{uid}`: {bal:.2f}₽" for uid, bal in top]) or "  нет данных"
    await cb_send_menu(
        query,
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: *{len(all_users)}*\n"
        f"💰 Суммарный баланс: *{sum(user_balances.values()):.2f}₽*\n"
        f"⏳ Ожидают оплаты ⭐: *{len(pending_payments)}*\n"
        f"⏳ Ожидают оплаты TON: *{len(pending_ton_orders)}*\n"
        f"⏳ Ожидают пополнения: *{len(pending_deposits)}*\n"
        f"⏳ Ожидают вывода: *{len(pending_withdrawals)}*\n\n"
        f"🏆 *Топ балансов:*\n{top_str}",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]]),
        context
    )


# ==================== КОМАНДЫ ИЗ МЕНЮ ====================

async def setup_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start",    "🏠 Главное меню"),
        BotCommand("buy",      "⭐ Купить звёзды"),
        BotCommand("buyton",   "💎 Купить TON"),
        BotCommand("balance",  "💰 Мой баланс"),
        BotCommand("deposit",  "💳 Пополнить баланс"),
        BotCommand("withdraw", "💸 Вывести средства"),
        BotCommand("referral", "👥 Реферальная программа"),
        BotCommand("info",     "ℹ️ Информация о сервисе"),
        BotCommand("support",  "🆘 Поддержка"),
        BotCommand("admin",    "🔧 Панель администратора"),
    ])


async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_users.add(update.effective_user.id)
    await send_menu_msg(
        update.effective_chat.id, update.effective_user.id,
        "⭐ *Покупка звёзд*\n\nВведите количество звёзд:\n_(минимум 50 звёзд)_",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        context, photo=banner_file_id
    )


async def buyton_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_users.add(update.effective_user.id)
    await send_menu_msg(
        update.effective_chat.id, update.effective_user.id,
        f"💎 *Покупка TON*\n\nКурс: *1 TON = {RATES['ton']:.0f}₽*\n\nВведите количество TON:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        context, photo=banner_file_id
    )


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    balance = get_balance(user.id)
    await send_menu_msg(
        update.effective_chat.id, user.id,
        f"💰 *Ваш баланс*\n\nДоступно: *{balance:.2f}₽*",
        main_menu_keyboard(user.id), context, photo=banner_file_id
    )


async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    bot_username = BOT_USERNAME.lstrip("@")
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    ref_count = sum(1 for v in user_referrals.values() if v == user.id)
    earned = referral_earnings.get(user.id, 0)
    await send_menu_msg(
        update.effective_chat.id, user.id,
        f"👥 *Реферальная система*\n\n🔗 Ваша ссылка:\n`{ref_link}`\n\n"
        f"• Приглашено: *{ref_count}*\n• Заработано: *{earned:.2f}₽*",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context, photo=banner_file_id
    )


async def deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    balance = get_balance(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рублями (₽)", callback_data="deposit_rub")],
        [InlineKeyboardButton("💵 Долларами ($)", callback_data="deposit_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="deposit_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])
    await send_menu_msg(
        update.effective_chat.id, user.id,
        f"💰 *Пополнение баланса*\n\nБаланс: *{balance:.2f}₽*\n\n"
        f"💳 Карта:\n`{CARD_NUMBER}`\nТел: `{CARD_PHONE}`\n\n"
        f"💎 TON/USDT:\n`{CRYPTO_ADDRESS}`\n\nВыберите валюту:",
        kb, context, photo=banner_file_id
    )


async def withdraw_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    balance = get_balance(user.id)
    if balance < 100:
        await update.message.reply_text(f"❌ Недостаточно средств!\nБаланс: *{balance:.2f}₽*", parse_mode="Markdown")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рублями (₽)", callback_data="withdraw_rub")],
        [InlineKeyboardButton("💵 Долларами ($)", callback_data="withdraw_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="withdraw_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ])
    await send_menu_msg(
        update.effective_chat.id, user.id,
        f"💸 *Вывод средств*\n\nБаланс: *{balance:.2f}₽*\n\nВыберите валюту:",
        kb, context, photo=banner_file_id
    )


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    await send_menu_msg(
        update.effective_chat.id, user.id,
        f"ℹ️ *{BOT_NAME}*\n\n⭐ 1 звезда = {STARS_PRICE_RUB}₽\n💎 1 TON = {RATES['ton']:.0f}₽\n📞 {SUPPORT_USERNAME}",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🆘 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ]),
        context, photo=banner_file_id
    )


async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆘 *Поддержка {BOT_NAME}*\n\n👉 {SUPPORT_USERNAME}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Написать", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ])
    )


# ==================== MAIN ====================

def main():
    app = Application.builder().token(TOKEN).post_init(setup_commands).build()

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_stars_start, pattern="^buy_stars$")],
        states={
            WAIT_STARS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_count)],
            WAIT_BUY_TYPE: [CallbackQueryHandler(buy_type_selected, pattern="^buy_type_(self|anon)$")],
            WAIT_TARGET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_username)],
            WAIT_CURRENCY: [CallbackQueryHandler(buy_stars_currency, pattern="^currency_(rub|usd|ton)$")],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    ton_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_ton_start, pattern="^buy_ton$")],
        states={
            WAIT_TON_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_ton_amount)],
            WAIT_TON_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_ton_address)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_currency_selected, pattern="^deposit_(rub|usd|ton)$")],
        states={WAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_received)]},
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_currency_selected, pattern="^withdraw_(rub|usd|ton)$")],
        states={
            WAIT_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_received)],
            WAIT_WITHDRAW_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_details_received)],
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(show_main_menu, pattern="^main_menu$")],
        per_message=False,
    )

    banner_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_banner_start, pattern="^admin_set_banner$")],
        states={WAIT_ADMIN_SET_BANNER: [MessageHandler(filters.PHOTO, admin_set_banner_photo)]},
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            WAIT_ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send),
                MessageHandler(filters.PHOTO, admin_broadcast_send),
            ]
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_price_start, pattern="^admin_edit_price$")],
        states={WAIT_ADMIN_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_price_set)]},
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    ton_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_ton_price_start, pattern="^admin_edit_ton_price$")],
        states={WAIT_ADMIN_EDIT_TON_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_ton_price_set)]},
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    balance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_balance_start, pattern="^admin_edit_balance$")],
        states={
            WAIT_ADMIN_BALANCE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_balance_user_received)],
            WAIT_ADMIN_BALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_balance_amount_received)],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    msg_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_msg_user_start, pattern="^admin_msg_user$")],
        states={
            WAIT_ADMIN_MSG_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_user_id_received)],
            WAIT_ADMIN_MSG_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_user_text_received)],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_panel$")],
        per_message=False,
    )

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("buyton", buyton_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("referral", referral_cmd))
    app.add_handler(CommandHandler("deposit", deposit_cmd))
    app.add_handler(CommandHandler("withdraw", withdraw_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("support", support_cmd))

    # Conversations
    app.add_handler(buy_conv)
    app.add_handler(ton_conv)
    app.add_handler(deposit_conv)
    app.add_handler(withdraw_conv)
    app.add_handler(banner_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(price_conv)
    app.add_handler(ton_price_conv)
    app.add_handler(balance_conv)
    app.add_handler(msg_user_conv)

    # Callbacks
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(buy_type_selected, pattern="^buy_type_(self|anon)$"))
    app.add_handler(CallbackQueryHandler(paid_stars, pattern="^paid_stars$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern="^(confirm|decline)_payment_"))
    app.add_handler(CallbackQueryHandler(ton_pay_currency, pattern="^ton_pay_(rub|usdt)$"))
    app.add_handler(CallbackQueryHandler(paid_ton, pattern="^paid_ton$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_ton, pattern="^(confirm|decline)_ton_"))
    app.add_handler(CallbackQueryHandler(deposit_menu, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(confirm_deposit, pattern="^confirm_deposit$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_deposit, pattern="^(confirm|decline)_dep_"))
    app.add_handler(CallbackQueryHandler(withdraw_menu, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_withdrawal, pattern="^(confirm|decline)_wd_"))
    app.add_handler(CallbackQueryHandler(referral_menu, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(info_menu, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_del_banner, pattern="^admin_del_banner$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))

    print(f"✅ {BOT_NAME} запущен!")
    print(f"🤖 Бот: {BOT_USERNAME}")
    print(f"👑 Администраторы: {ADMIN_IDS}")
    app.run_polling()


if __name__ == "__main__":
    main()
