import asyncio
import os
import random
import string
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

sys.path.append(os.getcwd())
from backend.src.common.constants import SYSTEM_TELEGRAM_ID
from backend.src.common.enums import (
    ChangeType,
    DeliveryTimeType,
    DisputeResolutionType,
    DisputeStatus,
    OrderStatus,
    OrderType,
    TransactionType,
    UserRole,
    UserStatus,
)
from backend.src.core.database import AsyncSessionLocal
from backend.src.models.courier import Courier
from backend.src.models.courier_rating import CourierRating
from backend.src.models.dispute import Dispute
from backend.src.models.order import Order
from backend.src.models.order_history import OrderHistory
from backend.src.models.order_note import OrderNote
from backend.src.models.registration_code import RegistrationCode
from backend.src.models.shop import Shop
from backend.src.models.transaction import Transaction
from backend.src.models.user import User
from faker import Faker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NUM_ADMINS = 2  # Не включая фиксированных
NUM_SHOPS = 50
NUM_COURIERS = 100
NUM_ORDERS = 2000
NUM_UNUSED_CODES = 50  # Сколько создать свободных кодов
NUM_EXPIRED_CODES = 20  # Сколько создать просроченных кодов
BATCH_SIZE = 100  # Размер батча для оптимизации
SERVICE_FEE_PERCENT = Decimal("0.20")  # 20% комиссия сервиса
MAX_ORDER_DURATION_HOURS = 10  # Максимальная длительность заказа

fake = Faker("ru_RU")


