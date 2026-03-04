"""
Сервис для работы с тикетами системы модерации
"""

from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, func, text

from app.database.models import Ticket, TicketMessage
from app.database import db


class TicketService:
    """Сервис для работы с тикетами"""
    
    async def create_ticket(
        self,
        user_id: int,
        message: str,
        user_username: Optional[str] = None,
        user_first_name: Optional[str] = None
    ) -> Ticket:
        """Создание нового тикета"""
        async with db.session_maker() as session:
            ticket = Ticket(
                user_id=user_id,
                message=message,
                user_username=user_username,
                user_first_name=user_first_name
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            return ticket
    
    async def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Получение тикета по ID"""
        async with db.session_maker() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            return result.scalar_one_or_none()
    
    async def get_user_tickets(self, user_id: int) -> List[Ticket]:
        """Получение всех тикетов пользователя"""
        async with db.session_maker() as session:
            result = await session.execute(
                select(Ticket)
                .where(Ticket.user_id == user_id)
                .order_by(Ticket.created_at.desc())
            )
            return result.scalars().all()
    
    async def get_all_tickets(self, statuses: Optional[List[str]] = None) -> List[Ticket]:
        """Получение всех тикетов с фильтрацией по статусам"""
        async with db.session_maker() as session:
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))
            query = query.order_by(Ticket.created_at.desc())
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_tickets_stats(self) -> Tuple[int, int, Optional[float]]:
        """Получение статистики по тикетам:
        (количество открытых, количество в работе, среднее время ответа)"""
        async with db.session_maker() as session:
            # Количество открытых тикетов
            open_count_result = await session.execute(
                select(func.count(Ticket.id))
                .where(Ticket.status == 'open')
            )
            open_count = open_count_result.scalar() or 0
            
            # Количество тикетов в работе
            in_progress_count_result = await session.execute(
                select(func.count(Ticket.id))
                .where(Ticket.status == 'in_progress')
            )
            in_progress_count = in_progress_count_result.scalar() or 0
            
            # Среднее время ответа (в минутах)
            avg_response_time = None
            avg_response_result = await session.execute(text("""
                SELECT AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60) 
                FROM tickets 
                WHERE first_response_at IS NOT NULL
            """))
            avg_response_row = avg_response_result.fetchone()
            if avg_response_row and avg_response_row[0] is not None:
                avg_response_time = round(float(avg_response_row[0]), 1)
            
            return open_count, in_progress_count, avg_response_time
    
    async def update_ticket_status(self, ticket_id: int, status: str) -> bool:
        """Обновление статуса тикета"""

        async with db.session_maker() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return False
            
            # Если статус меняется на in_progress и это первый ответ
            if status == 'in_progress' and ticket.status == 'open':
                ticket.first_response_at = datetime.now(timezone.utc)

            # Если статус меняется на closed (и ранее не был закрыт)
            if status == 'closed' and ticket.status != 'closed':
                ticket.closed_at = datetime.now(timezone.utc)

            ticket.status = status
            ticket.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return True

    async def close_ticket(self, ticket_id: int) -> bool:
        """Закрыть тикет (установить статус 'closed' и время закрытия)"""
        return await self.update_ticket_status(ticket_id, 'closed')
    
    async def add_message_to_ticket(
        self,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str
    ) -> TicketMessage:
        """Добавление сообщения к тикету"""
        async with db.session_maker() as session:
            ticket_message = TicketMessage(
                ticket_id=ticket_id,
                sender_type=sender_type,
                sender_id=sender_id,
                message=message
            )
            session.add(ticket_message)
            await session.commit()
            await session.refresh(ticket_message)
            return ticket_message
    
    async def get_ticket_messages(self, ticket_id: int) -> List[TicketMessage]:
        """Получение всех сообщений тикета"""
        async with db.session_maker() as session:
            result = await session.execute(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at.asc())
            )
            return result.scalars().all()

    async def get_tickets_page(
        self,
        page: int = 1,
        per_page: int = 10,
        statuses: Optional[List[str]] = None
    ) -> Tuple[List[Ticket], int]:
        """
        Получение одной страницы списка тикетов с пагинацией.

        :param page: Номер страницы (начиная с 1)
        :param per_page: Количество тикетов на одной странице
        :param statuses: Опциональный фильтр по статусам (например, ['open', 'in_progress'])
        :return: Кортеж (список тикетов на текущей странице, общее количество тикетов)
        """
        async with db.session_maker() as session:
            # Формируем базовый запрос с возможной фильтрацией по статусам
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))

            # Сортируем от новых к старым
            query = query.order_by(Ticket.created_at.desc())

            # Получаем общее количество тикетов (без пагинации)
            # Для этого создаём подзапрос из основного запроса и считаем строки
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await session.scalar(count_query) or 0

            # Применяем смещение (offset) и лимит (limit) для пагинации
            # offset = (номер_страницы - 1) * количество_на_странице
            query = query.offset((page - 1) * per_page).limit(per_page)

            # Выполняем запрос и получаем тикеты для текущей страницы
            result = await session.execute(query)
            tickets = result.scalars().all()

            return tickets, total_count

    async def get_tickets_total_pages(
        self,
        per_page: int = 10,
        statuses: Optional[List[str]] = None
    ) -> int:
        """
        Вычисление общего количества страниц для списка тикетов.

        :param per_page: Количество тикетов на странице
        :param statuses: Опциональный фильтр по статусам
        :return: Общее количество страниц (целое число)
        """
        async with db.session_maker() as session:
            # Строим запрос для подсчёта тикетов с учётом фильтра
            query = select(Ticket)
            if statuses:
                query = query.where(Ticket.status.in_(statuses))

            # Подсчитываем общее количество
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await session.scalar(count_query) or 0

            # Округление вверх: (total + per_page - 1) // per_page
            return (total_count + per_page - 1) // per_page


# Создаем глобальный экземпляр сервиса
ticket_service = TicketService()
