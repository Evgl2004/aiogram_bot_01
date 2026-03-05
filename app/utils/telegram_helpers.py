from typing import Union
from aiogram.types import Message, CallbackQuery


async def send_safe_message(
    obj: Union[Message, CallbackQuery],
    text: str,
    **kwargs
):
    """
    Отправляет сообщение в зависимости от типа объекта.
    Для CallbackQuery используется message.answer, для Message – answer.
    """

    if isinstance(obj, Message):
        return await obj.answer(text, **kwargs)
    else:
        return await obj.message.answer(text, **kwargs)


async def edit_safe_message(
    obj: Union[Message, CallbackQuery],
    text: str,
    **kwargs
):
    """
    Редактирует сообщение, если объект – CallbackQuery.
    Для Message просто отправляет новое сообщение.
    """

    if isinstance(obj, CallbackQuery):
        return await obj.message.edit_text(text, **kwargs)
    else:
        # У Message нет edit_text, поэтому отправляем новое
        return await obj.answer(text, **kwargs)
