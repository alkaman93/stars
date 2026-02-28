import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8676951864:AAFre_ZY7CI85TKvfoI3yxqRWowoj5daO0s"
ADMIN_ID = 1208378923  # ← ЗАМЕНИТЕ НА ВАШ TELEGRAM ID

SUPPORT_USERNAME = "@Scronexcyyy"

# Реквизиты
CRYPTO_ADDRESS = "UQDUUFncBcWC4eH3wN_4G3N9Yaf6nBFlcumDP8daYAQHNSOc"
CARD_NUMBER = "2200702051809809"
CARD_PHONE = "+79242143705"
STARS_PRICE_RUB = 1.3

# Конвертация (1 единица = ? рублей)
RATES = {"rub": 1.0, "usd": 90.0, "ton": 550.0}

# Состояния
(
    WAIT_STARS_COUNT, WAIT_TARGET_USERNAME, WAIT_CURRENCY,
    WAIT_DEPOSIT_AMOUNT,
    WAIT_WITHDRAW_AMOUNT, WAIT_WITHDRAW_DETAILS,
    WAIT_ADMIN_BROADCAST,
    WAIT_ADMIN_SET_BANNER,
    WAIT_ADMIN_EDIT_PRICE,
    WAIT_ADMIN_BALANCE_USER, WAIT_ADMIN_BALANCE_AMOUNT,
    WAIT_ADMIN_MSG_USER_ID, WAIT_ADMIN_MSG_TEXT,
) = range(13)

# Хранилище
user_balances = {}
user_referrals = {}
referral_earnings = {}
pending_payments = {}
pending_deposits = {}
pending_withdrawals = {}
all_users = set()
last_menu_msg = {}  # {user_id: message_id} — для удаления предыдущего
banner_file_id = None  # file_id фото-баннера


# ==================== УТИЛИТЫ ====================

def get_balance(uid): return user_balances.get(uid, 0.0)
def add_balance(uid, amt): user_balances[uid] = get_balance(uid) + amt


def main_menu_keyboard(is_admin=False):
    kb = [
        [InlineKeyboardButton("⭐ Купить звёзды", callback_data="buy_stars")],
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
    if is_admin:
        kb.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


async def _delete_prev(user_id, chat_id, context):
    """Удаляет предыдущее меню-сообщение пользователя."""
    mid = last_menu_msg.pop(user_id, None)
    if mid:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass


async def send_menu_msg(chat_id, user_id, text, kb, context, photo=None):
    """Удаляет старое меню и отправляет новое (с баннером или без)."""
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
    """Хелпер для callback-хэндлеров: отвечает на query и показывает меню."""
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

    is_admin = (user.id == ADMIN_ID)
    text = (
        f"✨ *Добро пожаловать в Stars Bulling!*\n\n"
        f"Привет, {user.first_name}! 👋\n\n"
        f"🌟 *Stars Bulling* — быстрый и надёжный сервис\n"
        f"покупки Telegram Stars.\n\n"
        f"⭐ Курс: *1 звезда = {STARS_PRICE_RUB}₽*\n"
        f"💰 Ваш баланс: *{get_balance(user.id):.2f}₽*\n\n"
        f"Выберите действие:"
    )
    await send_menu_msg(
        update.effective_chat.id, user.id, text,
        main_menu_keyboard(is_admin), context, photo=banner_file_id
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    all_users.add(user.id)
    is_admin = (user.id == ADMIN_ID)
    text = (
        f"🏠 *Главное меню — Stars Bulling*\n\n"
        f"⭐ Курс: *1 звезда = {STARS_PRICE_RUB}₽*\n"
        f"💰 Ваш баланс: *{get_balance(user.id):.2f}₽*\n\n"
        f"Выберите действие:"
    )
    await cb_send_menu(query, text, main_menu_keyboard(is_admin), context)


# ==================== ПОКУПКА ЗВЁЗД ====================

async def buy_stars_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
    await cb_send_menu(
        query,
        "⭐ *Покупка звёзд*\n\n"
        "Введите количество звёзд, которое хотите купить:\n"
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
        await update.message.reply_text(
            "👤 Введите *@юзернейм* получателя звёзд:\n_(например: @username)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")]]),
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
    stars = context.user_data["stars_count"]
    rub = stars * STARS_PRICE_RUB
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Рубли (₽)", callback_data="currency_rub")],
        [InlineKeyboardButton("💵 Доллары ($)", callback_data="currency_usd")],
        [InlineKeyboardButton("💎 TON", callback_data="currency_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_stars")],
    ])
    await update.message.reply_text(
        f"💳 *Выберите валюту оплаты:*\n\n"
        f"⭐ Звёзды: *{stars}*\n"
        f"👤 Получатель: *{username}*\n\n"
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
    msg = await send_menu_msg(cid, uid, text, kb, context, photo=banner_file_id)
    return ConversationHandler.END


async def paid_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    stars = context.user_data.get("stars_count", "?")
    username = context.user_data.get("target_username", "?")
    currency = context.user_data.get("currency", "?")
    amount = context.user_data.get("amount", 0)
    syms = {"rub": "₽", "usd": "$", "ton": " TON"}
    sym = syms.get(currency, "")
    order_id = f"{user.id}_{stars}_{int(float(amount) * 100)}"
    pending_payments[order_id] = {
        "user_id": user.id, "user_name": user.full_name,
        "username_tg": f"@{user.username}" if user.username else f"ID:{user.id}",
        "stars": stars, "target": username, "currency": currency, "amount": amount, "symbol": sym,
    }
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Оплата пришла", callback_data=f"confirm_payment_{order_id}")],
        [InlineKeyboardButton("❌ Не пришла", callback_data=f"decline_payment_{order_id}")],
    ])
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Новая оплата за звёзды!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"⭐ Звёзд: *{stars}*\n📨 Получатель: *{username}*\n"
        f"💰 Сумма: *{amount}{sym}*\n💳 Валюта: *{currency.upper()}*",
        parse_mode="Markdown", reply_markup=admin_kb
    )
    await cb_send_menu(
        query,
        "⏳ *Заявка отправлена на проверку!*\n\n"
        "Администратор проверит ваш платёж.\n"
        "Звёзды отправят после подтверждения.\n\n"
        "Обычно это занимает до 15 минут ⏱",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context
    )


