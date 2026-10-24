from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.modules.product.schemas import ProductPage, ProductResponse
from app.modules.product.service import ProductService

router = APIRouter(prefix="/api/v1/products", tags=["products"])


async def get_product_service(
    session: AsyncSession = Depends(get_session),
) -> ProductService:
    return ProductService(session)


@router.get("", response_model=ProductPage)
async def list_products(
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=6, ge=1, le=50),
    service: ProductService = Depends(get_product_service),
) -> ProductPage:
    return await service.list_products(category, page, page_size)


@router.get("/candidates", response_model=list[ProductResponse])
async def list_candidates(
    categories: list[str] = Query(min_length=1),
    premium_min: Decimal | None = Query(default=None, gt=0),
    limit_per_category: int = Query(default=5, ge=1, le=10),
    service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    return await service.list_candidates(
        categories=categories,
        premium_min=premium_min,
        limit_per_category=limit_per_category,
    )
