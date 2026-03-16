from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import get_user_risk_history, get_all_risk_history_service
from backend.app.role.schema import RoleChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import (
    PaginatedHistoryResponseSchema,
    RiskHistoryItemSchema,
    RiskHistoryParams,
    RiskHistoryAllUserParams
)
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

logger = get_logger()
router = APIRouter(prefix="/transaction", tags=["Transaction"])


def get_risk_history_params(
    start_date: datetime | None = Query(
        default=None,
        description="Lọc lịch sử rủi ro bắt đầu từ ngày này",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="Lọc lịch sử rủi ro đến ngày này",
    ),
    min_risk_score: float | None = Query(
        default=None,
        ge=0,
        le=1,
        description="Ngưỡng điểm rủi ro tối thiểu",
    ),
    user_id: str | None = Query(
        default=None,
        description="ID người dùng mục tiêu",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Trang hiện tại (bắt đầu từ 1)",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Số bản ghi mỗi trang",
    ),
) -> RiskHistoryParams:
    # Chuẩn hóa pagination
    skip = (page - 1) * limit

    # Chuẩn hóa date (quan trọng)
    if start_date:
        start_date = start_date.replace(hour=0, minute=0, second=0)

    if end_date:
        end_date = end_date.replace(hour=23, minute=59, second=59)

    return RiskHistoryParams(
        start_date=start_date,
        end_date=end_date,
        min_risk_score=min_risk_score,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )

def get_risk_history_all_user_params(
    start_date: datetime | None = Query(
        default=None,
        description="Lọc lịch sử rủi ro bắt đầu từ ngày này",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="Lọc lịch sử rủi ro đến ngày này",
    ),
    min_risk_score: float | None = Query(
        default=None,
        ge=0,
        le=1,
        description="Ngưỡng điểm rủi ro tối thiểu",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Trang hiện tại (bắt đầu từ 1)",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Số bản ghi mỗi trang",
    ),
) -> RiskHistoryAllUserParams:
    # Chuẩn hóa pagination
    skip = (page - 1) * limit

    # Chuẩn hóa date (quan trọng)
    if start_date:
        start_date = start_date.replace(hour=0, minute=0, second=0)

    if end_date:
        end_date = end_date.replace(hour=23, minute=59, second=59)

    return RiskHistoryAllUserParams(
        start_date=start_date,
        end_date=end_date,
        min_risk_score=min_risk_score,
        skip=skip,
        limit=limit,
    )
@router.get(
    "/risk-history",
    response_model=PaginatedHistoryResponseSchema,
    status_code=status.HTTP_200_OK,
    description=(
        "Lấy lịch sử phân tích rủi ro giao dịch có phân trang. "
        "Chỉ dành cho nhân viên quản lý tài khoản."
    ),
)
async def get_risk_history(
    current_user = Depends(require_permission(PermissionChoicesSchema.VIEW_RISK_HISTORY)),
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
        # Xác định user cần truy vấn
        if params.user_id:
            try:
                target_user_id = UUID(params.user_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "ID người dùng không hợp lệ",
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
        logger.error(f"Lỗi khi lấy lịch sử phân tích rủi ro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi khi lấy lịch sử phân tích rủi ro.",
                "action": "Vui lòng thử lại sau.",
            },
        )

@router.get(
    "/risk-history/all-user",
    response_model=PaginatedHistoryResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def get_risk_history_all_user(
    params: RiskHistoryAllUserParams = Depends(get_risk_history_all_user_params),
    session: AsyncSession = Depends(get_session),
) -> PaginatedHistoryResponseSchema:
    try: 
        # Gọi service lấy dữ liệu lịch sử rủi ro
        history_dicts, total_count = await get_all_risk_history_service(
            start_date=params.start_date,
            end_date=params.end_date,
            min_risk_score=params.min_risk_score,
            skip=params.skip,
            limit=params.limit,
            session=session
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
        logger.error(f"Lỗi khi lấy lịch sử phân tích rủi ro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi khi lấy lịch sử phân tích rủi ro.",
                "action": "Vui lòng thử lại sau.",
            },
        )