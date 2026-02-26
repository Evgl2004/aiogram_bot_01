"""
Обработчики процесса регистрации: согласие с правилами, получение контакта и анкетирование
"""

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from loguru import logger

from app.database import db
from app.keyboards.registration import (
    get_contact_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_review_keyboard,
    get_edit_choice_keyboard
)
from app.states.registration import Registration
from app.handlers.menu import show_main_menu

import re
from datetime import datetime, date
from typing import Union

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
        "✅ Отлично! Правила приняты. Теперь, чтобы подключиться к программе лояльности, "
        "нажми кнопку «📱 Поделиться контактом».",
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

        await message.answer(
            "⚠️ Пожалуйста, отправьте свой собственный контакт, используя кнопку ниже."
        )

        # Возвращаем клавиатуру с кнопкой контакта
        await message.answer(
            "📱 Нажмите кнопку «Поделиться контактом»:",
            reply_markup=get_contact_keyboard()
        )
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
        "✅ Спасибо! Номер телефона сохранён.\n\n"
        "✍️ Теперь, пожалуйста, напишите ваше имя.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Переходим к следующему состоянию — запрос имени
    await state.set_state(Registration.waiting_for_first_name)


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
        "📱 Пожалуйста, нажмите кнопку «Поделиться контактом» на клавиатуре, "
        "чтобы отправить свой номер телефона."
    )


