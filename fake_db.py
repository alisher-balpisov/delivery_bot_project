import asyncio

# Добавляем корневую директорию в путь
import os
import random
import string
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

sys.path.append(os.getcwd())
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

# --- ИМПОРТЫ ---
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
from sqlalchemy import text  # Для SQL-запросов
from sqlalchemy.ext.asyncio import AsyncSession

# --- НАСТРОЙКИ ---
NUM_ADMINS = 2
NUM_SHOPS = 50
NUM_COURIERS = 100
NUM_ORDERS = 2000
NUM_UNUSED_CODES = 50  # Сколько создать свободных кодов
NUM_EXPIRED_CODES = 20  # Сколько создать просроченных кодов

fake = Faker("ru_RU")


def generate_code_string(length=8) -> str:
    """Генерирует случайный код из 8 символов (Буквы + Цифры)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


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

    # 1. Admins
    # Фиксированный alisher только один раз
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

    # Остальные админы — случайные
    for _ in range(NUM_ADMINS - 1):  # Минус один, т.к. alisher уже добавлен
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
                is_active=True,
                photo_id=fake.uuid4(),
            )
        )

    session.add_all(users)
    session.add_all(shops)
    session.add_all(couriers)
    await session.commit()
    return shops, couriers, users


async def create_registration_codes(session: AsyncSession, all_users: List[User]):
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
            created_at = fake.date_time_between(start_date="-60d", end_date="-10d")
            reg_code = RegistrationCode(
                code=get_unique_code(),
                role=user.role,
                is_used=True,
                used_by_user_id=user.id,
                created_by_admin_id=creator.id,
                # Срок действия истек неделю после создания (но он уже использован, так что ок)
                expires_at=created_at + timedelta(days=7),
                # created_at=created_at # Если в Base есть created_at
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
            expires_at=datetime.now() + timedelta(days=7),  # Действителен еще неделю
        )
        codes_batch.append(reg_code)

    # 3. ПРОСРОЧЕННЫЕ неиспользованные коды
    for _ in range(NUM_EXPIRED_CODES):
        creator = random.choice(admins)
        role = random.choice([UserRole.SHOP, UserRole.COURIER])
        reg_code = RegistrationCode(
            code=get_unique_code(),
            role=role,
            is_used=False,
            used_by_user_id=None,
            created_by_admin_id=creator.id,
            expires_at=datetime.now() - timedelta(days=1),  # Истек вчера
        )
        codes_batch.append(reg_code)

    session.add_all(codes_batch)
    await session.commit()
    print(f"--- Добавлено {len(codes_batch)} кодов (в т.ч. {NUM_UNUSED_CODES} активных).")


async def create_orders(
    session: AsyncSession, shops: List[Shop], couriers: List[Courier], all_users: List[User]
):
    """Создает заказы, споры, рейтинги и историю."""
    print(f"--- Генерация {NUM_ORDERS} заказов...")
    orders_batch = []
    history_batch = []
    ratings_batch = []
    disputes_batch = []
    notes_batch = []
    admin_users = [u for u in all_users if u.role == UserRole.ADMIN]
    for _ in range(NUM_ORDERS):
        shop = random.choice(shops)
        status = random.choice(list(OrderStatus))
        created_at = fake.date_time_between(start_date="-30d", end_date="now")
        delivery_type = random.choice(list(DeliveryTimeType))
        delivery_time = None
        if delivery_type == DeliveryTimeType.SCHEDULED:
            delivery_time = created_at + timedelta(hours=random.randint(1, 48))
        price = Decimal(random.uniform(150.00, 5000.00)).quantize(Decimal("0.01"))
        order = Order(
            shop_id=shop.id,
            status=status,
            order_type=random.choice(list(OrderType)),
            price=price,
            delivery_time_type=delivery_type,
            delivery_time=delivery_time,
            description=fake.text(max_nb_chars=100) if random.random() > 0.7 else None,
            # created_at=created_at
        )
        courier = None
        if status != OrderStatus.PENDING:
            courier = random.choice(couriers)
            order.courier_id = courier.id
        if status in OrderStatus.completed_statuses():
            completion_delay = timedelta(minutes=random.randint(20, 120))
            order.completed_at = created_at + completion_delay
        if status == OrderStatus.COMPLETED and courier and random.random() < 0.7:
            rating = CourierRating(
                order=order,
                shop_id=shop.id,
                courier_id=courier.id,
                rating=random.randint(1, 5),
                comment=fake.sentence() if random.random() > 0.5 else None,
            )
            ratings_batch.append(rating)
        if status == OrderStatus.DISPUTED or (
            status == OrderStatus.COMPLETED and random.random() < 0.05
        ):
            if status == OrderStatus.COMPLETED:
                dispute_status = DisputeStatus.RESOLVED
            else:
                dispute_status = random.choice(
                    [DisputeStatus.PENDING_REVIEW, DisputeStatus.IN_REVIEW]
                )
            opener = shop.user
            dispute = Dispute(
                order=order,
                opened_by_user_id=opener.id,
                description=fake.text(),
                status=dispute_status,
                # created_at=created_at + timedelta(minutes=30)
            )
            if dispute_status == DisputeStatus.RESOLVED:
                admin = random.choice(admin_users) if admin_users else opener
                dispute.resolved_by_admin_id = admin.id
                dispute.resolution_type = random.choice(list(DisputeResolutionType))
                dispute.resolved_at = datetime.now()
                dispute.resolution_comment = fake.sentence()
                if random.random() < 0.3:
                    dispute.fined_user_id = courier.user_id
                    dispute.fine_amount = Decimal("500.00")
            disputes_batch.append(dispute)
        history = OrderHistory(
            order=order,
            changed_by_user_id=shop.user_id,
            change_type=ChangeType.STATUS_UPDATE,
            changes={"old": None, "new": OrderStatus.PENDING.value},
            # created_at=created_at
        )
        history_batch.append(history)
        if random.random() < 0.2:
            note = OrderNote(
                order=order,
                author_user_id=shop.user_id,
                author_role=UserRole.SHOP,
                content=f"Важно: {fake.sentence()}",
                # created_at=created_at
            )
            notes_batch.append(note)
        orders_batch.append(order)
        if len(orders_batch) >= 500:
            session.add_all(orders_batch)
            await session.flush()
            session.add_all(history_batch)
            session.add_all(ratings_batch)
            session.add_all(disputes_batch)
            session.add_all(notes_batch)
            orders_batch = []
            history_batch = []
            ratings_batch = []
            disputes_batch = []
            notes_batch = []

    session.add_all(orders_batch)
    await session.flush()
    session.add_all(history_batch)
    session.add_all(ratings_batch)
    session.add_all(disputes_batch)
    session.add_all(notes_batch)
    await session.commit()
    print("--- Заказы и связанные данные успешно созданы.")


async def main():
    async with AsyncSessionLocal() as session:
        # 0. Очистка таблиц перед генерацией (чтобы избежать дубликатов)
        print("--- Очистка существующих данных...")
        # Очищаем в порядке, обратном зависимостям (сначала дочерние таблицы)
        await session.execute(text("TRUNCATE TABLE order_notes CASCADE;"))
        await session.execute(text("TRUNCATE TABLE disputes CASCADE;"))
        await session.execute(text("TRUNCATE TABLE courier_ratings CASCADE;"))
        await session.execute(text("TRUNCATE TABLE order_history CASCADE;"))
        await session.execute(text("TRUNCATE TABLE orders CASCADE;"))
        await session.execute(text("TRUNCATE TABLE registration_codes CASCADE;"))
        await session.execute(text("TRUNCATE TABLE couriers CASCADE;"))
        await session.execute(text("TRUNCATE TABLE shops CASCADE;"))
        await session.execute(text("TRUNCATE TABLE users CASCADE;"))
        await session.commit()  # Коммит очистки

        # 1. Пользователи
        shops, couriers, all_users = await create_users_with_roles(session)

        # 2. Коды регистрации (NEW)
        await create_registration_codes(session, all_users)

        # 3. Заказы
        await create_orders(session, shops, couriers, all_users)

    print("\n✅ Генерация всех тестовых данных завершена!")


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Скрипт остановлен.")
