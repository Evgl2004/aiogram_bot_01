"""
Состояния (FSM) для процесса регистрации пользователя.
Каждый класс наследуется от StatesGroup, а каждый атрибут — это отдельное состояние (State).
"""

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    """
    Группа состояний для регистрации нового пользователя.
    Порядок состояний соответствует последовательности шагов.
    """

    # Ожидание нажатия на кнопку «Согласен» после ознакомления с правилами
    waiting_for_rules_consent = State()

    # Ожидание отправки контакта (номера телефона) через специальную кнопку
    waiting_for_contact = State()

    # Ожидание ввода имени и фамилии (текстовое сообщение)
    waiting_for_name = State()

    # Ожидание выбора "Да/Нет" или нового текста
    waiting_for_name_confirm = State()

    # Ожидание ввода нового обращения
    waiting_for_name_edit = State()

    # Ожидание выбора пола (через кнопки внутри сообщения)
    waiting_for_gender = State()

    # Ожидание ввода даты рождения (в формате ДД.ММ.ГГГГ)
    waiting_for_birth_date = State()

    # Ожидание ввода email
    waiting_for_email = State()

    # Состояние для отдельного согласия на уведомления
    waiting_for_notifications_consent = State()
