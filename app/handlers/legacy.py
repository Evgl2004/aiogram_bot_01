"""
Обработчики процесса обновления для пользователей, перенесённых из старого бота (legacy).
Последовательность шагов:
1. Приветствие и согласие с правилами.
2. Проверка наличия всех обязательных полей (имя, фамилия, пол, дата рождения, email).
   - Если поле отсутствует или невалидно, оно запрашивается у пользователя.
3. После заполнения всех полей показывается анкета для подтверждения.
4. При необходимости можно отредактировать любое поле.
5. После подтверждения анкеты запрашивается согласие на уведомления.
6. Сохраняется согласие, снимается признак is_legacy, показывается главное меню.
"""

from datetime import datetime, timezone
import re
from typing import Union, List

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.database import db
from app.keyboards.registration import (
    get_rules_keyboard,
    get_gender_keyboard,
    get_notifications_keyboard,
    get_review_keyboard,
    get_edit_choice_keyboard,
)
from app.states.legacy import LegacyUpgrade
from app.handlers.menu import show_main_menu

router = Router()


# ---------- Вспомогательные функции ----------
async def get_missing_fields(user) -> List[str]:
    """
    Определяет, какие обязательные поля у пользователя отсутствуют или невалидны.
    Возвращает список строк-идентификаторов: 'first_name', 'last_name', 'gender', 'birth_date', 'email'.
    """

    missing = []

    # Имя
    if not user.first_name_input or not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', user.first_name_input):
        missing.append('first_name')
    # Фамилия
    if not user.last_name_input or not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', user.last_name_input):
        missing.append('last_name')
    # Пол
    if user.gender not in ['male', 'female']:
        missing.append('gender')
    # Дата рождения (проверка, что это date и возраст 18-100)
    if not user.birth_date:
        missing.append('birth_date')
    else:
        today = datetime.now().date()
        age = (today.year
               - user.birth_date.year
               - ((today.month, today.day) < (user.birth_date.month, user.birth_date.day))
               )
        if age < 18 or age > 100:
            missing.append('birth_date')
    # Email
    if not user.email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', user.email):
        missing.append('email')
    return missing


async def ask_next_field(user_id: int,
                         missing_fields: List[str],
                         obj: Union[types.Message, types.CallbackQuery],
                         state: FSMContext):
    """
    Задаёт пользователю следующий вопрос из списка missing_fields.
    Если список пуст – переходит к показу анкеты (show_profile_review).
    """

    if not missing_fields:
        await show_profile_review(obj, state)
        return

    # Сохраняем оставшиеся поля в данных состояния
    await state.update_data(missing_fields=missing_fields)

    field = missing_fields[0]
    if field == 'first_name':
        text = "✍️ Введите ваше имя:"
        next_state = LegacyUpgrade.waiting_for_field
    elif field == 'last_name':
        text = "✍️ Введите вашу фамилию:"
        next_state = LegacyUpgrade.waiting_for_field
    elif field == 'gender':
        # Для пола используем inline-клавиатуру
        if isinstance(obj, types.Message):
            await obj.answer("Выберите ваш пол:", reply_markup=get_gender_keyboard())
        else:
            await obj.message.edit_text("Выберите ваш пол:", reply_markup=get_gender_keyboard())
        await state.set_state(LegacyUpgrade.waiting_for_field)
        return
    elif field == 'birth_date':
        text = "📅 Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        next_state = LegacyUpgrade.waiting_for_field
    elif field == 'email':
        text = "📧 Введите ваш email:"
        next_state = LegacyUpgrade.waiting_for_field
    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, obj, state)
        return

    if isinstance(obj, types.Message):
        await obj.answer(text)
    else:
        await obj.message.edit_text(text)
    await state.set_state(next_state)


