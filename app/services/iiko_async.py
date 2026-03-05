"""
Асинхронный клиент для работы с iiko Cloud API v1.
Использует aiohttp и asyncio.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from loguru import logger


class AsyncIikoApi:
    """Асинхронный клиент для взаимодействия с iiko API."""

    def __init__(self, api_key: str = None, organization_id: str = None):
        self.api_key = api_key or settings.IIKO_API_KEY
        self.organization_id = organization_id or settings.DEFAULT_ORG_ID
        self.base_url = "https://api-ru.iiko.services/api/1"
        self.token: Optional[str] = None
        self.token_expire_time: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()  # блокировка для доступа к токену

    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает сессию (создаёт при первом вызове)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Закрывает сессию. Должен быть вызван при остановке бота."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _is_token_valid(self) -> bool:
        """Проверяет валидность текущего токена (без блокировки, вызывать внутри _lock)."""
        if not self.token or not self.token_expire_time:
            return False
        return datetime.now() < self.token_expire_time

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _get_token(self) -> Optional[str]:
        """
        Получает токен доступа к API. Токен действителен 15 минут.
        При неудаче делает до 3 повторных попыток.
        """
        async with self._lock:
            # Проверяем, действителен ли текущий токен
            if await self._is_token_valid():
                logger.debug("Используем существующий токен iiko")
                return self.token

            logger.info("Запрашиваем новый токен iiko")
            session = await self._get_session()
            headers = {"Content-Type": "application/json"}
            data = {"apiLogin": self.api_key}

            try:
                async with session.post(
                    f"{self.base_url}/access_token",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    resp.raise_for_status()
                    token_data = await resp.json()
                    self.token = token_data.get('token')
                    # Токен действителен 15 минут, ставим запас в 1 минуту
                    self.token_expire_time = datetime.now() + timedelta(minutes=14)
                    logger.info("Новый токен iiko получен")
                    return self.token
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка получения токена iiko: {e}")
                raise  # для повторных попыток tenacity

    def _format_phone(self, phone: str) -> str:
        """Приводит номер телефона к формату +7XXXXXXXXXX."""

        # Создаём пустую строку, куда будем добавлять цифры
        digits = ""

        # Перебираем каждый символ в исходной строке
        for character in phone:
            # Если символ – цифра, добавляем его к результату
            if character.isdigit():
                digits += character

        if digits.startswith('7'):
            return f"+{digits}"
        elif digits.startswith('8'):
            return f"+7{digits[1:]}"
        elif len(digits) == 10:
            return f"+7{digits}"
        else:
            return f"+{digits}"

    async def get_customer_info(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о клиенте по номеру телефона.
        """
        token = await self._get_token()
        if not token:
            logger.error("Не удалось получить токен для запроса информации о клиенте")
            return None

        formatted_phone = self._format_phone(phone)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "phone": formatted_phone,
            "type": "phone",
            "organizationId": self.organization_id
        }

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/loyalty/iiko/customer/info",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    return self._extract_customer_info(response_data)
                elif resp.status in (400, 404):
                    text = await resp.text()
                    logger.info(f"Клиент с номером {phone} не найден. Ответ API: {text}")
                    return None
                else:
                    text = await resp.text()
                    logger.error(f"Ошибка при запросе информации о клиенте: {resp.status} - {text}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при запросе информации о клиенте: {e}")
            return None

    async def register_customer(
            self,
            phone: str,
            name: str = "",
            surname: str = "",
            middle_name: str = "",
            birth_date: Optional[str] = None,
            sex: Optional[int] = None,
            email: str = "",
            consent_status: int = 0,
            should_receive_promo: bool = True,
            should_receive_loyalty: bool = True,
            customer_id: Optional[str] = None  # новый параметр
    ) -> Tuple[Optional[str], str]:
        """
        Регистрирует нового клиента или обновляет существующего.
        Если customer_id передан, обновляет существующего клиента.
        """

        token = await self._get_token()
        if not token:
            return None, "❌ Не удалось получить токен авторизации"

        formatted_phone = self._format_phone(phone)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "phone": formatted_phone,
            "name": name,
            "shouldReceivePromoActionsInfo": should_receive_promo,
            "shouldReceiveLoyaltyInfo": should_receive_loyalty,
            "consentStatus": consent_status,
            "organizationId": self.organization_id
        }
        # Добавляем поля только если они предоставлены
        if surname:
            data["surName"] = surname
        if middle_name:
            data["middleName"] = middle_name
        if birth_date:
            data["birthday"] = birth_date
        if sex is not None:
            data["sex"] = sex
        if email:
            data["email"] = email
        if customer_id:
            data["id"] = customer_id  # добавляем id для обновления

        session = await self._get_session()
        try:
            async with session.post(
                    f"{self.base_url}/loyalty/iiko/customer/create_or_update",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    customer_id = response_data.get('id')
                    logger.info(f"Клиент {formatted_phone} зарегистрирован/обновлён, id={customer_id}")
                    return customer_id, "✅ Клиент успешно зарегистрирован"
                else:
                    error_text = await resp.text()
                    logger.error(f"Ошибка регистрации клиента: {resp.status} - {error_text}")
                    return None, f"❌ Ошибка регистрации: {error_text}"
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при регистрации клиента: {e}")
            return None, "❌ Ошибка сети при регистрации"

    async def add_card(self, customer_id: str, card_number: str) -> Tuple[bool, str]:
        """
        Добавляет карту клиенту.
        """
        token = await self._get_token()
        if not token:
            return False, "❌ Не удалось получить токен авторизации"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "customerId": customer_id,
            "cardNumber": card_number,
            "cardTrack": card_number,
            "organizationId": self.organization_id
        }

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/loyalty/iiko/customer/card/add",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Карта {card_number} добавлена клиенту {customer_id}")
                    return True, "✅ Карта успешно добавлена"
                else:
                    error_text = await resp.text()
                    logger.error(f"Ошибка добавления карты: {resp.status} - {error_text}")
                    return False, f"❌ Ошибка добавления карты: {error_text}"
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при добавлении карты: {e}")
            return False, "❌ Ошибка сети при добавлении карты"

    async def get_loyalty_programs(self) -> List[Dict[str, Any]]:
        """
        Получает список программ лояльности.
        """
        token = await self._get_token()
        if not token:
            return []

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "withoutMarketingCampaigns": True,
            "organizationId": self.organization_id
        }

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/loyalty/iiko/program",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    programs_data = await resp.json()
                    programs = (programs_data.get('programs') or
                                programs_data.get('Programs') or
                                [])
                    logger.info(f"Получено {len(programs)} программ лояльности")
                    return programs
                else:
                    logger.error(f"Ошибка получения программ лояльности: {resp.status}")
                    return []
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при получении программ: {e}")
            return []

    async def add_customer_to_program(self, customer_id: str, program_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Подключает клиента к программе лояльности.
        Если program_id не указан, выбирается первая доступная программа.
        """
        if not program_id:
            programs = await self.get_loyalty_programs()
            if not programs:
                return False, "❌ Не удалось получить список программ лояльности"
            # Ищем программу с названием "программа лояльности" или берём первую
            target = next(
                (p for p in programs if p.get("name", "").strip().lower() == "программа лояльности"),
                None
            )
            if not target:
                target = programs[0]
            program_id = target.get("id")
            if not program_id:
                return False, "❌ Не удалось определить ID программы"

        token = await self._get_token()
        if not token:
            return False, "❌ Не удалось получить токен авторизации"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "customerId": customer_id,
            "organizationId": self.organization_id,
            "programId": program_id
        }

        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/loyalty/iiko/customer/program/add",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Клиент {customer_id} подключён к программе {program_id}")
                    return True, "✅ Программа лояльности подключена"
                else:
                    error_text = await resp.text()
                    logger.error(f"Ошибка подключения к программе: {resp.status} - {error_text}")
                    return False, f"❌ Ошибка подключения к программе: {error_text}"
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при подключении к программе: {e}")
            return False, "❌ Ошибка сети при подключении к программе"

    def _extract_customer_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлекает из ответа API информацию о клиенте в удобном формате.
        """
        result = {
            'customer_id': data.get('id'),
            'name': f"{data.get('surname', '')} {data.get('name', '')}".strip(),
            'phone': data.get('phone', ''),
            'balance': 0,
            'program_name': '',
            'cards': [],
        }

        wallets = data.get('walletBalances') or []
        if wallets:
            target = next(
                (w for w in wallets if (w.get('name') or w.get('programName') or w.get('walletName') or '')
                 .strip().lower() == 'программа лояльности'),
                None
            )
            if not target:
                target = next((w for w in wallets if w.get('type') == 1), None)
            if not target and wallets:
                target = wallets[0]

            if target:
                result['balance'] = target.get('balance', 0)
                result['program_name'] = (
                    target.get('name') or target.get('programName') or target.get('walletName') or ''
                ).strip()

        cards_data = data.get('cards') or []
        for card in cards_data:
            card_info = {
                'number': card.get('number', ''),
                'valid_to': card.get('validToDate', '')
            }
            if card_info['valid_to']:
                try:
                    date_obj = datetime.strptime(card_info['valid_to'], '%Y-%m-%d %H:%M:%S.%f')
                    card_info['valid_to'] = date_obj.strftime('%d.%m.%Y')
                except:
                    pass
            result['cards'].append(card_info)

        return result
