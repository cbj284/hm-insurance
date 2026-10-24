from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ProductResponse(BaseModel):
    """保险产品响应结果"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    clause_name: str
    category: str
    insurer: str
    image_url: str | None = None
    description: str | None = None
    min_premium: Decimal | None
    max_premium: Decimal | None
    target_group: str | None
    highlights: list[str] = Field(default_factory=list)
    status: str


class ProductPage(BaseModel):
    """保险产品分页结果"""

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int