# ---------- Начало обновления ----------
async def start_legacy_upgrade(obj: Union[types.Message, types.CallbackQuery], state: FSMContext, user):
    """
    Запускает процесс обновления для устаревшего-пользователя.
    Вызывается из start.py, когда обнаружен пользователь с is_legacy=True.
    """

    logger.info(f"Запуск обновления для устаревшего пользователя user_id={user.id} (is_legacy={user.is_legacy})")

    # Приветственное сообщение
    text = (
        "👋 Здравствуй, друг! Мы обновили бота и хотим убедиться, "
        "что твои данные актуальны, а также получить необходимые согласия. "
        "Это займёт всего пару минут."
    )
    if isinstance(obj, types.Message):
        await obj.answer(text)
    else:
        await obj.message.answer(text)

    # Показываем правила
    await obj.message.answer(
        "📜 Для начала нам необходимо получить твоё согласие на обработку персональных данных "
        "и согласие с политикой конфиденциальности.\n\n"
        "👉 Ознакомься с документами по ссылке ниже и нажми «✅ Согласен».",
        reply_markup=get_rules_keyboard()
    )
    await state.set_state(LegacyUpgrade.waiting_for_rules_consent)


# ---------- Обработчики состояний ----------
@router.callback_query(LegacyUpgrade.waiting_for_rules_consent, lambda c: c.data == "accept_rules")
async def process_rules_accept(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия кнопки «Согласен» на правилах.
    Сохраняет факт принятия правил с текущей датой, затем проверяет наличие недостающих полей.
    Если поля есть – запускает их сбор, иначе сразу показывает анкету.
    """

    user_id = callback.from_user.id
    logger.info(f"Устаревший пользователь user_id={user_id} принял правила")

    # Сохраняем согласие с датой
    await db.update_user(
        user_id,
        rules_accepted=True,
        rules_accepted_at=datetime.now(timezone.utc)
    )

    await callback.answer("Спасибо! Правила приняты.")
    await callback.message.edit_reply_markup(reply_markup=None)

    # Получаем пользователя и список недостающих полей
    user = await db.get_user(user_id)
    missing = await get_missing_fields(user)
    if missing:
        await ask_next_field(user_id, missing, callback, state)
    else:
        # Если все поля уже заполнены, сразу показываем анкету
        await show_profile_review(callback, state)


# ---------- Обработка ввода полей ----------
@router.message(LegacyUpgrade.waiting_for_field)
async def process_field_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает текстовый ввод для имени, фамилии, даты рождения или email.
    Проверяет, какое поле сейчас ожидается (первое в списке missing_fields),
    проверяет введённое значение и сохраняет его. После сохранения убирает это поле из списка
    и переходит к следующему (ask_next_field).
    """

    user_id = message.from_user.id
    data = await state.get_data()
    missing_fields = data.get('missing_fields', [])
    if not missing_fields:
        await show_profile_review(message, state)
        return

    field = missing_fields[0]
    value = message.text.strip()

    # Валидация и сохранение
    if field == 'first_name':
        if not value:
            await message.answer("❌ Имя не может быть пустым. Введите имя:")
            return
        if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
            await message.answer("⚠️ Имя может содержать только буквы, пробелы и дефисы. Попробуйте снова:")
            return
        cleaned = re.sub(r'\s+', ' ', value).strip()
        await db.update_user(user_id, first_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, message, state)

    elif field == 'last_name':
        if not value:
            await message.answer("❌ Фамилия не может быть пустой. Введите фамилию:")
            return
        if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
            await message.answer("⚠️ Фамилия может содержать только буквы, пробелы и дефисы. Попробуйте снова:")
            return
        cleaned = re.sub(r'\s+', ' ', value).strip()
        await db.update_user(user_id, last_name_input=cleaned)
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, message, state)

    elif field == 'birth_date':
        if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', value):
            await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
            return
        try:
            birth = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("⚠️ Некорректная дата. Проверьте число, месяц и год:")
            return
        today = datetime.now().date()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if birth > today:
            await message.answer("⚠️ Дата рождения не может быть в будущем.")
            return
        if age < 18:
            await message.answer("⛔ К сожалению, программа лояльности доступна только для гостей старше 18 лет.")
            return
        if age > 100:
            await message.answer("⛔ Пожалуйста, введите корректную дату рождения.")
            return
        await db.update_user(user_id, birth_date=birth)
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, message, state)

    elif field == 'email':
        if not value:
            await message.answer("❌ Email не может быть пустым. Введите email:")
            return
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
            await message.answer("⚠️ Неверный формат email. Попробуйте снова:")
            return
        await db.update_user(user_id, email=value)
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, message, state)

    else:
        # Неизвестное поле – пропускаем
        missing_fields.pop(0)
        await ask_next_field(user_id, missing_fields, message, state)


