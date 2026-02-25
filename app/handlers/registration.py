"""
Обработчики процесса регистрации: согласие с правилами, получение контакта и анкетирование
"""

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger

from app.database import db
from app.keyboards.registration import get_contact_keyboard, get_gender_keyboard, get_notifications_keyboard
from app.states.registration import Registration

import re
from datetime import datetime, date

router = Router()


# Обработчик нажатия на кнопку "Согласен"
@router.callback_query(Registration.waiting_for_rules_consent, lambda c: c.data == "accept_rules")
async def process_rules_accept(callback: types.CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} принял согласие с правилами")

    # Обновляем поле rules_accepted через метод update_user
    await db.update_user(user_id, rules_accepted=True)

    await callback.answer("Спасибо! Правила приняты.")
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "Отлично! Теперь, чтобы подключиться к программе лояльности, "
        "нажми кнопку «Поделиться контактом».",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(Registration.waiting_for_contact)


# Обработчик получение контакта
@router.message(Registration.waiting_for_contact, lambda message: message.contact is not None)
async def process_contact(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает полученный контакт (номер телефона).
    Сохраняет номер в БД и переходит к следующему шагу — запросу имени.
    """
    user_id = message.from_user.id
    contact = message.contact
    logger.info(f"Пользователь user_id={user_id} отправил контакт")

    # Проверяем, что контакт принадлежит именно этому пользователю
    # (хотя Telegram гарантирует, что кнопка "Поделиться контактом" отправляет контакт текущего пользователя,
    # но дополнительная проверка не помешает)
    if contact.user_id != user_id:
        logger.warning(f"⚠️ Пользователь user_id={user_id} пытался отправить чужой контакт")
        await message.answer("Пожалуйста, отправьте свой собственный контакт, используя кнопку ниже.")
        # Возвращаем клавиатуру с кнопкой контакта
        await message.answer("Нажмите кнопку «Поделиться контактом»:", reply_markup=get_contact_keyboard())
        return

    # Сохраняем номер телефона в базу данных
    phone = contact.phone_number
    # Приводим номер к единому формату (если нужно, можно добавить +)
    # Например, если номер приходит без +, добавим его
    if not phone.startswith('+'):
        phone = '+' + phone

    # Сохраняем номер через update_user
    await db.update_user(user_id, phone_number=phone)

    # Подтверждаем получение
    await message.answer(
        "Спасибо! Номер телефона сохранён.\n\n"
        "Теперь, пожалуйста, напишите ваше имя и фамилию (как вас представлять)."
    )

    # Переходим к следующему состоянию — запрос имени
    await state.set_state(Registration.waiting_for_name)


# Обработчик, если пользователь в состоянии waiting_for_contact (ожидание получения контакта от пользователя),
# но прислал что-то другое (не контакт)
@router.message(Registration.waiting_for_contact)
async def process_contact_invalid(message: types.Message) -> None:
    """
    Если пользователь в состоянии ожидания контакта, но прислал не контакт,
    напоминаем, что нужно нажать кнопку.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь user_id={user_id} отправил сообщение без контакта, ожидая контакта")
    await message.answer(
        "Пожалуйста, нажмите кнопку «Поделиться контактом» на клавиатуре, "
        "чтобы отправить свой номер телефона."
    )


# Обработчик для получения имени (состояние waiting_for_name)
@router.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод имени пользователя.
    Принимает текстовое сообщение, проверяет:
    - что оно не пустое;
    - содержит только буквы (русские/латиница), пробелы и дефисы (для двойных имён);
    - после проверки очищает от лишних пробелов.
    Сохраняет полное имя в поле full_name, извлекает первое слово для preferred_name,
    затем переводит в состояние выбора пола (waiting_for_gender).
    """

    user_id = message.from_user.id
    # Получаем текст сообщения, удаляем лишние пробелы
    name_text = message.text.strip() if message.text else ""

    logger.info(f"Пользователь user_id={user_id} вводит имя: '{name_text}'")

    # Проверяем, что имя не пустое (и не состоит из одних пробелов)
    if not name_text:
        await message.answer("Имя не может быть пустым. Пожалуйста, напишите ваше имя.")
        # Остаёмся в том же состоянии, чтобы пользователь попробовал снова
        return

    # --- Валидация допустимых символов ---
    # Разрешены: буквы (латиница и кириллица, включая 'ё'), пробелы, дефис.
    # Знак ^ означает начало строки, $ — конец, [ ... ]+ — один или более допустимых символов.
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', name_text):
        await message.answer(
            "Имя может содержать только буквы (латиница и кириллица), пробелы и дефисы.\n"
            "Пожалуйста, введите корректное имя (например, 'Анна' или 'Сергей-Петр')."
        )
        return  # остаёмся в том же состоянии

    # --- Дополнительная очистка: заменяем множественные пробелы на один ---
    # Например, "Иван   Петров" -> "Иван Петров"
    name_cleaned = re.sub(r'\s+', ' ', name_text).strip()

    # Извлекаем первое слово для обращения
    # Проверяем, что строка name_cleaned не пустая
    if name_cleaned:
        # Разбиваем строку по пробелам на отдельные слова
        words = name_cleaned.split()
        # Берём первое слово (индекс 0)
        preferred_suggested = words[0]
    else:
        # Если строка пустая, то и предпочитаемое имя будет пустым
        preferred_suggested = name_cleaned  # это пустая строка

    # Сохраняем полное имя в базу (пока без preferred_name)
    await db.update_user(user_id, full_name=name_cleaned)

    # Сохраняем предложенное обращение в FSM (не в БД, только для этого сеанса)
    await state.update_data(preferred_suggested=preferred_suggested, full_name=name_cleaned)

    # Создаём клавиатуру для подтверждения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, верно", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="✏️ Нет, изменить", callback_data="confirm_edit")]
    ])

    await message.answer(
        f"Вас можно называть *{preferred_suggested}*?\n\n"
        f"Если хотите изменить обращение, нажмите «Нет, изменить».",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    await state.set_state(Registration.waiting_for_name_confirm)


@router.callback_query(Registration.waiting_for_name_confirm, lambda c: c.data == "confirm_yes")
async def process_name_confirm_yes(callback: types.CallbackQuery, state: FSMContext) -> None:
    """
    Пользователь подтвердил предложенное обращение.
    Сохраняем preferred_name в БД и переходим к выбору пола.
    """
    user_id = callback.from_user.id
    data = await state.get_data()
    preferred_suggested = data.get("preferred_suggested", "")

    # Сохраняем предпочитаемое обращение
    await db.update_user(user_id, preferred_name=preferred_suggested)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)  # убираем кнопки

    # Подтверждаем получение и показываем клавиатуру для выбора пола
    await callback.message.answer(
        f"Приятно познакомиться, {preferred_suggested}!\n\n"
        "Теперь укажите ваш пол:",
        reply_markup=get_gender_keyboard()
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_gender)


@router.callback_query(Registration.waiting_for_name_confirm, lambda c: c.data == "confirm_edit")
async def process_name_confirm_edit(callback: types.CallbackQuery, state: FSMContext) -> None:
    """
    Пользователь хочет изменить обращение.
    Запрашиваем новый вариант.
    """
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "Пожалуйста, напишите, как к вам обращаться (например, только имя)."
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_name_edit)


@router.message(Registration.waiting_for_name_edit)
async def process_name_edit(message: types.Message, state: FSMContext) -> None:
    """
    Принимает новый вариант обращения, проверяет и сохраняет.
    """
    user_id = message.from_user.id
    new_preferred = message.text.strip() if message.text else ""

    if not new_preferred:
        await message.answer("Обращение не может быть пустым. Пожалуйста, введите текст.")
        return

    # Можно наложить те же ограничения (буквы, пробелы, дефисы)
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', new_preferred):
        await message.answer(
            "Обращение может содержать только буквы, пробелы и дефисы.\n"
            "Пожалуйста, введите корректный вариант."
        )
        return

    # Очищаем
    new_preferred_cleaned = re.sub(r'\s+', ' ', new_preferred).strip()

    # Сохраняем в БД
    await db.update_user(user_id, preferred_name=new_preferred_cleaned)

    # Получаем полное имя из данных (на всякий случай)
    data = await state.get_data()
    full_name = data.get("full_name", "")

    # Подтверждаем получение и показываем клавиатуру для выбора пола
    await message.answer(
        f"Приятно познакомиться, {new_preferred_cleaned}!\n\n"
        "Теперь укажите ваш пол:",
        reply_markup=get_gender_keyboard()
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_gender)


# Обработчик выбора пола (состояние waiting_for_gender)
@router.callback_query(Registration.waiting_for_gender, lambda c: c.data in ["gender_male", "gender_female"])
async def process_gender(callback: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает нажатие на кнопки выбора пола.
    Сохраняет выбранное значение в поле gender пользователя (male/female)
    и переводит в состояние ввода даты рождения (waiting_for_birth_date).
    """

    user_id = callback.from_user.id
    # Определяем пол по данным callback
    if callback.data == "gender_male":
        gender_value = "male"
        gender_text = "мужской"
    else:  # gender_female
        gender_value = "female"
        gender_text = "женский"

    logger.info(f"Пользователь user_id={user_id} выбрал пол: {gender_text}")

    # Сохраняем пол в базу данных
    await db.update_user(user_id, gender=gender_value)

    # Отвечаем на callback, чтобы убрать "часики" на кнопке
    await callback.answer()

    # Убираем клавиатуру из сообщения (чтобы кнопки не висели)
    await callback.message.edit_reply_markup(reply_markup=None)

    # Отправляем сообщение с запросом даты рождения
    await callback.message.answer(
        "Спасибо! Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_birth_date)


@router.message(Registration.waiting_for_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод даты рождения.
    Проверяет формат ДД.ММ.ГГГГ, корректность даты (существует ли она),
    а также минимальный и максимальный возраст (18–100 лет).
    При успехе сохраняет дату в поле birth_date и переходит к запросу email.
    """

    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    logger.info(f"Пользователь user_id={user_id} вводит дату рождения: '{text}'")

    # Проверка формата регулярным выражением (не обязательна, но помогает отсеять совсем неподходящее)
    if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', text):
        await message.answer(
            "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
        )
        return

    # Пытаемся распарсить дату
    try:
        birth = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        # Если дата не существует (например, 31.02.2020)
        await message.answer(
            "Введена некорректная дата. Пожалуйста, проверьте правильность числа, месяца и года."
        )
        return

    # Проверка на будущую дату и возрастные ограничения
    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

    if birth > today:
        await message.answer("Дата рождения не может быть в будущем. Пожалуйста, введите корректную дату.")
        return

    if age < 18:
        await message.answer("К сожалению, программа лояльности доступна только для гостей старше 18 лет.")
        return

    if age > 100:
        await message.answer("Пожалуйста, введите корректную дату рождения.")
        return

    # Сохраняем дату в базу данных
    await db.update_user(user_id, birth_date=birth)

    # Подтверждаем и переходим к запросу email
    await message.answer(
        "Спасибо! Дата рождения сохранена.\n\n"
        "Теперь, пожалуйста, укажите ваш адрес электронной почты."
    )

    # Переводим в состояние ожидания email
    await state.set_state(Registration.waiting_for_email)


@router.message(Registration.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод email.
    Проверяет корректность формата (простая проверка: наличие @ и точки после @).
    Сохраняет email в поле email пользователя, устанавливает is_registered = True
    и завершает регистрацию, показывая главное меню.
    """

    user_id = message.from_user.id
    email = message.text.strip() if message.text else ""

    logger.info(f"Пользователь user_id={user_id} вводит email: '{email}'")

    # Проверка на пустой ввод
    if not email:
        await message.answer("Email не может быть пустым. Пожалуйста, введите ваш email.")
        return

    # Простая валидация email: наличие @ и точки после @
    # Более строгую проверку можно сделать с помощью библиотеки email-validator, но для простоты достаточно
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        await message.answer(
            "Пожалуйста, введите корректный email-адрес, например: example@domain.com"
        )
        return

    # Сохраняем email в базу данных
    await db.update_user(user_id, email=email)

    # Переходим к запросу согласия на уведомления
    await message.answer(
        "Мы хотим радовать вас уникальными предложениями и акциями.\n"
        "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
        reply_markup=get_notifications_keyboard()
    )

    # Переводим в состояние ожидания согласия на уведомления
    await state.set_state(Registration.waiting_for_notifications_consent)


@router.callback_query(Registration.waiting_for_notifications_consent, lambda c: c.data in ["notify_yes", "notify_no"])
async def process_notifications_consent(callback: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает выбор пользователя по согласию на уведомления.
    Сохраняет значение notifications_allowed (True/False) в БД,
    устанавливает is_registered = True и завершает регистрацию.
    """

    user_id = callback.from_user.id

    # Определяем значение в зависимости от нажатой кнопки
    if callback.data == "notify_yes":
        notifications_allowed = True
        choice_text = "согласился на уведомления"
    else:  # notify_no
        notifications_allowed = False
        choice_text = "отказался от уведомлений"

    logger.info(f"Пользователь user_id={user_id} {choice_text}")

    # Обновляем запись: согласие на уведомления и флаг завершения регистрации
    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        is_registered=True
    )

    # Отвечаем на callback (убираем "часики" на кнопке)
    await callback.answer()

    # Убираем клавиатуру из сообщения
    await callback.message.edit_reply_markup(reply_markup=None)

    # Получаем обновлённые данные пользователя (для приветствия)
    user = await db.get_user(user_id)
    preferred_name = user.preferred_name or "Гость"

    # Отправляем финальное сообщение с главным меню (пока заглушка)
    await callback.answer(
        f"🎉 Поздравляем, {preferred_name}! Вы успешно зарегистрированы в программе лояльности.\n\n"
        f"Главное меню:\n"
        f"• Мой баланс\n"
        f"• Специальные предложения\n"
        f"• Сайты заведений\n"
    )

    # Очищаем состояние FSM, регистрация завершена
    await state.clear()
