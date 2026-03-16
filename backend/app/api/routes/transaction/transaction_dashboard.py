from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select, func, desc

from backend.app.core.db import get_session
from backend.app.transaction.models import Transaction
from backend.app.api.routes.auth.deps import get_current_user
from backend.app.api.services.security import require_role
from backend.app.role.schema import RoleChoicesSchema

router = APIRouter(
    prefix="/transaction",
    tags=["Transaction"]
)

@router.get("/transaction-dashboard", dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))])
async def get_transactions_dashboard(
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=100),
    session: AsyncSession = Depends(get_session)
):
    offset = (page - 1) * limit # Tính toán offset dựa trên trang và giới hạn

    stmt = (
        select(Transaction)
        .order_by(desc(Transaction.created_at))
        .offset(offset)
        .limit(limit)
    )

    transactions = (await session.execute(stmt)).scalars().all()  # Lấy danh sách giao dịch theo trang và giới hạn

    total = await session.scalar(
        select(func.count())
        .select_from(Transaction)
    )# Lấy tổng số giao dịch để trả về cùng với dữ liệu phân trang

    return {
        "items": [
            {
                "id": t.id,
                "user": t.reference,
                "amount": t.amount,
                "channel": t.transaction_type,
                "status": t.status,
                "created_at": t.created_at,
            }
            for t in transactions
        ],
        "total": total,
    }
@router.get("/metrics", dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))])
async def get_dashboard_metrics(
    session: AsyncSession = Depends(get_session),
):
    total_transactions = await session.scalar(select(func.count(col(Transaction.id))))# Lấy tổng số giao dịch
    suspicious_transactions = await session.scalar(
        select(func.count(col(Transaction.id))).where(
            col(Transaction.ai_review_status).is_not(None)
        )
    )# Lấy số giao dịch bị nghi ngờ (có trạng thái đánh giá AI khác null)
    total_amount = await session.scalar(
        select(func.coalesce(func.sum(col(Transaction.amount)), 0))
    )# Lấy tổng số tiền giao dịch, sử dụng coalesce để trả về 0 nếu không có giao dịch nào

    total_transactions_value = total_transactions or 0
    suspicious_transactions_value = suspicious_transactions or 0
    total_amount_value = total_amount or 0

    fraud_rate = (
        suspicious_transactions_value / total_transactions_value * 100
        if total_transactions_value
        else 0
    )# Tính tỷ lệ gian lận, tránh chia cho 0 bằng cách kiểm tra tổng số giao dịch trước khi tính toán tỷ lệ

    return {
        "total_transactions": total_transactions_value,
        "suspicious_transactions": suspicious_transactions_value,
        "fraud_rate": round(fraud_rate, 2),
        "total_amount": int(total_amount_value),
    }

@router.get("/charts", dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))])
async def get_dashboard_charts(
    session: AsyncSession = Depends(get_session)
):
    # Transaction trend (7 ngày gần nhất)
    trend_stmt = (
        select(
            cast(col(Transaction.created_at), Date).label("date"),
            func.count(col(Transaction.id)).label("total"),
            func.count(col(Transaction.ai_review_status)).label("fraud"),
        )
        .group_by(cast(col(Transaction.created_at), Date))
        .order_by(cast(col(Transaction.created_at), Date).desc())
        .limit(7)
    )

    trend_rows = (await session.execute(trend_stmt)).mappings().all()
    # Lấy dữ liệu xu hướng giao dịch, 
    # sử dụng mappings() để trả về kết quả dưới dạng dictionary 
    # thay vì tuple và sau đó đảo ngược thứ tự để 
    # hiển thị từ ngày cũ nhất đến ngày mới nhất trên biểu đồ

    transaction_trend = [
        {
            "date": r["date"],
            "total": r["total"],
            "fraud": r["fraud"],
        }
        for r in reversed(trend_rows)
    ]

    # Fraud by risk level (JSONB)
    risk_level_expr = col(Transaction.transaction_metadata)["risk_level"].astext# Truy cập trường risk_level trong transaction_metadata (kiểu JSONB) và chuyển nó thành text để có thể nhóm và đếm số lượng giao dịch theo mức độ rủi ro.
    risk_stmt = (
        select(
            risk_level_expr.label("risk"),
            func.count().label("count"),
        )
        .where(col(Transaction.ai_review_status).is_not(None))
        .group_by(risk_level_expr)
    )

    risk_rows = await session.execute(risk_stmt)

    fraud_by_risk_level = {row.risk: row.count for row in risk_rows if row.risk is not None}

    return {
        "transaction_trend": transaction_trend,
        "fraud_by_risk_level": fraud_by_risk_level,
    }