async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
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
            "❌ *Оплата не найдена.*\n\nПлатёж не подтверждён.\nОбратитесь в поддержку.",
            parse_mode="Markdown"
        )
        await query.edit_message_text(f"❌ Отклонено!\n{payment['username_tg']}")
    del pending_payments[order_id]


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
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Заявка на пополнение!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{sym}*\n💵 В рублях: *≈{amount_rub:.2f}₽*",
        parse_mode="Markdown", reply_markup=admin_kb
    )
    await cb_send_menu(
        query,
        "⏳ *Заявка на пополнение отправлена!*\n\n"
        "Администратор проверит платёж.\n"
        "Баланс пополнится после подтверждения.",
        InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]),
        context
    )


async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
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
            f"❌ *Недостаточно средств*\n\nБаланс: *{balance:.2f}₽*\nМинимум вывода: *100₽*",
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
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *Заявка на вывод!*\n\n"
        f"👤 {user.full_name} ({f'@{user.username}' if user.username else f'ID:{user.id}'})\n"
        f"💰 Сумма: *{amount}{sym}*\n💵 В рублях: *{amount_rub:.2f}₽*\n"
        f"📋 Реквизиты:\n`{details}`",
        parse_mode="Markdown", reply_markup=admin_kb
    )
    await update.message.reply_text(
        "⏳ *Заявка на вывод отправлена!*\n\nАдмин обработает в течение 24 часов.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]])
    )
    return ConversationHandler.END


