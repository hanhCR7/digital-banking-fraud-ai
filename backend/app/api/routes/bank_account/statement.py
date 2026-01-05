from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import generate_user_statement
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.core.celery_app import celery_app
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import (
    StatementRequestSchema,
    StatementResponseSchema,
)

logger = get_logger()
router = APIRouter(prefix="/bank-account", tags=["Bank Account"])

@router.post(
    "/statement/generate",
    response_model=StatementResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_statement(
    request: StatementRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> StatementResponseSchema:
    # API khởi tạo yêu cầu tạo sao kê (statement) bất đồng bộ bằng Celery
    try:
        # Kiểm tra ngày bắt đầu phải trước ngày kết thúc
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Start date must be before end date",
                },
            )

        # Nếu người dùng yêu cầu sao kê cho một tài khoản cụ thể
        if request.account_number:
            # Kiểm tra tài khoản tồn tại và thuộc về người dùng hiện tại
            account_query = select(BankAccount).where(
                BankAccount.account_number == request.account_number,
                BankAccount.user_id == current_user.id,
            )
            result = await session.exec(account_query)
            account = result.first()

            # Tài khoản không tồn tại hoặc không thuộc quyền sở hữu
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "status": "error",
                        "message": "Account not found or doed not belong to you",
                    },
                )

            # Không cho phép tạo sao kê cho tài khoản không hoạt động
            if account.account_status != AccountStatusEnum.Active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Cannot generate statement for inactive account",
                    },
                )

        # Gọi service tạo sao kê và đẩy task xử lý sang Celery
        result = await generate_user_statement(
            user_id=current_user.id,
            start_date=request.start_date,
            end_date=request.end_date,
            session=session,
            account_number=request.account_number,
        )

        # Khởi tạo AsyncResult để đảm bảo task Celery được register
        celery_app.AsyncResult(result["task_id"])

        # Thời gian tạo sao kê và thời gian hết hạn tải file
        generated_at = datetime.now(timezone.utc)
        expires_at = generated_at + timedelta(hours=1)

        # Trả về thông tin task để client theo dõi trạng thái xử lý
        return StatementResponseSchema(
            status="pending",
            message="Statement generation initiated",
            task_id=result["task_id"],
            statement_id=result["statement_id"],
            generated_at=generated_at,
            expires_at=expires_at,
        )

    except ValueError as e:
        # Bắt lỗi validate nghiệp vụ phát sinh từ service layer
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            },
        )

    except HTTPException as http_ex:
        # Ném lại các lỗi HTTP đã được xử lý trước đó
        raise http_ex

    except Exception as e:
        # Lỗi hệ thống không xác định
        logger.error(f"Failed to generate statement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to generate statement",
                "action": "Please try again later",
            },
        )


@router.get("/statement/{statement_id}")
async def get_statement(statement_id: str) -> Response:
    # API tải file sao kê PDF từ Redis theo statement_id
    try:
        # Sử dụng Redis backend của Celery để truy xuất file PDF
        redis_client = celery_app.backend.client

        # Lấy dữ liệu PDF đã được lưu tạm trong Redis
        pdf_data = redis_client.get(f"statement:{statement_id}")

        # File không tồn tại hoặc đã hết hạn
        if not pdf_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Statement not found or has expired",
                },
            )

        # Trả về file PDF dưới dạng attachment để người dùng tải xuống
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment;filename=statement_{statement_id}.pdf"
            },
        )

    except HTTPException:
        # Ném lại lỗi HTTP
        raise

    except Exception as e:
        # Lỗi khi truy xuất hoặc trả file sao kê
        logger.error(f"Failed to retrieve statement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to retrieve statement"},
        )
