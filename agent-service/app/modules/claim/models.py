from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, UpdateAtMixin


class Claim(Base, UpdateAtMixin):
    """理赔申请"""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("products.id"))
    policy_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("policies.id"))
    claim_type: Mapped[str] = mapped_column(String(50))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="submitted")
    claim_number: Mapped[str | None] = mapped_column(String(60))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