async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
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
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    ref_count = sum(1 for v in user_referrals.values() if v == user.id)
    earned = referral_earnings.get(user.id, 0)
    await cb_send_menu(
        query,
        f"👥 *Реферальная система*\n\n"
        f"💡 Зарабатывайте *3%* с каждой покупки вашего реферала!\n\n"
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
        "ℹ️ *О сервисе Stars Bulling*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🏆 *КТО МЫ*\n\n"
        "Stars Bulling — профессиональный и проверенный сервис по покупке "
        "и продаже Telegram Stars. Мы обеспечиваем быстрое, безопасное и "
        "честное проведение всех операций. Каждый клиент для нас важен, "
        "и мы всегда стремимся превзойти ожидания.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ *БЕЗОПАСНОСТЬ И ЗАЩИТА*\n\n"
        "Безопасность ваших средств и данных — наш главный приоритет. "
        "Мы используем ручную проверку каждой транзакции, что исключает "
        "автоматические сбои и мошенничество. Все платёжные реквизиты "
        "применяются исключительно для проведения конкретной операции "
        "и не передаются третьим лицам.\n\n"
        "Наша система работает по принципу «сначала оплата — потом проверка»: "
        "мы подтверждаем получение средств вручную, что полностью исключает "
        "риск потери денег с нашей стороны.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *СКОРОСТЬ РАБОТЫ*\n\n"
        "• Подтверждение оплаты: 5–30 минут\n"
        "• Отправка звёзд: сразу после подтверждения\n"
        "• Пополнение баланса: до 30 минут\n"
        "• Вывод средств: до 24 часов\n"
        "• Ответ поддержки: до 2 часов\n\n"
        "В ночное время (00:00–08:00 МСК) возможна небольшая задержка. "
        "Мы всегда уведомляем о статусе вашей заявки.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *ГАРАНТИИ КАЧЕСТВА*\n\n"
        "✅ Только реальные Telegram Stars — без накруток и ботов\n"
        "✅ Гарантия доставки: если звёзды не дошли — вернём деньги\n"
        "✅ Прозрачная история всех операций на вашем балансе\n"
        "✅ Приём 3 валют: ₽ (рубли), $ (доллары), TON (крипто)\n"
        "✅ Реферальная программа с моментальным начислением бонусов\n"
        "✅ Вывод средств на карту или крипто-кошелёк\n"
        "✅ Поддержка на связи 7 дней в неделю\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 *РЕФЕРАЛЬНАЯ ПРОГРАММА*\n\n"
        "Приглашайте друзей по своей уникальной ссылке и получайте "
        "*3%* с каждой их покупки автоматически. Бонусы зачисляются "
        "мгновенно на ваш внутренний баланс. Накопленные средства "
        "можно вывести в любое время в удобной валюте.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 *ТАРИФЫ И УСЛОВИЯ*\n\n"
        f"• Курс: *1 ⭐ = {STARS_PRICE_RUB}₽*\n"
        f"• Минимум покупки: *50 звёзд*\n"
        f"• Минимум пополнения баланса: *без ограничений*\n"
        f"• Минимум вывода: *100₽*\n"
        f"• Реферальный бонус: *3% с каждой покупки*\n"
        f"• Конвертация $ → ₽: курс 90₽/$\n"
        f"• Конвертация TON → ₽: курс 550₽/TON\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 *ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ*\n\n"
        "Мы не собираем, не продаём и не передаём личные данные пользователей "
        "третьим лицам. Ваш Telegram ID используется исключительно для "
        "идентификации внутри бота. Платёжные реквизиты хранятся только "
        "до момента проведения транзакции.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📞 *СЛУЖБА ПОДДЕРЖКИ*\n\n"
        "По всем вопросам, спорным ситуациям, жалобам и предложениям:\n"
        f"👉 {SUPPORT_USERNAME}\n\n"
        "Мы рассмотрим каждое обращение и найдём оптимальное решение.\n\n"
        "_Stars Bulling — ваш надёжный партнёр в мире Telegram Stars_ ⭐",
        kb, context
    )


# ==================== АДМИН-ПАНЕЛЬ ====================

def admin_panel_text():
    total_users = len(all_users)
    total_balance = sum(user_balances.values())
    return (
        f"🔧 *Админ-панель Stars Bulling*\n\n"
        f"👥 Пользователей: *{total_users}*\n"
        f"💰 Суммарный баланс: *{total_balance:.2f}₽*\n"
        f"⏳ Ожидают оплаты: *{len(pending_payments)}*\n"
        f"⏳ Ожидают пополнения: *{len(pending_deposits)}*\n"
        f"⏳ Ожидают вывода: *{len(pending_withdrawals)}*\n\n"
        f"🖼️ Баннер: *{'установлен ✅' if banner_file_id else 'не установлен ❌'}*\n"
        f"⭐ Курс: *1 ⭐ = {STARS_PRICE_RUB}₽*"
    )


def admin_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Установить баннер", callback_data="admin_set_banner"),
         InlineKeyboardButton("🗑️ Удалить баннер", callback_data="admin_del_banner")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Изменить курс ⭐", callback_data="admin_edit_price")],
        [InlineKeyboardButton("👤 Изменить баланс юзера", callback_data="admin_edit_balance")],
        [InlineKeyboardButton("✉️ Написать пользователю", callback_data="admin_msg_user")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(query, admin_panel_text(), admin_panel_kb(), context)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа")
        return
    await send_menu_msg(
        update.effective_chat.id, update.effective_user.id,
        admin_panel_text(), admin_panel_kb(), context
    )


# --- Установить баннер ---

async def admin_set_banner_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "🖼️ *Установка баннера*\n\n"
        "Отправьте фото-баннер.\n"
        "Оно будет отображаться во всех сообщениях бота.",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_SET_BANNER


async def admin_set_banner_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global banner_file_id
    if update.effective_user.id != ADMIN_ID:
        return
    if update.message.photo:
        banner_file_id = update.message.photo[-1].file_id
        await update.message.reply_text(
            "✅ *Баннер установлен!*\nОн будет отображаться во всех сообщениях.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Отправьте именно фото (не файл):")
        return WAIT_ADMIN_SET_BANNER


async def admin_del_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global banner_file_id
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
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
        text="🗑️ *Баннер удалён.*\nТеперь бот работает без баннера.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
    )
    last_menu_msg[query.from_user.id] = msg.message_id


