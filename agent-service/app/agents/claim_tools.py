from datetime import datetime

from fastapi.encoders import jsonable_encoder
from langchain.tools import ToolRuntime, tool
from langgraph.config import get_stream_writer

from app.agents.schemas import InsuranceAgentContext
from app.infra.database import AsyncSessionFactory
from app.modules.claim.models import Claim
from app.modules.claim.repository import ClaimRepository
from app.modules.policy.models import Policy
from app.modules.policy.repository import PolicyRepository
from app.modules.product.models import Product

CLAIM_STATUS_LABEL = {
    "submitted": "已提交",
    "reviewing": "审核中",
    "approved": "已通过",
    "rejected": "已拒赔",
    "paid": "已赔付",
}

POLICY_STATUS_LABEL = {
    "pending": "待生效",
    "active": "保障中",
    "expired": "已过期",
    "terminated": "已终止",
}

CLAIM_TYPE_LABEL = {
    "medical": "医疗",
    "accident": "意外",
    "critical_illness": "重疾",
    "life": "寿险",
}

CLAIM_GUIDES = {
    "medical": (
        "住院医疗理赔一般需要：理赔申请书、身份证、银行卡、诊断证明、出院小结、费用清单和发票。"
        "先向医院开齐材料，再向承保公司提交；审核周期常见 5-15 个工作日。"
    ),
    "accident": (
        "意外医疗/伤残理赔一般需要：理赔申请书、身份证、事故说明、门急诊病历或鉴定报告、费用票据。"
        "若涉及交通事故，还需交警事故认定书。"
    ),
    "critical_illness": (
        "重疾理赔一般需要：理赔申请书、身份证、保单号、专科医生诊断证明、病理或影像学检查报告。"
        "以条款疾病定义为准，确诊后尽快报案。"
    ),
    "life": (
        "身故理赔一般需要：理赔申请书、被保人死亡证明、关系证明、受益人身份证件和保单。"
        "复杂案件建议转人工协助。"
    ),
    "general": (
        "理赔常见步骤：1. 出险后尽快报案；2. 按险种准备申请书和证明材料；"
        "3. 提交承保公司审核；4. 关注审核进度，补充材料后重新审核。"
        "下载申请书可使用链接 {{download_url}}。"
    ),
}


def _format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_policy(policy: Policy, product: Product | None) -> dict:
    return {
        "id": str(policy.id),
        "user_id": policy.user_id,
        "product_id": policy.product_id,
        "policy_number": policy.policy_number,
        "status": policy.status,
        "effective_at": _format_dt(policy.effective_at),
        "expires_at": _format_dt(policy.expires_at),
        "application_no": policy.application_no,
        "holder_name": policy.holder_name,
        "insured_name": policy.insured_name,
        "insured_phone": policy.insured_phone,
        "insured_id_no_masked": policy.insured_id_no_masked,
        "coverage_amount": policy.coverage_amount,
        "premium_amount": policy.premium_amount,
        "payment_frequency": policy.payment_frequency,
        "policy_snapshot": policy.policy_snapshot,
        "coverage_snapshot": policy.coverage_snapshot,
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "image_url": product.image_url,
            "insurer": product.insurer,
        }
        if product
        else None,
    }


def serialize_claim(
    claim: Claim,
    policy: Policy | None,
    product: Product | None,
) -> dict:
    return {
        "id": str(claim.id),
        "claim_number": claim.claim_number,
        "claim_type": claim.claim_type,
        "claim_type_label": CLAIM_TYPE_LABEL.get(claim.claim_type, claim.claim_type),
        "amount": claim.amount,
        "description": claim.description,
        "status": claim.status,
        "status_label": CLAIM_STATUS_LABEL.get(claim.status, claim.status),
        "submitted_at": _format_dt(claim.submitted_at),
        "updated_at": _format_dt(claim.updated_at),
        "policy_number": policy.policy_number if policy else None,
        "product_name": product.name if product else None,
        "product_id": claim.product_id,
    }


@tool
async def query_user_policies(
    runtime: ToolRuntime[InsuranceAgentContext],
    policy_number: str | None = None,
) -> list[dict]:
    """查询当前用户的保单列表或指定保单。用户询问我的保单、保障期间、保单号时使用。

    Args:
        policy_number: 可选，精确匹配保单号。
    """
    async with AsyncSessionFactory() as session:
        repository = PolicyRepository(session)
        if policy_number:
            row = await repository.find_by_number(runtime.context.user_id, policy_number)
            rows = [row] if row else []
        else:
            rows = await repository.list_by_user(runtime.context.user_id)

    policies = [serialize_policy(policy, product) for policy, product in rows]
    writer = get_stream_writer()
    writer({"type": "additional_info", "data": {"policies": policies}})
    if not policies:
        return []
    return jsonable_encoder(policies)


@tool
async def query_claim_progress(
    runtime: ToolRuntime[InsuranceAgentContext],
    claim_number: str | None = None,
    policy_number: str | None = None,
) -> list[dict]:
    """查询当前用户的理赔进度。用户问理赔到哪一步、案件号、审核结果时使用。

    Args:
        claim_number: 可选，理赔案件号，如 CLM-DEMO-2026-0001。
        policy_number: 可选，按保单号筛选理赔记录。
    """
    async with AsyncSessionFactory() as session:
        repository = ClaimRepository(session)
        rows = await repository.list_by_user(
            runtime.context.user_id,
            claim_number=claim_number,
            policy_number=policy_number,
        )

    claims = [
        serialize_claim(claim, policy, product)
        for claim, policy, product in rows
    ]
    related_policies = []
    seen: set[str] = set()
    for claim, policy, product in rows:
        if policy and str(policy.id) not in seen:
            seen.add(str(policy.id))
            related_policies.append(serialize_policy(policy, product))
    if related_policies:
        writer = get_stream_writer()
        writer({"type": "additional_info", "data": {"policies": related_policies}})
    return jsonable_encoder(claims)


@tool
def query_claim_guide(claim_type: str | None = None) -> str:
    """说明理赔流程、所需材料和注意事项。用户问怎么报案、要准备什么材料时使用。

    Args:
        claim_type: 可选，medical / accident / critical_illness / life。
    """
    key = claim_type if claim_type in CLAIM_GUIDES else "general"
    return CLAIM_GUIDES[key]
