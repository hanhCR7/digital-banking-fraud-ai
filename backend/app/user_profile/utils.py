from datetime import date

from fastapi import HTTPException, status

# Kiểm tra ngày hết hạn của giấy tờ tùy thân
# Đảm bảo ngày hết hạn phải lớn hơn ngày cấp
def validate_id_dates(issue_date: date, expiry_date: date) -> None:
    if expiry_date <= issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "ID expiry date must be after the issue date",
            },
        )