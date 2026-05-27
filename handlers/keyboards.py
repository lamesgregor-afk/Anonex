from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="🛒 Маркет"), KeyboardButton(text="➕ Продать"))
    kb.row(KeyboardButton(text="📦 Мои покупки"), KeyboardButton(text="📋 Мои товары"))
    kb.row(KeyboardButton(text="💼 Кошелёк"), KeyboardButton(text="👥 Реферальная"))
    return kb.as_markup(resize_keyboard=True)


def listing_card(listing_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Купить", callback_data=f"buy:{listing_id}")
    return kb.as_markup()


def my_listing_card(listing_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Снять с продажи", callback_data=f"del_listing:{listing_id}")
    return kb.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📁 Файл", callback_data="cat:file")
    kb.button(text="🛠 Услуга", callback_data="cat:service")
    kb.button(text="💬 Консультация", callback_data="cat:consultation")
    kb.button(text="🔖 Другое", callback_data="cat:other")
    kb.adjust(2)
    return kb.as_markup()


def order_pay_button(pay_url: str, order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить в CryptoBot", url=pay_url)
    kb.button(text="🔄 Проверить оплату", callback_data=f"check_pay:{order_id}")
    kb.button(text="❌ Отменить", callback_data=f"cancel_order:{order_id}")
    kb.adjust(1)
    return kb.as_markup()


def buyer_delivery_keyboard(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить получение", callback_data=f"confirm:{order_id}")
    kb.button(text="⚠️ Открыть спор", callback_data=f"dispute:{order_id}")
    kb.adjust(1)
    return kb.as_markup()


def seller_deliver_button(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Передать товар/услугу", callback_data=f"deliver:{order_id}")
    return kb.as_markup()


def wallet_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Вывести средства", callback_data="withdraw")
    kb.button(text="📊 История транзакций", callback_data="tx_history")
    kb.adjust(1)
    return kb.as_markup()


def admin_main_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Споры", callback_data="admin:disputes")
    kb.button(text="💸 Выводы", callback_data="admin:withdrawals")
    kb.button(text="📊 Транзакции", callback_data="admin:transactions")
    kb.button(text="📈 Статистика", callback_data="admin:stats")
    kb.adjust(2)
    return kb.as_markup()


def dispute_resolve_keyboard(dispute_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ Вернуть покупателю", callback_data=f"resolve_buyer:{dispute_id}")
    kb.button(text="✅ Продавцу (подтвердить)", callback_data=f"resolve_seller:{dispute_id}")
    kb.adjust(1)
    return kb.as_markup()


def withdrawal_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"w_approve:{withdrawal_id}")
    kb.button(text="❌ Отклонить", callback_data=f"w_reject:{withdrawal_id}")
    kb.adjust(2)
    return kb.as_markup()
