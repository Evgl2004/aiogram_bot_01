"""
Клавиатуры для процесса регистрации.
Содержат функции, возвращающие готовые объекты клавиатур.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_rules_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру внутри сообщения с кнопкой-ссылкой на документы
    и кнопкой «Согласен» для подтверждения ознакомления с правилами.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка-ссылка на страницу с документами (текст и URL)
    builder.row(InlineKeyboardButton(
        text="📄 Открыть документы",
        url="https://sagur.24vds.ru/agreement/"
    ))

    # Кнопка для подтверждения согласия
    builder.row(InlineKeyboardButton(
        text="✅ Согласен",
        callback_data="accept_rules"
    ))

    return builder.as_markup()


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру с заготовленными ответами (с одной кнопкой «Поделиться контактом»),
    которая при нажатии отправляет боту номер телефона пользователя.
    Клавиатура автоматически скрывается после нажатия (one_time_keyboard=True)
    и подстраивается под размер экрана (resize_keyboard=True).
    """
    builder = ReplyKeyboardBuilder()

    # Кнопка с запросом контакта (специальный параметр request_contact=True)
    builder.add(KeyboardButton(
        text="📱 Поделиться контактом",
        request_contact=True
    ))

    # Располагаем одну кнопку в ряду
    builder.adjust(1)

    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру внутри сообщения для выбора пола.
    Используется в состоянии waiting_for_gender.
    Кнопки отправляют callback_data: gender_male и gender_female.
    """
    builder = InlineKeyboardBuilder()
    # Добавляем две кнопки в один ряд (width=2)
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="gender_male"),
        InlineKeyboardButton(text="Женский", callback_data="gender_female"),
        width=2
    )
    return builder.as_markup()


def get_notifications_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру внутри сообщения для получения согласия на уведомления.
    Содержит ссылку на документ с условиями и две кнопки выбора.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка-ссылка на HTML-страницу с условиями получения уведомлений
    builder.row(InlineKeyboardButton(
        text="📄 Условия получения уведомлений",
        url="https://sagur.24vds.ru/notifications/"  # замените на реальный URL
    ))

    # Кнопки выбора (каждая на отдельной строке для удобства чтения)
    builder.row(InlineKeyboardButton(
        text="✅ О да, кидай всё, что есть! 🔥",
        callback_data="notify_yes"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Нет, останусь без подарков… 🙁",
        callback_data="notify_no"
    ))

    return builder.as_markup()


def get_review_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для подтверждения анкеты.
    Кнопки: "✅ Всё верно" и "✏️ Изменить".
    """

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Всё верно", callback_data="review_correct"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить", callback_data="review_edit"))
    return builder.as_markup()


def get_edit_choice_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для выбора поля, которое нужно отредактировать.
    Включает кнопки для каждого редактируемого поля и кнопку отмены.
    """
    builder = InlineKeyboardBuilder()
    fields = [
        ("👤 Имя", "edit_first_name"),
        ("👥 Фамилия", "edit_last_name"),
        ("⚥ Пол", "edit_gender"),
        ("🎂 Дата рождения", "edit_birth_date"),
        ("📧 Email", "edit_email"),
    ]
    for text, callback in fields:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="edit_cancel"))
    return builder.as_markup()
