"""Общие функции валидации данных пользователей"""

import re
from datetime import datetime, date
from typing import Tuple
from aiogram.types import Message


async def validate_first_name(value: str) -> Tuple[bool, str]:
    """
    Валидация имени пользователя.
    
    Args:
        value (str): Введенное значение
        
    Returns:
        tuple[bool, str]: (успех, сообщение об ошибке)
    """
    if not value:
        return False, "❌ Имя не может быть пустым. Введите имя:"
    
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
        return False, "⚠️ Имя может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
    
    return True, ""


async def validate_last_name(value: str) -> Tuple[bool, str]:
    """
    Валидация фамилии пользователя.
    
    Args:
        value (str): Введенное значение
        
    Returns:
        tuple[bool, str]: (успех, сообщение об ошибке)
    """
    if not value:
        return False, "❌ Фамилия не может быть пустой. Введите фамилию:"
    
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
        return False, "⚠️ Фамилия может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
    
    return True, ""


async def validate_birth_date(value: str) -> Tuple[bool, str]:
    """
    Валидация даты рождения пользователя.
    
    Args:
        value (str): Введенное значение в формате ДД.ММ.ГГГГ
        
    Returns:
        tuple[bool, str]: (успех, сообщение об ошибке)
    """
    if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', value):
        return False, "❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:"
    
    try:
        birth = datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return False, "⚠️ Некорректная дата. Проверьте число, месяц и год:"
    
    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    
    if birth > today:
        return False, "⚠️ Дата рождения не может быть в будущем."
    
    if age < 18:
        return False, "⛔ К сожалению, программа лояльности доступна только для гостей старше 18 лет."
    
    if age > 100:
        return False, "⛔ Пожалуйста, введите корректную дату рождения."
    
    return True, ""


async def validate_email(value: str) -> Tuple[bool, str]:
    """
    Валидация email пользователя.
    
    Args:
        value (str): Введенное значение
        
    Returns:
        tuple[bool, str]: (успех, сообщение об ошибке)
    """
    if not value:
        return False, "❌ Email не может быть пустым. Введите email:"
    
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
        return False, "⚠️ Неверный формат email. Попробуйте снова:"
    
    return True, ""


async def clean_name(value: str) -> str:
    """
    Очистка имени/фамилии от лишних пробелов.
    
    Args:
        value (str): Введенное значение
        
    Returns:
        str: Очищенное значение
    """
    return re.sub(r'\s+', ' ', value).strip()


async def confirm_text(message: Message, error_text: str = "❌ Пожалуйста, отправьте текстовое сообщение.") -> bool:
    """
    Проверяет, содержит ли сообщение текст.
    Если нет – отправляет пользователю сообщение об ошибке и возвращает False.
    """
    if not message.text:
        await message.answer(error_text)
        return False
    return True