# --- Рассылка ---

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "📢 *Рассылка*\n\n"
        "Отправьте сообщение для рассылки.\n"
        "Можно текст, фото с подписью, или просто фото.",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_BROADCAST


async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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


# --- Изменить курс ---

async def admin_edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        f"💰 *Изменение курса*\n\nТекущий курс: *1 ⭐ = {STARS_PRICE_RUB}₽*\n\nВведите новый курс:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_EDIT_PRICE


async def admin_edit_price_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STARS_PRICE_RUB
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        new_price = float(update.message.text.strip().replace(",", "."))
        if new_price <= 0:
            raise ValueError
        STARS_PRICE_RUB = new_price
        await update.message.reply_text(
            f"✅ Курс обновлён!\n*1 ⭐ = {STARS_PRICE_RUB}₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректное число:")
        return WAIT_ADMIN_EDIT_PRICE


# --- Изменить баланс пользователя ---

async def admin_edit_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
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
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_target_uid"] = uid
        current = get_balance(uid)
        await update.message.reply_text(
            f"💰 Баланс пользователя *{uid}*: *{current:.2f}₽*\n\n"
            f"Введите новое значение:\n"
            f"• `+100` — прибавить 100₽\n"
            f"• `-50` — вычесть 50₽\n"
            f"• `500` — установить 500₽",
            parse_mode="Markdown"
        )
        return WAIT_ADMIN_BALANCE_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Введите корректный числовой ID:")
        return WAIT_ADMIN_BALANCE_USER


async def admin_balance_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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
                f"💰 *Ваш баланс изменён администратором!*\n"
                f"Новый баланс: *{get_balance(uid):.2f}₽*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text(
            f"✅ Баланс пользователя *{uid}* {action}\nНовый баланс: *{get_balance(uid):.2f}₽*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму (например: +100, -50, 200):")
        return WAIT_ADMIN_BALANCE_AMOUNT


# --- Написать пользователю ---

async def admin_msg_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    await cb_send_menu(
        query,
        "✉️ *Сообщение пользователю*\n\nВведите Telegram ID пользователя:",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="admin_panel")]]),
        context
    )
    return WAIT_ADMIN_MSG_USER_ID


async def admin_msg_user_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(update.message.text.strip())
        context.user_data["admin_msg_uid"] = uid
        await update.message.reply_text(
            f"✉️ Введите текст сообщения для пользователя *{uid}*:",
            parse_mode="Markdown"
        )
        return WAIT_ADMIN_MSG_TEXT
    except ValueError:
        await update.message.reply_text("❌ Введите корректный числовой ID:")
        return WAIT_ADMIN_MSG_USER_ID


async def admin_msg_user_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = context.user_data.get("admin_msg_uid")
    try:
        await context.bot.send_message(
            uid,
            f"📩 *Сообщение от администратора:*\n\n{update.message.text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"✅ Сообщение отправлено пользователю *{uid}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]])
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")
    return ConversationHandler.END


# --- Статистика ---

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    top = sorted(user_balances.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = "\n".join([f"  `{uid}`: {bal:.2f}₽" for uid, bal in top]) or "  нет данных"
    await cb_send_menu(
        query,
        f"📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: *{len(all_users)}*\n"
        f"💰 Суммарный баланс: *{sum(user_balances.values()):.2f}₽*\n"
        f"⏳ Ожидают оплаты: *{len(pending_payments)}*\n"
        f"⏳ Ожидают пополнения: *{len(pending_deposits)}*\n"
        f"⏳ Ожидают вывода: *{len(pending_withdrawals)}*\n\n"
        f"🏆 *Топ балансов:*\n{top_str}",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В панель", callback_data="admin_panel")]]),
        context
    )


# ==================== MAIN ====================

def main():
    app = Application.builder().token(TOKEN).build()

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_stars_start, pattern="^buy_stars$")],
        states={
            WAIT_STARS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_count)],
            WAIT_TARGET_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_stars_username)],
            WAIT_CURRENCY: [CallbackQueryHandler(buy_stars_currency, pattern="^currency_(rub|usd|ton)$")],
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))

    app.add_handler(buy_conv)
    app.add_handler(deposit_conv)
    app.add_handler(withdraw_conv)
    app.add_handler(banner_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(price_conv)
    app.add_handler(balance_conv)
    app.add_handler(msg_user_conv)

    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(paid_stars, pattern="^paid_stars$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern="^(confirm|decline)_payment_"))
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

    print("✅ Stars Bulling Bot запущен!")
    print(f"⚠️  Замените ADMIN_ID = {ADMIN_ID} на ВАШ Telegram ID!")
    app.run_polling()


if __name__ == "__main__":
    main()
