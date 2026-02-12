from typing import TYPE_CHECKING

from backend.src.common.enums import TransactionType, UserRole
from backend.src.models import Transaction, User

if TYPE_CHECKING:
    from backend.src.models import Order
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_system_user_id(self) -> int:
        """Получаем ID внутреннего кошелька системы."""
        stmt = select(User.id).where(User.role == UserRole.SYSTEM)
        result = await self.session.execute(stmt)
        user_id = result.scalar_one_or_none()
        if user_id is None:
            raise ValueError("System user not found! Run init_data.")
        return user_id

    async def get_balance(self, user_id: int) -> int:
        """
        Возвращает текущий баланс пользователя.
        Отрицательный = пользователь должен нам.
        Положительный = мы должны пользователю.
        """
        stmt = select(func.sum(Transaction.amount)).where(Transaction.user_id == user_id)
        result = await self.session.execute(stmt)
        balance = result.scalar()
        return int(balance) if balance is not None else 0

    async def process_order_completion(
        self,
        order: Order,
        shop_user_id: int,
        courier_user_id: int,
        commission_rate: float = 0.20,  # 20%
    ) -> None:
        """
        Распределяет деньги после завершения заказа.
        Пример: Заказ 1000. Комиссия 200. Курьеру 800.
        """
        system_user_id = await self._get_system_user_id()

        total_price = order.price or 0  # 1000
        service_profit = int(total_price * commission_rate)  # 200
        courier_earning = total_price - service_profit  # 800

        transactions = [
            # 1. Списываем с магазина (Долг магазина растет)
            Transaction(
                user_id=shop_user_id,
                order_id=order.id,
                type=TransactionType.ORDER_DEBIT,
                amount=-total_price,  # -1000
                description=f"Оплата доставки заказа #{order.id}",
            ),
            # 2. Начисляем курьеру (Наш долг перед ним растет)
            Transaction(
                user_id=courier_user_id,
                order_id=order.id,
                type=TransactionType.ORDER_CREDIT,
                amount=courier_earning,  # +800
                description=f"Выплата за заказ #{order.id}",
            ),
            # 3. Фиксируем прибыль системы
            Transaction(
                user_id=system_user_id,
                order_id=order.id,
                type=TransactionType.SERVICE_FEE,
                amount=service_profit,  # +200
                description=f"Комиссия с заказа #{order.id}",
            ),
        ]

        self.session.add_all(transactions)
        # Commit делается на уровне контроллера/роутера

    async def process_cash_collection(
        self, shop_user_id: int, amount: int, admin_id: int
    ) -> Transaction:
        """
        Магазин отдает наличные админу.
        Баланс магазина: увеличивается (долг гасится).
        Баланс системы: уменьшается (мы получили кэш, прибыль "выведена" в карман).
        """
        system_user_id = await self._get_system_user_id()

        # Магазин гасит долг (+1000)
        shop_txn = Transaction(
            user_id=shop_user_id,
            type=TransactionType.CASH_COLLECTION,
            amount=amount,
            created_by_admin_id=admin_id,
            description="Инкассация наличных",
        )

        # Для равновесия системы записываем минус на системный кошелек
        # (Означает, что деньги перешли из виртуальных долгов в реальный кэш у админа)
        system_txn = Transaction(
            user_id=system_user_id,
            type=TransactionType.CASH_COLLECTION,
            amount=-amount,
            created_by_admin_id=admin_id,
            description=f"Поступление наличных от магазина #{shop_user_id}",
        )

        self.session.add_all([shop_txn, system_txn])
        return shop_txn

    async def process_courier_payout(
        self, courier_user_id: int, amount: int, admin_id: int
    ) -> Transaction:
        """
        Админ отдает наличные курьеру.
        Баланс курьера: уменьшается (мы погасили долг перед ним).
        Баланс системы: увеличивается (мы отдали кэш).
        """
        system_user_id = await self._get_system_user_id()

        # Мы отдаем долг курьеру (-800)
        courier_txn = Transaction(
            user_id=courier_user_id,
            type=TransactionType.PAYOUT,
            amount=-amount,
            created_by_admin_id=admin_id,
            description="Выплата заработка",
        )

        # Балансируем систему
        system_txn = Transaction(
            user_id=system_user_id,
            type=TransactionType.PAYOUT,
            amount=amount,
            created_by_admin_id=admin_id,
            description=f"Выплата наличных курьеру #{courier_user_id}",
        )

        self.session.add_all([courier_txn, system_txn])
        return courier_txn
