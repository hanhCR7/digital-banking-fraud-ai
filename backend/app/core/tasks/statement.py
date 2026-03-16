from datetime import datetime, timedelta
from io import BytesIO

from celery import Task
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

# Celery task dùng để sinh file PDF sao kê tài khoản

class StatementGenerationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Ghi log khi task thất bại
        logger.error(f"Sinh sao kê thất bại: {exc}", exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    base=StatementGenerationTask,
    name="generate_statement_pdf",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
)
def generate_statement_pdf(self, statement_data: dict, statement_id: str) -> dict:
    """Sinh file PDF sao kê và lưu tạm thời vào Redis."""
    try:
        # Khởi tạo buffer và cấu hình trang PDF
        buffer = BytesIO()
        PAGE_WIDTH = A4[0]
        MARGIN = 72
        USABLE_WIDTH = PAGE_WIDTH - (2 * MARGIN)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=MARGIN,
            leftMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
        )

        # Khởi tạo style cho PDF
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="SmallText", parent=styles["Normal"], fontSize=8))
        styles.add(
            ParagraphStyle(
                name="AccountInfo", parent=styles["Normal"], fontSize=10, spaceAfter=6
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading3"],
                fontSize=12,
                spaceAfter=6,
                alignment=1,
            )
        )

        elements = []

        # Tiêu đề sao kê
        elements.append(
            Paragraph(f"Sao kê tài khoản {settings.SITE_NAME}", styles["Heading1"])
        )
        elements.append(Spacer(1, 12))

        # Thời gian sao kê
        elements.append(
            Paragraph(
                f"Thời gian sao kê: {statement_data['start_date']} đến {statement_data['end_date']}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 12))

        user = statement_data["user"]
        account = user["accounts"][0]

        # Thông tin khách hàng & tài khoản
        user_info = [
            [Paragraph("Thông tin khách hàng:", styles["Heading4"]), ""],
            ["Họ tên:", user["full_name"]],
            ["Tên đăng nhập:", user["username"]],
            ["Email:", user["email"]],
        ]

        account_info = [
            [Paragraph("Thông tin tài khoản:", styles["Heading4"]), ""],
            ["Số tài khoản:", account["account_number"]],
            ["Tên tài khoản:", account["account_name"]],
            ["Loại tài khoản:", account["account_type"]],
            ["Loại tiền tệ:", account["currency"]],
            ["Số dư hiện tại:", str(account["balance"])],
        ]

        # Hiển thị bảng thông tin khách hàng + tài khoản
        col_width = USABLE_WIDTH / 2
        user_table = Table(user_info, colWidths=[col_width * 0.4, col_width * 0.6])
        account_table = Table(account_info, colWidths=[col_width * 0.4, col_width * 0.6])

        table_style = TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("SPAN", (0, 0), (1, 0)),
            ]
        )

        user_table.setStyle(table_style)
        account_table.setStyle(table_style)

        elements.append(
            Table(
                [[user_table, account_table]],
                colWidths=[col_width, col_width],
                spaceBefore=10,
                spaceAfter=10,
            )
        )

        elements.append(Spacer(1, 20))

        # Bảng lịch sử giao dịch
        transactions = statement_data["transactions"]
        if transactions:
            elements.append(Paragraph("Lịch sử giao dịch", styles["SectionTitle"]))
            elements.append(Spacer(1, 12))

            table_data = [
                ["Ngày", "Mã tham chiếu", "Nội dung", "Loại", "Số tiền", "Số dư"]
            ]

            for txn in transactions:
                amount_str = (
                    f"+{txn['amount']}"
                    if txn["transaction_category"] == "credit"
                    else f"-{txn['amount']}"
                )
                description = (
                    txn["description"][:30] + "..."
                    if len(txn["description"]) > 30
                    else txn["description"]
                )
                table_data.append(
                    [
                        txn["created_at"],
                        txn["reference"],
                        description,
                        txn["transaction_type"],
                        amount_str,
                        txn["balance_after"],
                    ]
                )

            trans_table = Table(
                table_data,
                colWidths=[USABLE_WIDTH * r for r in [0.12, 0.20, 0.30, 0.15, 0.11, 0.12]],
                repeatRows=1,
            )

            trans_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ]
                )
            )
            elements.append(trans_table)
        else:
            elements.append(
                Paragraph("Không có giao dịch nào trong khoảng thời gian này.", styles["Normal"])
            )

        # Chân trang
        elements.append(Spacer(1, 12))
        elements.append(
            Paragraph(
                f"Thời gian tạo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["SmallText"],
            )
        )
        elements.append(
            Paragraph(
                "Đây là sao kê được tạo tự động bằng hệ thống và không cần chữ ký.",
                styles["SmallText"],
            )
        )

        # Tạo file PDF
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        # Lưu file PDF tạm thời vào Redis
        redis_client = celery_app.backend.client
        redis_client.setex(f"statement:{statement_id}", 3600, pdf_data)

        return {
            "trạng_thái": "thành_công",
            "statement_id": statement_id,
            "thời_gian_tạo": datetime.now().isoformat(),
            "hết_hạn_lúc": (datetime.now() + timedelta(hours=1)).isoformat(),
        }

    except Exception as e:
        # Thử lại task khi xảy ra lỗi
        logger.error(f"Không thể sinh sao kê: {e}")
        raise self.retry(exc=e, countdown=5)
