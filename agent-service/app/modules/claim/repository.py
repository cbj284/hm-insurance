from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.claim.models import Claim
from app.modules.policy.models import Policy
from app.modules.product.models import Product


class ClaimRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(
        self,
        user_id: int,
        claim_number: str | None = None,
        policy_number: str | None = None,
    ) -> list[tuple[Claim, Policy | None, Product | None]]:
        stmt = (
            select(Claim, Policy, Product)
            .outerjoin(Policy, Policy.id == Claim.policy_id)
            .outerjoin(Product, Product.id == Claim.product_id)
            .where(Claim.user_id == user_id)
            .order_by(Claim.updated_at.desc())
        )
        if claim_number:
            stmt = stmt.where(Claim.claim_number == claim_number)
        if policy_number:
            stmt = stmt.where(Policy.policy_number == policy_number)
        result = await self.session.execute(stmt)
        return list(result.all())
