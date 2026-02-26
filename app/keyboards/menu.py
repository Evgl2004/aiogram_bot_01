"""
Клавиатуры для главного меню и подменю.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню:
    - Мой баланс
    - Виртуальная карта
    - Отдел заботы
    - Вакансии
    """

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Мой баланс", callback_data="balance"))
    builder.row(InlineKeyboardButton(text="🪪 Виртуальная карта", callback_data="virtual_card"))
    builder.row(InlineKeyboardButton(text="🆘 Отдел заботы", callback_data="support"))
    builder.row(InlineKeyboardButton(text="💼 Вакансии", callback_data="vacancies"))
    return builder.as_markup()


def get_support_submenu_keyboard() -> InlineKeyboardMarkup:
    """
    Подменю отдела заботы:
    - Оставить отзыв
    - Мне только спросить
    - Контакты
    - 🔙 Назад в меню
    """

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="support_feedback"))
    builder.row(InlineKeyboardButton(text="❓ Мне только спросить", callback_data="support_question"))
    builder.row(InlineKeyboardButton(text="📧 Контакты", callback_data="support_contacts"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка для возврата в главное меню (используется в разделах без подменю).
    """
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()


def get_back_to_support_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка для возврата в подменю отдела заботы.
    """

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад в отдел заботы", callback_data="back_to_support"))
    return builder.as_markup()
