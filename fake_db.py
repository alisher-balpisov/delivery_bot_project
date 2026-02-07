import asyncio
import os
import random
import string
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

sys.path.append(os.getcwd())
from backend.src.common.constants import SYSTEM_TELEGRAM_ID
from backend.src.common.enums import (
    ChangeType,
    DeliveryTimeType,
    DisputeResolutionType,
    DisputeStatus,
    OrderStatus,
    OrderType,
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

fake = Faker("ru_RU")


def generate_code_string(length=8) -> str:
    """Генерирует случайный код из 8 символов (Буквы + Цифры)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def create_order_history_entries(
    order: Order, created_at: datetime, shop_user_id: int, courier_user_id: int | None = None
) -> list[OrderHistory]:
    """Создает полную историю изменений статуса заказа."""
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
        time_delta = timedelta(minutes=10)  # Интервал между статусами

        previous_status = OrderStatus.PENDING
        for i, new_status in enumerate(transitions[1:], 1):  # Пропускаем PENDING (уже создан)
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


async def create_users_with_roles(session: AsyncSession):
    """Создает пользователей, магазины и курьеров."""
    print(f"--- Создание пользователей ({NUM_SHOPS} магазинов, {NUM_COURIERS} курьеров)...")
    users = []
    shops = []
    couriers = []
    telegram_ids_set = set()  # Для проверки уникальности telegram_id в памяти

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
    shamil_tg_id = 123456789
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
        couriers.append(
            Courier(
                user=user,
                full_name=fake.name(),
                phone_number=[fake.phone_number()],
                is_active=random.choice([True, False]),  # Некоторые курьеры неактивны
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
    generated_codes_set = set()  # Для проверки уникальности в памяти

    # Хелпер для уникальности
    def get_unique_code():
        while True:
            c = generate_code_string(8)
            if c not in generated_codes_set:
                generated_codes_set.add(c)
                return c

    # 1. Имитация ИСПОЛЬЗОВАННЫХ кодов (для существующих пользователей)
    # Предположим, 60% пользователей пришли по кодам
    target_users = shops + couriers
    for user in target_users:
        if random.random() < 0.6:
            creator = random.choice(admins)
            # Код был создан в прошлом (например, месяц назад)
            created_days_ago = random.randint(10, 60)
            created_at = datetime.now(UTC) - timedelta(days=created_days_ago)

            reg_code = RegistrationCode(
                code=get_unique_code(),
                role=user.role,
                is_used=True,
                used_by_user_id=user.id,
                created_by_admin_id=creator.id,
                # Срок действия был 7 дней с момента создания
                expires_at=created_at + timedelta(days=7),
            )
            codes_batch.append(reg_code)

    # 2. Новые АКТИВНЫЕ коды (можно использовать сейчас)
    for _ in range(NUM_UNUSED_CODES):
        creator = random.choice(admins)
        role = random.choice([UserRole.SHOP, UserRole.COURIER])
        reg_code = RegistrationCode(
            code=get_unique_code(),
            role=role,
            is_used=False,
            used_by_user_id=None,
            created_by_admin_id=creator.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),  # Действителен еще неделю
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
            expires_at=datetime.now(UTC) - timedelta(days=expired_days_ago),  # Истек
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
    """Создает заказы, споры, рейтинги и историю."""
    print(f"--- Генерация {NUM_ORDERS} заказов...")

    orders_batch = []
    history_batch = []
    ratings_batch = []
    disputes_batch = []
    notes_batch = []
    admin_users = [u for u in all_users if u.role == UserRole.ADMIN]
    active_couriers = [c for c in couriers if c.is_active]

    if not active_couriers:
        print("!!! Предупреждение: Нет активных курьеров, используем всех")
        active_couriers = couriers

    for i in range(NUM_ORDERS):
        shop = random.choice(shops)
        status = random.choice(list(OrderStatus))

        # Создаем заказ в прошлом (от 30 дней назад до сейчас)
        created_at = fake.date_time_between(start_date="-30d", end_date="now", tzinfo=UTC)

        delivery_type = random.choice(list(DeliveryTimeType))
        delivery_time = None

        if delivery_type == DeliveryTimeType.SCHEDULED:
            # Запланированное время должно быть в будущем от created_at
            delivery_time = created_at + timedelta(hours=random.randint(1, 48))
        elif delivery_type == DeliveryTimeType.ASAP:
            # ASAP обычно в течение часа
            delivery_time = created_at + timedelta(minutes=random.randint(30, 90))

        price = Decimal(random.uniform(150.00, 5000.00)).quantize(Decimal("0.01"))

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

        # Устанавливаем completed_at для завершенных заказов
        if status in OrderStatus.completed_statuses():
            completion_delay = timedelta(minutes=random.randint(20, 180))
            order.completed_at = created_at + completion_delay

        orders_batch.append(order)

        # Создаем рейтинг для завершенных заказов (70% случаев)
        if status == OrderStatus.COMPLETED and courier and random.random() < 0.7:
            rating = CourierRating(
                order=order,
                shop_id=shop.id,
                courier_id=courier.id,
                rating=random.randint(1, 5),
                comment=fake.sentence() if random.random() > 0.5 else None,
            )
            ratings_batch.append(rating)

        # Создаем споры
        should_create_dispute = False
        dispute_status = None

        if status == OrderStatus.DISPUTED:
            should_create_dispute = True
            dispute_status = random.choice([DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW])
        elif status == OrderStatus.COMPLETED and random.random() < 0.05:
            # 5% завершенных заказов имели спор, который был разрешен
            should_create_dispute = True
            dispute_status = DisputeStatus.RESOLVED

        if should_create_dispute:
            # Спор может открыть либо магазин, либо курьер
            opener = (
                shop.user if random.random() < 0.6 else (courier.user if courier else shop.user)
            )

            dispute = Dispute(
                order=order,
                opened_by_user_id=opener.id,
                description=fake.text(max_nb_chars=200),
                status=dispute_status,
            )

            if dispute_status == DisputeStatus.RESOLVED:
                admin = random.choice(admin_users) if admin_users else shop.user
                dispute.resolved_by_admin_id = admin.id
                dispute.resolution_type = random.choice(list(DisputeResolutionType))
                dispute.resolved_at = created_at + timedelta(days=random.randint(1, 7))
                dispute.resolution_comment = fake.sentence()

                # 30% шанс назначить штраф
                if random.random() < 0.3 and courier:
                    # Штраф может быть назначен либо магазину, либо курьеру
                    dispute.fined_user_id = random.choice([shop.user_id, courier.user_id])
                    dispute.fine_amount = Decimal(random.uniform(100.00, 1000.00)).quantize(
                        Decimal("0.01")
                    )

            disputes_batch.append(dispute)

        # Создаем полную историю изменений статуса
        order_history = create_order_history_entries(
            order, created_at, shop.user_id, courier.user_id if courier else None
        )
        history_batch.extend(order_history)

        # Создаем заметки (20% шанс)
        if random.random() < 0.2:
            # Заметка от магазина
            note = OrderNote(
                order=order,
                author_user_id=shop.user_id,
                author_role=UserRole.SHOP,
                content=f"Важно: {fake.sentence()}",
            )
            notes_batch.append(note)

            # Иногда курьер тоже оставляет заметку
            if courier and random.random() < 0.3:
                courier_note = OrderNote(
                    order=order,
                    author_user_id=courier.user_id,
                    author_role=UserRole.COURIER,
                    content=f"Примечание курьера: {fake.sentence()}",
                )
                notes_batch.append(courier_note)

        # Коммитим батчами для оптимизации
        if len(orders_batch) >= BATCH_SIZE:
            session.add_all(orders_batch)
            await session.flush()

            session.add_all(history_batch)
            session.add_all(ratings_batch)
            session.add_all(disputes_batch)
            session.add_all(notes_batch)
            await session.commit()

            print(f"  ✓ Обработано {i + 1}/{NUM_ORDERS} заказов...")

            # Очищаем батчи
            orders_batch = []
            history_batch = []
            ratings_batch = []
            disputes_batch = []
            notes_batch = []

    # Коммитим остатки
    if orders_batch:
        session.add_all(orders_batch)
        await session.flush()

        session.add_all(history_batch)
        session.add_all(ratings_batch)
        session.add_all(disputes_batch)
        session.add_all(notes_batch)
        await session.commit()

    print(f"✓ Создано {NUM_ORDERS} заказов с полной историей")


async def main():
    async with AsyncSessionLocal() as session:
        # 0. Очистка таблиц перед генерацией
        print("=" * 60)
        print("ОЧИСТКА БАЗЫ ДАННЫХ")
        print("=" * 60)

        # Очищаем в порядке, обратном зависимостям (сначала дочерние таблицы)
        tables = [
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

        # 3. Заказы
        print("=" * 60)
        print("СОЗДАНИЕ ЗАКАЗОВ")
        print("=" * 60)
        await create_orders(session, shops, couriers, all_users)
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
    print("=" * 60)


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Скрипт остановлен пользователем.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\nЗавершение работы...")