# Обработчик для получения имени
@router.message(Registration.waiting_for_first_name)
async def process_first_name(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод имени пользователя.
    Принимает текстовое сообщение, проверяет:
    - что оно не пустое;
    - содержит только буквы (русские/латиница), пробелы и дефисы (для двойных имён);
    - после проверки очищает от лишних пробелов.
    Сохраняет имя, затем переводит в состояние ввода фамилии.
    """

    user_id = message.from_user.id
    # Получаем текст сообщения, удаляем лишние пробелы
    first_name_text = message.text.strip() if message.text else ""

    logger.info(f"Пользователь user_id={user_id} вводит имя: '{first_name_text}'")

    # Проверяем, что имя не пустое (и не состоит из одних пробелов)
    if not first_name_text:
        await message.answer(
            "❌ Имя не может быть пустым. Пожалуйста, напишите ваше имя."
        )
        # Остаёмся в том же состоянии, чтобы пользователь попробовал снова
        return

    # --- Валидация допустимых символов ---
    # Разрешены: буквы (латиница и кириллица, включая 'ё'), пробелы, дефис.
    # Знак ^ означает начало строки, $ — конец, [ ... ]+ — один или более допустимых символов.
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', first_name_text):
        await message.answer(
            "⚠️ Имя может содержать только буквы (латиница и кириллица), пробелы и дефисы.\n"
            "✍️ Пожалуйста, введите корректное имя (например, 'Анна' или 'Сергей-Петр')."
        )
        return  # остаёмся в том же состоянии

    # --- Дополнительная очистка: заменяем множественные пробелы на один ---
    # Например, "Иван   Петров" -> "Иван Петров"
    first_name_cleaned = re.sub(r'\s+', ' ', first_name_text).strip()

    # Сохраняем полное имя в базу (пока без preferred_name)
    await db.update_user(user_id, first_name_input=first_name_cleaned)

    await message.answer(
        "✅ Спасибо! Теперь напишите вашу фамилию."
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_last_name)


# Обработчик для получения фамилии
@router.message(Registration.waiting_for_last_name)
async def process_last_name(message: types.Message, state: FSMContext) -> None:
    """
    Обрабатывает ввод фамилии пользователя.
    Принимает текстовое сообщение, проверяет:
    - что оно не пустое;
    - содержит только буквы (русские/латиница), пробелы и дефисы (для двойных имён);
    - после проверки очищает от лишних пробелов.
    Сохраняет имя, затем переводит в состояние ввода пола.
    """

    user_id = message.from_user.id
    # Получаем текст сообщения, удаляем лишние пробелы
    last_name_text = message.text.strip() if message.text else ""

    logger.info(f"Пользователь user_id={user_id} вводит фамилию: '{last_name_text}'")

    # Проверяем, что имя не пустое (и не состоит из одних пробелов)
    if not last_name_text:
        await message.answer(
            "❌ Фамилия не может быть пустой. Пожалуйста, напишите вашу фамилию."
        )
        # Остаёмся в том же состоянии, чтобы пользователь попробовал снова
        return

    # --- Валидация допустимых символов ---
    # Разрешены: буквы (латиница и кириллица, включая 'ё'), пробелы, дефис.
    # Знак ^ означает начало строки, $ — конец, [ ... ]+ — один или более допустимых символов.
    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', last_name_text):
        await message.answer(
            "⚠️ Фамилия может содержать только буквы (латиница и кириллица), пробелы и дефисы.\n"
            "✍️ Пожалуйста, введите корректную фамилию (например, 'Петров' или 'Петров-Сидоров')."
        )
        return  # остаёмся в том же состоянии

    # --- Дополнительная очистка: заменяем множественные пробелы на один ---
    last_name_cleaned = re.sub(r'\s+', ' ', last_name_text).strip()

    # Сохраняем полное имя в базу (пока без preferred_name)
    await db.update_user(user_id, last_name_input=last_name_cleaned)

    await message.answer(
        "👍 Отлично! Теперь укажите ваш пол:",
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
        "✅ Спасибо! Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
    )

    # Переводим пользователя в следующее состояние
    await state.set_state(Registration.waiting_for_birth_date)


# Обработчик ввода дня рождения (состояние waiting_for_gender)
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
            "❌ Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 25.12.1990)."
        )
        return

    # Пытаемся разобрать дату
    try:
        birth = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        # Если дата не существует (например, 31.02.2020)
        await message.answer(
            "⚠️ Введена некорректная дата. Пожалуйста, проверьте правильность числа, месяца и года."
        )
        return

    # Проверка на будущую дату и возрастные ограничения
    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

    if birth > today:
        await message.answer(
            "⚠️ Дата рождения не может быть в будущем. Пожалуйста, введите корректную дату."
        )
        return

    if age < 18:
        await message.answer(
            "⛔ К сожалению, программа лояльности доступна только для гостей старше 18 лет."
        )
        return

    if age > 100:
        await message.answer(
            "⛔ Пожалуйста, введите корректную дату рождения."
        )
        return

    # Сохраняем дату в базу данных
    await db.update_user(user_id, birth_date=birth)

    # Подтверждаем и переходим к запросу email
    await message.answer(
        "✅ Спасибо! Дата рождения сохранена.\n\n"
        "📧 Теперь, пожалуйста, укажите ваш адрес электронной почты."
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
        await message.answer(
            "❌ Email не может быть пустым. Пожалуйста, введите ваш email."
        )
        return

    # Простая валидация email: наличие @ и точки после @
    # Более строгую проверку можно сделать с помощью библиотеки email-validator, но для простоты достаточно
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        await message.answer(
            "⚠️ Пожалуйста, введите корректный email-адрес, например: example@domain.com"
        )
        return

    # Сохраняем email в базу данных
    await db.update_user(user_id, email=email)

    # Вместо перехода к уведомлениям показываем анкету
    await show_profile_review(message, state)


# --- Обработчики ревью анкеты ---
@router.callback_query(Registration.waiting_for_review, lambda c: c.data == "review_correct")
async def process_review_correct(callback: types.CallbackQuery, state: FSMContext):
    """
    Пользователь подтвердил анкету -> переходим к согласию на уведомления.
    """

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
        "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
        reply_markup=get_notifications_keyboard()
    )
    await state.set_state(Registration.waiting_for_notifications_consent)


@router.callback_query(Registration.waiting_for_review, lambda c: c.data == "review_edit")
async def process_review_edit(callback: types.CallbackQuery, state: FSMContext):
    """
    Пользователь хочет что-то изменить -> показываем выбор поля.
    """

    await callback.answer()
    await callback.message.edit_text(
        "🔧 Выберите, что хотите исправить:",
        reply_markup=get_edit_choice_keyboard()
    )
    await state.set_state(Registration.waiting_for_edit_choice)


# --- Обработчик выбора поля для редактирования ---
@router.callback_query(Registration.waiting_for_edit_choice)
async def process_edit_choice(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    await callback.answer()

    if data == "edit_cancel":
        await show_profile_review(callback, state)
        return

    if data == "edit_first_name":
        new_state = Registration.waiting_for_edit_first_name
        msg = "✍️ Введите новое имя:"
    elif data == "edit_last_name":
        new_state = Registration.waiting_for_edit_last_name
        msg = "✍️ Введите новую фамилию:"
    elif data == "edit_gender":
        new_state = Registration.waiting_for_edit_gender
        await callback.message.edit_text(
            "Выберите ваш пол:",
            reply_markup=get_gender_keyboard()
        )
        await state.set_state(new_state)
        return
    elif data == "edit_birth_date":
        new_state = Registration.waiting_for_edit_birth_date
        msg = "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
    elif data == "edit_email":
        new_state = Registration.waiting_for_edit_email
        msg = "📧 Введите новый email:"
    else:
        await show_profile_review(callback, state)
        return

    await callback.message.edit_text(msg)
    await state.set_state(new_state)


# --- Обработчики редактирования каждого поля ---
@router.message(Registration.waiting_for_edit_first_name)
async def process_edit_first_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    first_name_text = message.text.strip() if message.text else ""

    if not first_name_text:
        await message.answer("Имя не может быть пустым. Введите имя:")
        return

    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', first_name_text):
        await message.answer(
            "Имя может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
        )
        return

    first_name_cleaned = re.sub(r'\s+', ' ', first_name_text).strip()
    await db.update_user(user_id, first_name_input=first_name_cleaned)

    await show_profile_review(message, state)


@router.message(Registration.waiting_for_edit_last_name)
async def process_edit_last_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    last_name_text = message.text.strip() if message.text else ""

    if not last_name_text:
        await message.answer("Фамилия не может быть пустой. Введите фамилию:")
        return

    if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', last_name_text):
        await message.answer(
            "Фамилия может содержать только буквы, пробелы и дефисы. Попробуйте снова:"
        )
        return

    last_name_cleaned = re.sub(r'\s+', ' ', last_name_text).strip()
    await db.update_user(user_id, last_name_input=last_name_cleaned)

    await show_profile_review(message, state)


@router.callback_query(Registration.waiting_for_edit_gender, lambda c: c.data in ["gender_male", "gender_female"])
async def process_edit_gender(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    gender = "male" if callback.data == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)

    await callback.answer("✅ Пол сохранён.")
    await show_profile_review(callback, state)


@router.message(Registration.waiting_for_edit_birth_date)
async def process_edit_birth_date(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()

    if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', text):
        await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return

    try:
        birth = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Некорректная дата. Проверьте число, месяц и год:")
        return

    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if birth > today:
        await message.answer("Дата рождения не может быть в будущем. Введите снова:")
        return
    if age < 18:
        await message.answer("К сожалению, программа лояльности доступна только для гостей старше 18 лет.")
        return
    if age > 100:
        await message.answer("Пожалуйста, введите корректную дату рождения.")
        return

    await db.update_user(user_id, birth_date=birth)
    await show_profile_review(message, state)


@router.message(Registration.waiting_for_edit_email)
async def process_edit_email(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    email = message.text.strip()

    if not email:
        await message.answer("Email не может быть пустым. Введите email:")
        return

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        await message.answer("Неверный формат email. Попробуйте снова:")
        return

    await db.update_user(user_id, email=email)
    await show_profile_review(message, state)


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
    name = user.first_name_input or "Гость"

    # Вызываем главное меню
    await show_main_menu(
        chat_id=callback.message.chat.id,
        bot=callback.bot,
        state=state,
        user_name=name
    )


# Функция показа анкеты
async def show_profile_review(obj: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """
    Показывает пользователю его анкету и предлагает подтвердить или изменить.
    """

    user_id = obj.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

    # Формируем текст анкеты
    gender_text = "мужской" if user.gender == "male" else "женский" if user.gender == "female" else "не указан"
    birth_text = user.birth_date.strftime('%d.%m.%Y') if user.birth_date else "не указана"
    text = (
        "📋 *Проверьте введённые данные:*\n\n"
        f"👤 *Имя:* {user.first_name_input or 'не указано'}\n"
        f"👥 *Фамилия:* {user.last_name_input or 'не указано'}\n"
        f"📞 *Телефон:* {user.phone_number or 'не указан'}\n"
        f"⚥ *Пол:* {gender_text}\n"
        f"🎂 *Дата рождения:* {birth_text}\n"
        f"📧 *Email:* {user.email or 'не указан'}\n\n"
        "Всё верно?"
    )

    if isinstance(obj, types.Message):
        await obj.answer(text, reply_markup=get_review_keyboard(), parse_mode="Markdown")
    else:
        await obj.message.edit_text(text, reply_markup=get_review_keyboard(), parse_mode="Markdown")
        await obj.answer()

    await state.set_state(Registration.waiting_for_review)
