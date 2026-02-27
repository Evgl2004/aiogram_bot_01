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

    waiting_for_rules_consent = State()             # ожидание согласия с правилами
    waiting_for_contact = State()                   # ожидание отправки контакта
    waiting_for_first_name = State()                # ожидание ввода имени
    waiting_for_last_name = State()                 # ожидание ввода фамилии
    waiting_for_gender = State()                    # выбор пола
    waiting_for_birth_date = State()                # ввод даты рождения
    waiting_for_email = State()                     # ввод email

    # Состояния для ревью и редактирования
    waiting_for_review = State()                    # показ анкеты, ожидание подтверждения
    waiting_for_edit_choice = State()               # выбор поля для редактирования
    waiting_for_edit_first_name = State()           # редактирование имени
    waiting_for_edit_last_name = State()            # редактирование фамилии
    waiting_for_edit_gender = State()               # редактирование пола
    waiting_for_edit_birth_date = State()           # редактирование даты рождения
    waiting_for_edit_email = State()                # редактирование email

    waiting_for_notifications_consent = State()     # согласие на уведомления
