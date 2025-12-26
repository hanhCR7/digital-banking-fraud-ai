from jinja2 import Environment, FileSystemLoader
from backend.app.core.emails.config import TEMPLATES_DIR
from backend.app.core.tasks.email import send_email_task
from backend.app.core.logging import get_logger

logger = get_logger()

# Khởi tạo môi trường Jinja2 để render email template
# - Load template từ thư mục TEMPLATES_DIR
# - Bật autoescape để tránh lỗi XSS trong email HTML
email_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True
)

class EmailTemplate:
    template_name: str
    template_name_plain: str
    subject: str

    @classmethod
    async def send_email(
        cls, email_to: str | list[str], context: dict, subject_override: str | None = None
    ) -> None:
        try:
            # Chuẩn hóa email người nhận về dạng danh sách
            # Cho phép truyền vào 1 email hoặc nhiều email
            recipients_list = [email_to] if isinstance(email_to, str) else email_to
            # Đảm bảo cả template HTML và plain text đều được khai báo
            # Theo best practice khi gửi email
            if not cls.template_name or not cls.template_name_plain:
                raise ValueError(
                    "Both HTML and plain text email templates are required"
                )
            # Load template HTML và plain text
            html_template = email_env.get_template(cls.template_name)
            plain_template = email_env.get_template(cls.template_name_plain)
            # Render nội dung email từ template và context
            html_content = html_template.render(**context)
            plain_content = plain_template.render(**context)
            # Đưa tác vụ gửi email vào Celery
            # Việc gửi email sẽ chạy ở background, không block request chính
            task = send_email_task.delay(
                recipients=recipients_list,
                subject=subject_override or cls.subject,
                html_content=html_content,
                plain_content=plain_content,
            )
            # Ghi log khi tác vụ gửi email được đưa vào hàng đợi thành công
            logger.info(
                logger.info(f"Email task {task.id} queued for: {recipients_list}")
            )
        except Exception as e:
            logger.error(
                f"Failed to queue email task for {recipients_list}: Error: {str(e)}"
            )
            raise