def generate_code_string(length=8) -> str:
    """Генерирует случайный код из 8 символов (Буквы + Цифры)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def create_order_history_entries(
    order: Order,
    created_at: datetime,
    shop_user_id: int,
    courier_user_id: int | None = None,
    all_active_couriers: list[Courier] | None = None,
) -> list[OrderHistory]:
    """Создает полную историю изменений заказа (статусы, детали, переназначения)."""
    history = []
    current_time = created_at

    # Начальный статус - PENDING
    history.append(
        OrderHistory(
            order=order,
            changed_by_user_id=shop_user_id,
            change_type=ChangeType.STATUS_UPDATE,
            changes={"old": None, "new": OrderStatus.PENDING.value},
        )
    )

    # Словарь переходов статусов
    status_transitions = {
        OrderStatus.PENDING_COURIER: [OrderStatus.PENDING],
        OrderStatus.COURIER_EN_ROUTE: [OrderStatus.PENDING, OrderStatus.PENDING_COURIER],
        OrderStatus.DELIVERING: [
            OrderStatus.PENDING,
            OrderStatus.PENDING_COURIER,
            OrderStatus.COURIER_EN_ROUTE,
        ],
        OrderStatus.AWAITING_CONFIRMATION: [
            OrderStatus.PENDING,
            OrderStatus.PENDING_COURIER,
            OrderStatus.COURIER_EN_ROUTE,
            OrderStatus.DELIVERING,
        ],
        OrderStatus.COMPLETED: [
            OrderStatus.PENDING,
            OrderStatus.PENDING_COURIER,
            OrderStatus.COURIER_EN_ROUTE,
            OrderStatus.DELIVERING,
            OrderStatus.AWAITING_CONFIRMATION,
        ],
        OrderStatus.DISPUTED: [
            OrderStatus.PENDING,
            OrderStatus.PENDING_COURIER,
            OrderStatus.COURIER_EN_ROUTE,
            OrderStatus.DELIVERING,
            OrderStatus.AWAITING_CONFIRMATION,
        ],
        OrderStatus.CANCELED: [OrderStatus.PENDING, OrderStatus.PENDING_COURIER],
    }

    # Если финальный статус не PENDING, создаем промежуточные записи
    if order.status in status_transitions:
        transitions = status_transitions[order.status]
        time_delta = timedelta(minutes=random.randint(15, 45))

        previous_status = OrderStatus.PENDING
        for i, new_status in enumerate(transitions[1:], 1):
            if new_status == order.status or i >= len(transitions):
                break

            current_time += time_delta
            changed_by = (
                courier_user_id
                if courier_user_id and new_status != OrderStatus.PENDING_COURIER
                else shop_user_id
            )

            history.append(
                OrderHistory(
                    order=order,
                    changed_by_user_id=changed_by,
                    change_type=ChangeType.STATUS_UPDATE,
                    changes={"old": previous_status.value, "new": new_status.value},
                )
            )

            # Добавляем случайные DETAILS_UPDATE (10% шанс после каждого изменения статуса)
            if random.random() < 0.1:
                current_time += timedelta(minutes=random.randint(5, 15))
                details_changes = {}

                if random.random() < 0.5:
                    details_changes["description"] = {
                        "old": "Старое описание",
                        "new": fake.sentence(),
                    }

                if random.random() < 0.3 and order.delivery_time:
                    old_time = order.delivery_time
                    new_time = old_time + timedelta(minutes=random.randint(30, 120))
                    details_changes["delivery_time"] = {
                        "old": old_time.isoformat(),
                        "new": new_time.isoformat(),
                    }

                if details_changes:
                    history.append(
                        OrderHistory(
                            order=order,
                            changed_by_user_id=shop_user_id,
                            change_type=ChangeType.DETAILS_UPDATE,
                            changes=details_changes,
                        )
                    )

            # Добавляем COURIER_REASSIGN (5% шанс, только если есть курьер и список курьеров)
            if (
                random.random() < 0.05
                and courier_user_id
                and all_active_couriers
                and new_status in [OrderStatus.PENDING_COURIER, OrderStatus.COURIER_EN_ROUTE]
            ):
                current_time += timedelta(minutes=random.randint(10, 30))
                new_courier = random.choice(all_active_couriers)

                history.append(
                    OrderHistory(
                        order=order,
                        changed_by_user_id=shop_user_id,
                        change_type=ChangeType.COURIER_REASSIGN,
                        changes={
                            "old_courier_id": courier_user_id,
                            "new_courier_id": new_courier.user_id,
                            "reason": "Переназначение по запросу магазина",
                        },
                    )
                )

            previous_status = new_status

        # Финальный статус
        if order.status != OrderStatus.PENDING:
            current_time += time_delta
            changed_by = courier_user_id if courier_user_id else shop_user_id

            history.append(
                OrderHistory(
                    order=order,
                    changed_by_user_id=changed_by,
                    change_type=ChangeType.STATUS_UPDATE,
                    changes={"old": previous_status.value, "new": order.status.value},
                )
            )

    return history


def create_order_transactions(
    order: Order,
    shop_user_id: int,
    courier_user_id: int | None,
    system_user_id: int,
    created_at: datetime,
) -> list[Transaction]:
    """
    Создает транзакции для заказа согласно принципу двойной записи.

    Принцип: сумма всех транзакций = 0
    - amount < 0: пользователь должен системе
    - amount > 0: система должна пользователю
    """
    transactions = []

    # Расчёт сумм (округляем до целых)
    total_price = Decimal(int(order.price))
    service_fee = Decimal(int(total_price * SERVICE_FEE_PERCENT))
    courier_payment = total_price - service_fee

    # 1. Списание с магазина (магазин уходит в минус)
    transactions.append(
        Transaction(
            user_id=shop_user_id,
            order_id=order.id,
            type=TransactionType.ORDER_DEBIT,
            amount=-total_price,  # Отрицательная сумма - магазин должен
            description=f"Списание за заказ #{order.id}",
            created_at=created_at,
            created_by_admin_id=None,
        )
    )

    # 2. Начисление курьеру (если курьер назначен)
    if courier_user_id:
        transactions.append(
            Transaction(
                user_id=courier_user_id,
                order_id=order.id,
                type=TransactionType.ORDER_CREDIT,
                amount=courier_payment,  # Положительная сумма - система должна курьеру
                description=f"Начисление за заказ #{order.id}",
                created_at=created_at,
                created_by_admin_id=None,
            )
        )

    # 3. Комиссия сервиса
    transactions.append(
        Transaction(
            user_id=system_user_id,
            order_id=order.id,
            type=TransactionType.SERVICE_FEE,
            amount=service_fee,  # Прибыль системы
            description=f"Комиссия за заказ #{order.id}",
            created_at=created_at,
            created_by_admin_id=None,
        )
    )

    # Если курьер не назначен, весь платёж идёт системе
    if not courier_user_id:
        transactions.append(
            Transaction(
                user_id=system_user_id,
                order_id=order.id,
                type=TransactionType.ORDER_CREDIT,
                amount=courier_payment,
                description=f"Платёж за заказ #{order.id} (курьер не назначен)",
                created_at=created_at,
                created_by_admin_id=None,
            )
        )

    return transactions


async def create_users_with_roles(session: AsyncSession):
    """Создает пользователей, магазины и курьеров."""
    print(f"--- Создание пользователей ({NUM_SHOPS} магазинов, {NUM_COURIERS} курьеров)...")
    users = []
    shops = []
    couriers = []
    telegram_ids_set = set()

    def add_unique_telegram_id(tg_id):
        if tg_id in telegram_ids_set:
            raise ValueError(f"Дубликат telegram_id: {tg_id}")
        telegram_ids_set.add(tg_id)

    # system
    add_unique_telegram_id(SYSTEM_TELEGRAM_ID)
    system_user = User(
        telegram_id=SYSTEM_TELEGRAM_ID,
        username="SystemWallet",
        role=UserRole.SYSTEM,
        status=UserStatus.ACTIVE,
        registration_attempts=0,
    )
    users.append(system_user)

    # 1. Admins - фиксированные
    # Alisher
    alisher_tg_id = 5040147542
    add_unique_telegram_id(alisher_tg_id)
    alisher = User(
        telegram_id=alisher_tg_id,
        username="alisher_balpisov",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        registration_attempts=0,
    )
    users.append(alisher)

    # Shamil
    shamil_tg_id = 790095251
    add_unique_telegram_id(shamil_tg_id)
    shamil = User(
        telegram_id=shamil_tg_id,
        username="eidillum",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        registration_attempts=0,
    )
    users.append(shamil)

    # Остальные админы — случайные
    for _ in range(NUM_ADMINS):
        tg_id = fake.unique.random_number(digits=10)
        add_unique_telegram_id(tg_id)
        users.append(
            User(
                telegram_id=tg_id,
                username=fake.user_name(),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                registration_attempts=0,
            )
        )

    # 2. Shops
    for _ in range(NUM_SHOPS):
        tg_id = fake.unique.random_number(digits=10)
        add_unique_telegram_id(tg_id)
        user = User(
            telegram_id=tg_id,
            username=fake.user_name(),
            role=UserRole.SHOP,
            status=UserStatus.ACTIVE,
            registration_attempts=0,
        )
        users.append(user)
        shops.append(
            Shop(
                user=user,
                name=fake.company(),
                address=fake.address(),
                address_link=fake.url(),
                phone_number=[fake.phone_number()],
            )
        )

    # 3. Couriers
    for _ in range(NUM_COURIERS):
        tg_id = fake.unique.random_number(digits=10)
        add_unique_telegram_id(tg_id)
        user = User(
            telegram_id=tg_id,
            username=fake.user_name(),
            role=UserRole.COURIER,
            status=UserStatus.ACTIVE,
            registration_attempts=0,
        )
        users.append(user)

        # ФИО в правильном порядке: Фамилия Имя Отчество
        full_name = f"{fake.last_name()} {fake.first_name()} {fake.middle_name()}"

        couriers.append(
            Courier(
                user=user,
                full_name=full_name,
                phone_number=[fake.phone_number()],
                is_active=random.choice([True, False]),
                photo_id=fake.uuid4(),
            )
        )

    session.add_all(users)
    session.add_all(shops)
    session.add_all(couriers)
    await session.commit()
    print(f"✓ Создано {len(users)} пользователей (включая Alisher и Shamil)")
    return shops, couriers, users


async def create_registration_codes(session: AsyncSession, all_users: list[User]):
    """Создает коды регистрации: использованные, активные и просроченные."""
    print("--- Генерация кодов регистрации...")
    admins = [u for u in all_users if u.role == UserRole.ADMIN]
    shops = [u for u in all_users if u.role == UserRole.SHOP]
    couriers = [u for u in all_users if u.role == UserRole.COURIER]

    if not admins:
        print("!!! Ошибка: Нет админов для создания кодов.")
        return

    codes_batch = []
    generated_codes_set = set()

    def get_unique_code():
        while True:
            c = generate_code_string(8)
            if c not in generated_codes_set:
                generated_codes_set.add(c)
                return c

    # 1. Имитация ИСПОЛЬЗОВАННЫХ кодов (для существующих пользователей)
    target_users = shops + couriers
    for user in target_users:
        if random.random() < 0.6:
            creator = random.choice(admins)
            created_days_ago = random.randint(10, 60)
            created_at = datetime.now(UTC) - timedelta(days=created_days_ago)

            reg_code = RegistrationCode(
                code=get_unique_code(),
                role=user.role,
                is_used=True,
                used_by_user_id=user.id,
                created_by_admin_id=creator.id,
                expires_at=created_at + timedelta(days=7),
            )
            codes_batch.append(reg_code)

    # 2. Новые АКТИВНЫЕ коды
    for _ in range(NUM_UNUSED_CODES):
        creator = random.choice(admins)
        role = random.choice([UserRole.SHOP, UserRole.COURIER])
        reg_code = RegistrationCode(
            code=get_unique_code(),
            role=role,
            is_used=False,
            used_by_user_id=None,
            created_by_admin_id=creator.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        codes_batch.append(reg_code)

    # 3. ПРОСРОЧЕННЫЕ неиспользованные коды
    for _ in range(NUM_EXPIRED_CODES):
        creator = random.choice(admins)
        role = random.choice([UserRole.SHOP, UserRole.COURIER])
        expired_days_ago = random.randint(1, 30)

        reg_code = RegistrationCode(
            code=get_unique_code(),
            role=role,
            is_used=False,
            used_by_user_id=None,
            created_by_admin_id=creator.id,
            expires_at=datetime.now(UTC) - timedelta(days=expired_days_ago),
        )
        codes_batch.append(reg_code)

    session.add_all(codes_batch)
    await session.commit()
    print(
        f"✓ Добавлено {len(codes_batch)} кодов (активных: {NUM_UNUSED_CODES}, просроченных: {NUM_EXPIRED_CODES})"
    )


async def create_orders(
    session: AsyncSession, shops: list[Shop], couriers: list[Courier], all_users: list[User]
):
    """Создает заказы, споры, рейтинги, историю и транзакции."""
    print(f"--- Генерация {NUM_ORDERS} заказов...")

    orders_batch = []
    history_batch = []
    ratings_batch = []
    disputes_batch = []
    notes_batch = []
    transactions_batch = []

    admin_users = [u for u in all_users if u.role == UserRole.ADMIN]
    active_couriers = [c for c in couriers if c.is_active]
    system_user = next(u for u in all_users if u.role == UserRole.SYSTEM)

    if not active_couriers:
        print("!!! Предупреждение: Нет активных курьеров, используем всех")
        active_couriers = couriers

    for i in range(NUM_ORDERS):
        shop = random.choice(shops)
        status = random.choice(list(OrderStatus))

        # Создаем заказ в прошлом
        created_at = fake.date_time_between(start_date="-30d", end_date="now", tzinfo=UTC)

        delivery_type = random.choice(list(DeliveryTimeType))
        delivery_time = None

        if delivery_type == DeliveryTimeType.SCHEDULED:
            delivery_time = created_at + timedelta(hours=random.randint(1, 48))
        elif delivery_type == DeliveryTimeType.ASAP:
            delivery_time = created_at + timedelta(minutes=random.randint(30, 90))

        # Цена - целое число
        price = Decimal(random.randint(150, 5000))

        order = Order(
            shop_id=shop.id,
            status=status,
            order_type=random.choice(list(OrderType)),
            price=price,
            delivery_time_type=delivery_type,
            delivery_time=delivery_time,
            description=fake.text(max_nb_chars=100) if random.random() > 0.7 else None,
        )

        # Назначаем курьера если статус не PENDING
        courier = None
        if status != OrderStatus.PENDING:
            courier = random.choice(active_couriers)
            order.courier_id = courier.id

        # Устанавливаем completed_at для завершенных заказов (максимум 10 часов)
        if status in OrderStatus.completed_statuses():
            completion_minutes = random.randint(20, MAX_ORDER_DURATION_HOURS * 60)
            order.completed_at = created_at + timedelta(minutes=completion_minutes)

        orders_batch.append(order)

        # Коммитим батчами и создаем связанные объекты
        if len(orders_batch) >= BATCH_SIZE:
            # Сначала сохраняем заказы, чтобы они получили id
            session.add_all(orders_batch)
            await session.flush()

            # Теперь создаем связанные объекты для каждого заказа в батче
            for order_obj in orders_batch:
                order_shop = next(s for s in shops if s.id == order_obj.shop_id)
                order_courier = (
                    next((c for c in couriers if c.id == order_obj.courier_id), None)
                    if order_obj.courier_id
                    else None
                )

                # Создаем рейтинг
                if (
                    order_obj.status == OrderStatus.COMPLETED
                    and order_courier
                    and random.random() < 0.7
                ):
                    rating = CourierRating(
                        order_id=order_obj.id,
                        shop_id=order_obj.shop_id,
                        courier_id=order_courier.id,
                        rating=random.randint(1, 5),
                        comment=fake.sentence() if random.random() > 0.5 else None,
                    )
                    ratings_batch.append(rating)

                # Определяем, нужен ли спор
                should_create_dispute = False
                dispute_status = None

                if order_obj.status == OrderStatus.DISPUTED:
                    should_create_dispute = True
                    dispute_status = random.choice(
                        [DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW]
                    )
                elif order_obj.status == OrderStatus.COMPLETED and random.random() < 0.15:
                    should_create_dispute = True
                    dispute_status = DisputeStatus.RESOLVED
                elif (
                    order_obj.status in [OrderStatus.AWAITING_CONFIRMATION, OrderStatus.DELIVERING]
                    and random.random() < 0.08
                ):
                    should_create_dispute = True
                    dispute_status = random.choice(
                        [DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW]
                    )
                elif order_obj.status == OrderStatus.CANCELED and random.random() < 0.1:
                    should_create_dispute = True
                    dispute_status = random.choice(
                        [DisputeStatus.RESOLVED, DisputeStatus.CANCELLED]
                    )

                if should_create_dispute:
                    opener = (
                        order_shop.user
                        if random.random() < 0.6
                        else (order_courier.user if order_courier else order_shop.user)
                    )

                    # Вычисляем дату создания заказа из created_at
                    order_created_at = order_obj.created_at

                    dispute = Dispute(
                        order_id=order_obj.id,
                        opened_by_user_id=opener.id,
                        description=fake.text(max_nb_chars=200),
                        status=dispute_status,
                    )

                    if dispute_status in [DisputeStatus.RESOLVED, DisputeStatus.CANCELLED]:
                        admin = random.choice(admin_users) if admin_users else order_shop.user
                        dispute.resolved_by_admin_id = admin.id

                        if dispute_status == DisputeStatus.RESOLVED:
                            dispute.resolution_type = random.choice(list(DisputeResolutionType))
                            dispute.resolution_comment = fake.sentence()
                        else:
                            dispute.resolution_comment = "Спор отменён"

                        dispute.resolved_at = order_created_at + timedelta(
                            days=random.randint(1, 7)
                        )

                        # Штраф
                        if (
                            dispute_status == DisputeStatus.RESOLVED
                            and random.random() < 0.4
                            and order_courier
                        ):
                            fined_user_id = random.choice(
                                [order_shop.user_id, order_courier.user_id]
                            )
                            dispute.fined_user_id = fined_user_id
                            fine_amount = Decimal(random.randint(100, 1000))
                            dispute.fine_amount = fine_amount

                            # Транзакция штрафа
                            fine_transaction = Transaction(
                                user_id=fined_user_id,
                                order_id=order_obj.id,
                                type=TransactionType.Fine,
                                amount=-fine_amount,
                                description=f"Штраф по спору для заказа #{order_obj.id}",
                                created_at=dispute.resolved_at,
                                created_by_admin_id=admin.id,
                            )
                            transactions_batch.append(fine_transaction)

                            # Компенсация для системы
                            compensation_transaction = Transaction(
                                user_id=system_user.id,
                                order_id=order_obj.id,
                                type=TransactionType.Fine,
                                amount=fine_amount,
                                description=f"Получение штрафа по спору для заказа #{order_obj.id}",
                                created_at=dispute.resolved_at,
                                created_by_admin_id=admin.id,
                            )
                            transactions_batch.append(compensation_transaction)

                    disputes_batch.append(dispute)

                # Создаем транзакции для заказа
                order_transactions = create_order_transactions(
                    order=order_obj,
                    shop_user_id=order_shop.user_id,
                    courier_user_id=order_courier.user_id if order_courier else None,
                    system_user_id=system_user.id,
                    created_at=order_obj.created_at,
                )
                transactions_batch.extend(order_transactions)

                # История
                order_history = create_order_history_entries(
                    order_obj,
                    order_obj.created_at,
                    order_shop.user_id,
                    order_courier.user_id if order_courier else None,
                    all_active_couriers=active_couriers,
                )
                history_batch.extend(order_history)

                # Заметки
                if random.random() < 0.25:
                    note = OrderNote(
                        order_id=order_obj.id,
                        author_user_id=order_shop.user_id,
                        author_role=UserRole.SHOP,
                        content=f"Важно: {fake.sentence()}",
                    )
                    notes_batch.append(note)

                    if order_courier and random.random() < 0.4:
                        courier_note = OrderNote(
                            order_id=order_obj.id,
                            author_user_id=order_courier.user_id,
                            author_role=UserRole.COURIER,
                            content=f"Примечание курьера: {fake.sentence()}",
                        )
                        notes_batch.append(courier_note)

            # Сохраняем все связанные объекты
            session.add_all(history_batch)
            session.add_all(ratings_batch)
            session.add_all(disputes_batch)
            session.add_all(notes_batch)
            session.add_all(transactions_batch)
            await session.commit()

            print(f"  ✓ Обработано {i + 1}/{NUM_ORDERS} заказов...")

            # Очищаем батчи
            orders_batch = []
            history_batch = []
            ratings_batch = []
            disputes_batch = []
            notes_batch = []
            transactions_batch = []

        continue  # Переходим к следующему заказу

    # Обработка остатков (последний батч)
    if orders_batch:
        # Сначала сохраняем заказы
        session.add_all(orders_batch)
        await session.flush()

        # Создаем связанные объекты
        for order_obj in orders_batch:
            order_shop = next(s for s in shops if s.id == order_obj.shop_id)
            order_courier = (
                next((c for c in couriers if c.id == order_obj.courier_id), None)
                if order_obj.courier_id
                else None
            )

            # Рейтинг
            if (
                order_obj.status == OrderStatus.COMPLETED
                and order_courier
                and random.random() < 0.7
            ):
                rating = CourierRating(
                    order_id=order_obj.id,
                    shop_id=order_obj.shop_id,
                    courier_id=order_courier.id,
                    rating=random.randint(1, 5),
                    comment=fake.sentence() if random.random() > 0.5 else None,
                )
                ratings_batch.append(rating)

        # Создаем споры (БОЛЬШЕ ДАННЫХ)
        should_create_dispute = False
        dispute_status = None

        if status == OrderStatus.DISPUTED:
            # 100% для заказов со статусом DISPUTED
            should_create_dispute = True
            dispute_status = random.choice([DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW])
        elif status == OrderStatus.COMPLETED and random.random() < 0.15:
            # 15% завершенных заказов имели спор
            should_create_dispute = True
            dispute_status = DisputeStatus.RESOLVED
        elif (
            status in [OrderStatus.AWAITING_CONFIRMATION, OrderStatus.DELIVERING]
            and random.random() < 0.08
        ):
            # 8% для активных заказов
            should_create_dispute = True
            dispute_status = random.choice([DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW])
        elif status == OrderStatus.CANCELED and random.random() < 0.1:
            # 10% отмененных заказов
            should_create_dispute = True
            dispute_status = random.choice([DisputeStatus.RESOLVED, DisputeStatus.CANCELLED])

        if should_create_dispute:
            opener = (
                shop.user if random.random() < 0.6 else (courier.user if courier else shop.user)
            )

            dispute = Dispute(
                order=order,
                opened_by_user_id=opener.id,
                description=fake.text(max_nb_chars=200),
                status=dispute_status,
            )

            if dispute_status in [DisputeStatus.RESOLVED, DisputeStatus.CANCELLED]:
                admin = random.choice(admin_users) if admin_users else shop.user
                dispute.resolved_by_admin_id = admin.id

                if dispute_status == DisputeStatus.RESOLVED:
                    dispute.resolution_type = random.choice(list(DisputeResolutionType))
                    dispute.resolution_comment = fake.sentence()
                else:
                    dispute.resolution_comment = "Спор отменён"

                dispute.resolved_at = cast(
                    datetime,
                    created_at + timedelta(days=random.randint(1, 7)),
                )

                # 40% шанс назначить штраф для разрешенных споров
                if dispute_status == DisputeStatus.RESOLVED and random.random() < 0.4 and courier:
                    fined_user_id = random.choice([shop.user_id, courier.user_id])
                    dispute.fined_user_id = fined_user_id
                    fine_amount = Decimal(random.randint(100, 1000))
                    dispute.fine_amount = fine_amount

                    # Создаём транзакцию штрафа
                    fine_transaction = Transaction(
                        user_id=fined_user_id,
                        order_id=order.id,
                        type=TransactionType.Fine,
                        amount=-fine_amount,
                        description=f"Штраф по спору для заказа #{order.id}",
                        created_at=dispute.resolved_at,
                        created_by_admin_id=admin.id,
                    )
                    transactions_batch.append(fine_transaction)

                    # Компенсирующая транзакция для системы
                    compensation_transaction = Transaction(
                        user_id=system_user.id,
                        order_id=order.id,
                        type=TransactionType.Fine,
                        amount=fine_amount,
                        description=f"Получение штрафа по спору для заказа #{order.id}",
                        created_at=dispute.resolved_at,
                        created_by_admin_id=admin.id,
                    )
                    transactions_batch.append(compensation_transaction)

            disputes_batch.append(dispute)

        # Создаем транзакции для заказа
        order_transactions = create_order_transactions(
            order=order,
            shop_user_id=shop.user_id,
            courier_user_id=courier.user_id if courier else None,
            system_user_id=system_user.id,
            created_at=created_at,
        )
        transactions_batch.extend(order_transactions)

        # Создаем полную историю изменений (с DETAILS_UPDATE и COURIER_REASSIGN)
        order_history = create_order_history_entries(
            order,
            created_at,
            shop.user_id,
            courier.user_id if courier else None,
            all_active_couriers=active_couriers,
        )
        history_batch.extend(order_history)

        # Создаем заметки (25% шанс)
        if random.random() < 0.25:
            note = OrderNote(
                order=order,
                author_user_id=shop.user_id,
                author_role=UserRole.SHOP,
                content=f"Важно: {fake.sentence()}",
            )
            notes_batch.append(note)

            if courier and random.random() < 0.4:
                courier_note = OrderNote(
                    order=order,
                    author_user_id=courier.user_id,
                    author_role=UserRole.COURIER,
                    content=f"Примечание курьера: {fake.sentence()}",
                )
                notes_batch.append(courier_note)

        # Коммитим батчами
        if len(orders_batch) >= BATCH_SIZE:
            session.add_all(orders_batch)
            await session.flush()

            session.add_all(history_batch)
            session.add_all(ratings_batch)
            session.add_all(disputes_batch)
            session.add_all(notes_batch)
            session.add_all(transactions_batch)
            await session.commit()

            print(f"  ✓ Обработано {i + 1}/{NUM_ORDERS} заказов...")

            orders_batch = []
            history_batch = []
            ratings_batch = []
            disputes_batch = []
            notes_batch = []
            transactions_batch = []

    # Коммитим остатки
    if orders_batch:
        session.add_all(orders_batch)
        await session.flush()

        session.add_all(history_batch)
        session.add_all(ratings_batch)
        session.add_all(disputes_batch)
        session.add_all(notes_batch)
        session.add_all(transactions_batch)
        await session.commit()

    print(f"✓ Создано {NUM_ORDERS} заказов с полной историей и транзакциями")


async def create_manual_transactions(
    session: AsyncSession, shops: list[Shop], couriers: list[Courier], all_users: list[User]
):
    """Создаёт ручные транзакции (инкассации и выплаты)."""
    print("--- Генерация ручных транзакций (инкассации и выплаты)...")

    admin_users = [u for u in all_users if u.role == UserRole.ADMIN]
    system_user = next(u for u in all_users if u.role == UserRole.SYSTEM)
    transactions_batch = []

    if not admin_users:
        print("!!! Предупреждение: Нет админов для создания ручных транзакций")
        return

    # Инкассация у магазинов (30% магазинов)
    for shop in random.sample(shops, k=int(NUM_SHOPS * 0.3)):
        admin = random.choice(admin_users)
        amount = Decimal(random.randint(1000, 10000))
        transaction_date = fake.date_time_between(start_date="-20d", end_date="now", tzinfo=UTC)

        # Инкассация у магазина
        transactions_batch.append(
            Transaction(
                user_id=shop.user_id,
                order_id=None,
                type=TransactionType.CASH_COLLECTION,
                amount=amount,
                description=f"Инкассация наличных у {shop.name}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

        # Компенсирующая запись для системы
        transactions_batch.append(
            Transaction(
                user_id=system_user.id,
                order_id=None,
                type=TransactionType.CASH_COLLECTION,
                amount=-amount,
                description=f"Получение наличных от {shop.name}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

    # Выплаты курьерам (40% курьеров)
    for courier in random.sample(couriers, k=int(NUM_COURIERS * 0.4)):
        admin = random.choice(admin_users)
        amount = Decimal(random.randint(500, 5000))
        transaction_date = fake.date_time_between(start_date="-20d", end_date="now", tzinfo=UTC)

        # Выплата курьеру
        transactions_batch.append(
            Transaction(
                user_id=courier.user_id,
                order_id=None,
                type=TransactionType.PAYOUT,
                amount=-amount,
                description=f"Выплата курьеру {courier.full_name}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

        # Компенсирующая запись для системы
        transactions_batch.append(
            Transaction(
                user_id=system_user.id,
                order_id=None,
                type=TransactionType.PAYOUT,
                amount=amount,
                description=f"Выдача наличных курьеру {courier.full_name}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

    # Корректировки (несколько случайных)
    for _ in range(random.randint(5, 15)):
        user_pool = [s.user for s in shops] + [c.user for c in couriers]
        target_user = random.choice(user_pool)
        admin = random.choice(admin_users)

        amount = Decimal(random.randint(-500, 500))
        if amount == 0:
            amount = Decimal(100)

        transaction_date = fake.date_time_between(start_date="-15d", end_date="now", tzinfo=UTC)

        # Корректировка баланса
        transactions_batch.append(
            Transaction(
                user_id=target_user.id,
                order_id=None,
                type=TransactionType.ADJUSTMENT,
                amount=amount,
                description=f"Ручная корректировка баланса: {fake.sentence()}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

        # Компенсирующая запись для системы
        transactions_batch.append(
            Transaction(
                user_id=system_user.id,
                order_id=None,
                type=TransactionType.ADJUSTMENT,
                amount=-amount,
                description=f"Корректировка баланса для {target_user.username}",
                created_at=transaction_date,
                created_by_admin_id=admin.id,
            )
        )

    session.add_all(transactions_batch)
    await session.commit()
    print(f"✓ Создано {len(transactions_batch)} ручных транзакций")


async def main():
    async with AsyncSessionLocal() as session:
        # 0. Очистка таблиц перед генерацией
        print("=" * 60)
        print("ОЧИСТКА БАЗЫ ДАННЫХ")
        print("=" * 60)

        tables = [
            "transactions",
            "order_notes",
            "disputes",
            "courier_ratings",
            "order_history",
            "orders",
            "registration_codes",
            "couriers",
            "shops",
            "users",
        ]

        for table in tables:
            await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            print(f"✓ Очищена таблица: {table}")

        await session.commit()
        print()

        # 1. Пользователи
        print("=" * 60)
        print("СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 60)
        shops, couriers, all_users = await create_users_with_roles(session)
        print()

        # 2. Коды регистрации
        print("=" * 60)
        print("СОЗДАНИЕ КОДОВ РЕГИСТРАЦИИ")
        print("=" * 60)
        await create_registration_codes(session, all_users)
        print()

        # 3. Заказы (включая транзакции по заказам)
        print("=" * 60)
        print("СОЗДАНИЕ ЗАКАЗОВ")
        print("=" * 60)
        await create_orders(session, shops, couriers, all_users)
        print()

        # 4. Ручные транзакции
        print("=" * 60)
        print("СОЗДАНИЕ РУЧНЫХ ТРАНЗАКЦИЙ")
        print("=" * 60)
        await create_manual_transactions(session, shops, couriers, all_users)
        print()

    print("=" * 60)
    print("✅ ГЕНЕРАЦИЯ ВСЕХ ТЕСТОВЫХ ДАННЫХ ЗАВЕРШЕНА!")
    print("=" * 60)
    print("Создано:")
    print(f"  - Пользователей: {len(all_users)}")
    print(f"  - Магазинов: {NUM_SHOPS}")
    print(f"  - Курьеров: {NUM_COURIERS}")
    print(f"  - Заказов: {NUM_ORDERS}")
    print(f"  - Активных кодов: {NUM_UNUSED_CODES}")
    print(f"  - Просроченных кодов: {NUM_EXPIRED_CODES}")
    print(f"  - Максимальная длительность заказа: {MAX_ORDER_DURATION_HOURS} часов")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Скрипт остановлен пользователем.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\nЗавершение работы...")