# ---------- Обработка выбора пола (inline) ----------
@router.callback_query(LegacyUpgrade.waiting_for_field, lambda c: c.data in ["gender_male", "gender_female"])
async def process_gender_input(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопки выбора пола (мужской/женский) в состоянии ожидания поля.
    Сохраняет выбранный пол, убирает поле 'gender' из списка missing_fields и переходит к следующему.
    """

    user_id = callback.from_user.id
    data = await state.get_data()
    missing_fields = data.get('missing_fields', [])
    if not missing_fields or missing_fields[0] != 'gender':
        await show_profile_review(callback, state)
        return

    gender = "male" if callback.data == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)
    missing_fields.pop(0)

    await callback.answer("✅ Пол сохранён.")
    await ask_next_field(user_id, missing_fields, callback, state)


# ---------- Показ анкеты (повторно используем из registration.py, но адаптируем) ----------
async def show_profile_review(obj: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """
    Показывает пользователю его текущие данные в виде анкеты с кнопками «Всё верно» / «Изменить».
    Используется как после сбора всех полей, так и после редактирования.
    """

    user_id = obj.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return

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

    await state.set_state(LegacyUpgrade.waiting_for_review)


# ---------- Подтверждение анкеты ----------
@router.callback_query(LegacyUpgrade.waiting_for_review, lambda c: c.data == "review_correct")
async def process_review_correct(callback: types.CallbackQuery, state: FSMContext):
    """
    Пользователь подтвердил, что данные верны. Переходим к согласию на уведомления.
    """

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "📢 Мы хотим радовать вас уникальными предложениями и акциями.\n"
        "Ознакомьтесь с условиями получения уведомлений по ссылке ниже и сделайте выбор:",
        reply_markup=get_notifications_keyboard()
    )
    await state.set_state(LegacyUpgrade.waiting_for_notifications_consent)


@router.callback_query(LegacyUpgrade.waiting_for_review, lambda c: c.data == "review_edit")
async def process_review_edit(callback: types.CallbackQuery, state: FSMContext):
    """
    Пользователь хочет что-то изменить. Показываем меню выбора поля для редактирования.
    """

    await callback.answer()
    await callback.message.edit_text(
        "🔧 Выберите, что хотите исправить:",
        reply_markup=get_edit_choice_keyboard()
    )
    await state.set_state(LegacyUpgrade.waiting_for_edit_choice)


# ---------- Редактирование (аналогично регистрации, но с сохранением дат) ----------
@router.callback_query(LegacyUpgrade.waiting_for_edit_choice)
async def process_edit_choice(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя в меню редактирования.
    Сохраняет выбранное поле в state и переводит в состояние ожидания ввода нового значения.
    Для поля 'пол' сразу показывает клавиатуру выбора.
    """

    data = callback.data
    await callback.answer()

    if data == "edit_cancel":
        await show_profile_review(callback, state)
        return

    # Сохраняем выбранное поле в state
    await state.update_data(edit_field=data)

    if data == "edit_first_name":
        msg = "✍️ Введите новое имя:"
        next_state = LegacyUpgrade.waiting_for_edit_field
    elif data == "edit_last_name":
        msg = "✍️ Введите новую фамилию:"
        next_state = LegacyUpgrade.waiting_for_edit_field
    elif data == "edit_gender":
        await callback.message.edit_text(
            "Выберите ваш пол:",
            reply_markup=get_gender_keyboard()
        )
        await state.set_state(LegacyUpgrade.waiting_for_edit_field)
        return
    elif data == "edit_birth_date":
        msg = "📅 Введите новую дату рождения в формате ДД.ММ.ГГГГ (например, 25.12.1990):"
        next_state = LegacyUpgrade.waiting_for_edit_field
    elif data == "edit_email":
        msg = "📧 Введите новый email:"
        next_state = LegacyUpgrade.waiting_for_edit_field
    else:
        await show_profile_review(callback, state)
        return

    await callback.message.edit_text(msg)
    await state.set_state(next_state)


@router.message(LegacyUpgrade.waiting_for_edit_field)
async def process_edit_field(message: types.Message, state: FSMContext):
    """
    Обрабатывает текстовый ввод нового значения для редактируемого поля.
    Проверят, сохраняет и возвращается к показу анкеты.
    """

    user_id = message.from_user.id
    data = await state.get_data()
    field = data.get('edit_field')
    value = message.text.strip()

    # Валидация и сохранение (аналогично регистрации)
    if field == 'edit_first_name':
        if not value:
            await message.answer("Имя не может быть пустым. Введите имя:")
            return
        if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
            await message.answer("Имя может содержать только буквы, пробелы и дефисы. Попробуйте снова:")
            return
        cleaned = re.sub(r'\s+', ' ', value).strip()
        await db.update_user(user_id, first_name_input=cleaned)

    elif field == 'edit_last_name':
        if not value:
            await message.answer("Фамилия не может быть пустой. Введите фамилию:")
            return
        if not re.fullmatch(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', value):
            await message.answer("Фамилия может содержать только буквы, пробелы и дефисы. Попробуйте снова:")
            return
        cleaned = re.sub(r'\s+', ' ', value).strip()
        await db.update_user(user_id, last_name_input=cleaned)

    elif field == 'edit_birth_date':
        if not re.fullmatch(r'^\d{2}\.\d{2}\.\d{4}$', value):
            await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
            return
        try:
            birth = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("Некорректная дата. Проверьте число, месяц и год:")
            return
        today = datetime.now().date()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if birth > today:
            await message.answer("Дата рождения не может быть в будущем.")
            return
        if age < 18:
            await message.answer("К сожалению, программа лояльности доступна только для гостей старше 18 лет.")
            return
        if age > 100:
            await message.answer("Пожалуйста, введите корректную дату рождения.")
            return
        await db.update_user(user_id, birth_date=birth)

    elif field == 'edit_email':
        if not value:
            await message.answer("Email не может быть пустым. Введите email:")
            return
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
            await message.answer("Неверный формат email. Попробуйте снова:")
            return
        await db.update_user(user_id, email=value)

    else:
        # Если неизвестное поле – просто показываем анкету
        await show_profile_review(message, state)
        return

    # После успешного сохранения показываем обновлённую анкету
    await show_profile_review(message, state)


@router.callback_query(LegacyUpgrade.waiting_for_edit_field, lambda c: c.data in ["gender_male", "gender_female"])
async def process_edit_gender(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор нового пола при редактировании.
    Сохраняет новое значение и возвращается к анкете.
    """

    user_id = callback.from_user.id
    gender = "male" if callback.data == "gender_male" else "female"
    await db.update_user(user_id, gender=gender)

    await callback.answer("✅ Пол сохранён.")
    await show_profile_review(callback, state)


# ---------- Согласие на уведомления ----------
@router.callback_query(LegacyUpgrade.waiting_for_notifications_consent, lambda c: c.data in ["notify_yes", "notify_no"])
async def process_notifications_consent(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя по согласию на уведомления.
    Сохраняет выбор с датой, снимает признак is_legacy, выводит финальное сообщение
    и показывает главное меню.
    """

    user_id = callback.from_user.id
    notifications_allowed = callback.data == "notify_yes"
    choice_text = "согласился на уведомления" if notifications_allowed else "отказался от уведомлений"
    logger.info(f"Legacy user {user_id} {choice_text}")

    # Сохраняем согласие и снимаем признак legacy
    await db.update_user(
        user_id,
        notifications_allowed=notifications_allowed,
        notifications_allowed_at=datetime.now(timezone.utc),
        is_legacy=False
    )

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    user = await db.get_user(user_id)
    name = user.first_name_input or "Гость"

    # Финальное сообщение
    await callback.message.answer(
        f"✅ Спасибо, {name}! Твои данные сохранены. Добро пожаловать в обновлённый бот!"
    )

    # Показываем главное меню
    await show_main_menu(
        chat_id=callback.message.chat.id,
        bot=callback.bot,
        state=state,
        user_name=name
    )
