from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import get_user_risk_history
from backend.app.auth.schema import RoleChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import (
    PaginatedHistoryResponseSchema,
    RiskHistoryItemSchema,
    RiskHistoryParams,
)

logger = get_logger()
router = APIRouter(prefix="/transaction", tags=["Transaction"])


def get_risk_history_params(
    start_date: datetime | None = Query(
        default=None,
        description="Filter risk history starting from this date",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="Filter risk history until this date",
    ),
    min_risk_score: float | None = Query(
        default=None,
        ge=0,
        le=1,
        description="Minimum risk score threshold",
    ),
    user_id: str | None = Query(
        default=None,
        description="Target user ID (only for account executives)",
    ),
    skip: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records to return",
    ),
) -> RiskHistoryParams:
    """
    Parse và gom các query parameter dùng để lọc lịch sử phân tích rủi ro.
    """
    return RiskHistoryParams(
        start_date=start_date,
        end_date=end_date,
        min_risk_score=min_risk_score,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/risk-history",
    response_model=PaginatedHistoryResponseSchema,
    status_code=status.HTTP_200_OK,
    description=(
        "Retrieve paginated transaction risk analysis history. "
        "Only accessible to account executives."
    ),
)
async def get_risk_history(
    current_user: CurrentUser,
    params: RiskHistoryParams = Depends(get_risk_history_params),
    session: AsyncSession = Depends(get_session),
) -> PaginatedHistoryResponseSchema:
    """
    API cho phép Account Executive xem lịch sử phân tích rủi ro giao dịch.

    Chức năng:
    - Kiểm tra quyền truy cập
    - Hỗ trợ lọc theo thời gian, user, và risk score
    - Trả về dữ liệu phân trang
    """
    try:
        # Chỉ Account Executive mới được phép truy cập
        if current_user.role != RoleChoicesSchema.ACCOUNT_EXECUTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "message": "Only account executives can view transaction risk history",
                },
            )

        # Xác định user cần truy vấn
        if params.user_id:
            try:
                target_user_id = UUID(params.user_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid user ID format",
                    },
                )
        else:
            target_user_id = current_user.id

        # Gọi service lấy dữ liệu lịch sử rủi ro
        history_dicts, total_count = await get_user_risk_history(
            user_id=target_user_id,
            start_date=params.start_date,
            end_date=params.end_date,
            min_risk_score=params.min_risk_score,
            skip=params.skip,
            limit=params.limit,
            session=session,
        )

        # Chuyển dữ liệu thô sang schema response
        history_items = [
            RiskHistoryItemSchema.model_validate(item)
            for item in history_dicts
        ]

        return PaginatedHistoryResponseSchema(
            total=total_count,
            skip=params.skip,
            limit=params.limit,
            items=history_items,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get risk history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to retrieve risk history",
                "action": "Please try again later",
            },
        )
