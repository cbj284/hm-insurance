import json
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from langchain.tools import ToolRuntime, tool
from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from app.agents.schemas import InsuranceAgentContext
from app.infra.database import AsyncSessionFactory
from app.modules.insurance_plan.schemas import InsurancePlanCreate
from app.modules.insurance_plan.service import InsurancePlanService
from app.modules.product.models import Product
from app.modules.product.service import ProductService


@tool
async def query_product_clause(
        query: str,
        k: int,
        product_id: int,
) -> str:
    """查询指定保险产品的条款内容。

    Args:
        query: 需要从保险条款中查询的问题。
        k: 返回的文档数量。
        product_id: 保险产品ID。
    """
    from app.rag import retriever

    chunks = await retriever.retrieve(query, k, product_id)
    if not chunks:
        return "没有查询到相关保险条款。"

    sources = {
        f"ref-{i:03d}": {
            "product_id": chunk.product_id,
            "clause_name": chunk.clause_name,
            "section_path": chunk.section_path,
            "content": chunk.content,
        }
        for i, chunk in enumerate(chunks, start=1)
    }

    writer = get_stream_writer()
    writer({"type": "additional_info", "data": sources})

    return json.dumps(sources, ensure_ascii=False)
@tool
async def query_candidate_products(
    categories: list[str],
    premium_min: Decimal | None = None,
    limit_per_category: int = 5
):
    """
    根据险种和保费条件查询可用于推荐的候选保险产品。当用户咨询具体保险产品或需要保险产品推荐时使用。

    Args:
        categories: 产品分类列表，可选值为 medical、critical_illness、life、accident。
        premium_min: 最低保费上限，可选参数，只返回最低保费小于该值的产品。
        limit_per_category: 每个险种最多返回的产品数量，可选参数，默认5。
    """

    async with AsyncSessionFactory() as session:
        # 1.初始化Service
        service = ProductService(session)
        # 2.调用Service，得到候选产品
        products: list[Product] = await service.list_candidates(
            categories,
            premium_min,
            limit_per_category
        )
        # 3.返回给AI，最好把Product处理成json返回
        return jsonable_encoder(products)


@tool
async def save_insurance_plan(
    plan: InsurancePlanCreate,
    runtime: ToolRuntime[InsuranceAgentContext],
) -> dict[str, str]:
    """请用户确认后，保存当前保险推荐方案。"""

    decision = interrupt(
        {
            "plan": plan.model_dump(mode="json"),
            "confirm_info": "是否确认保存这份保险推荐方案？",
            "action": ["approve", "reject"],
        }
    )
    if decision.get("action") != "approve":
        return {
            "message": f"用户取消保存保险方案, 原因:{decision.get('reject_reason')}"
        }

    async with AsyncSessionFactory() as session:
        service = InsurancePlanService(session)
        plan_id = await service.create_plan(
            user_id=runtime.context.user_id,
            data=plan,
        )

    return {
        "plan_id": str(plan_id),
        "message": "保险方案保存成功",
    }
