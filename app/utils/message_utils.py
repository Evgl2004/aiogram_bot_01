from aiogram.types import CallbackQuery


async def safe_edit_message(callback: CallbackQuery, text: str, **kwargs):
    """
    Безопасное редактирование сообщения.
    Если исходное сообщение не найдено (удалено), отправляет новое.
    """

    try:
        await callback.message.edit_text(text, **kwargs)
    except Exception:
        # При ошибке отправляем новое сообщение
        await callback.message.answer(text, **kwargs)
