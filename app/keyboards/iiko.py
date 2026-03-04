from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def retry_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для повторной попытки регистрации в iiko.
    Используется при временных сбоях сети или ошибках API.
    """

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 Повторить попытку",
        callback_data="retry_iiko_registration"
    ))
    return builder.as_markup()
