from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.models import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _active_conditions(self, category: str | None = None) -> list:
        conditions = [Product.status == "active"]
        if category:
            conditions.append(Product.category == category)
        return conditions

    async def find_by_category(
        self,
        category: str | None = None,
        page: int = 1,
        page_size: int = 6,
    ) -> tuple[list[Product], int]:
        conditions = self._active_conditions(category)

        total = await self.session.scalar(
            select(func.count()).select_from(Product).where(*conditions)
        ) or 0

        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(products.all()), int(total)

    async def find_limited_by_category(
            self,
            category: str,
            premium_min: Decimal | None,
            limit: int,
    ) -> list[Product]:
        conditions = [
            Product.status == "active",
            Product.category == category,
        ]
        if premium_min is not None:
            conditions.append(Product.min_premium < premium_min)

        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(
                Product.min_premium.asc().nullslast(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        return products.all()