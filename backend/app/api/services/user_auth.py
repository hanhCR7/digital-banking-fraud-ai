import asyncio
import uuid
import jwt
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.auth.models import User
from backend.app.auth.schema import AccountStatusSchema, UserCreateSchema, ChangePasswordSchema, ChangeInitialPasswordSchema
from backend.app.role.schema import RoleChoicesSchema
from backend.app.auth.utils import (
    generate_username, generate_password_hash,
    create_activation_token, generate_otp, verify_password
)
from datetime import datetime, timedelta, timezone
from backend.app.core.services.activation_email import send_activation_email
from backend.app.core.services.login_otp import send_login_otp_email
from backend.app.core.services.account_lockout import send_account_lockout_email
from backend.app.api.services.user_role import user_role_service
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

class UserAuthService:
    async def get_user_by_email(
        self,
        email: str,
        session: AsyncSession,
        include_inactive: bool = False,#
    ) -> User | None:
        """Lấy thông tin user qua email"""
        # Tạo câu truy vấn lấy user theo email
        statement = select(User).where(User.email == email)
        # Nếu không cho phép lấy user inactive, chỉ lấy user active
        if not include_inactive:
            statement = statement.where(User.is_active)
        result = await session.exec(statement)# thực thi truy vấn
        user = result.first()
        return user
    async def get_user_by_id_no(
        self,
        id_no: str,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> User | None:
        """Lấy thông tin user qua số giấy tờ tùy thân (CCCD/CMND)"""
         # Tạo câu truy vấn lấy user theo id no
        statement = select(User).where(User.id_no == id_no)
        # Nếu không cho phép lấy user inactive, chỉ lấy user active
        if not include_inactive:
            statement = statement.where(User.is_active)
        result = await session.exec(statement)
        user = result.first()
        return user
    async def get_user_by_id(
        self,
        user_id: uuid.UUID,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> User | None:
        """Lấy thông tin user qua id"""
        # Tạo câu truy vấn lấy yusser theo id
        statement = select(User).where(User.id == user_id)
        # Nếu không cho phép lấy user inactive, chỉ lấy user active
        if not include_inactive:
            statement = statement.where(User.is_active)
        result = await session.exec(statement)
        user = result.first()
        return user
    
    async def check_user_email_exists(self, email: str , session: AsyncSession) -> bool:
        """Kiểm tra email đã tồn tại trong hệ thống hay chưa"""
        user = await self.get_user_by_email(email, session)
        return bool(user)
    async def check_user_id_no_exists(self, id_no: str, session: AsyncSession) -> bool:
        """Kiểm tra số giấy tờ tùy thân (CCCD/CMND) đã tồn tại trong hệ thống hay chưa"""
        user = await self.get_user_by_id_no(id_no, session)
        return bool(user)
    async def verify_user_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        """Xác minh mật khẩu người dùng"""
        return verify_password(plain_password, hashed_password)
    async def reset_user_state(
        self,
        user: User,
        session: AsyncSession,
        *,
        clear_otp: bool = True,
        log_action: bool = True,
    ) -> None:
        """
        Reset trạng thái bảo mật của người dùng sau khi xác thực thành công
        Thường được gọi khi:
        - Đăng nhập thành công
        - Xác minh OTP thành công
        - Mở khóa tài khoản
        """
        # Lưu lại trạng thái tài khoản trước khi thay đổi
        previous_status = user.account_status
        # Reset số lần đăng nhập sai
        user.failed_login_attempts = 0
        # Xóa thời điểm đăng nhập sai gần nhất
        user.last_failed_login = None
        # Nếu được phép, xóa OTP và thời hạn OTP
        if clear_otp:
            user.otp = ""
            user.otp_expiry_time = None
        # Nếu tài khoản đang bị khóa thì mở khóa lại
        if user.account_status == AccountStatusSchema.LOCKED:
            user.account_status = AccountStatusSchema.ACTIVE
        await session.commit()
        await session.refresh(user)
        # Ghi log nếu trạng thái tài khoản có thay đổi
        if log_action and previous_status != user.account_status:
            logger.info(
                f"Trạng thái tài khoản người dùng {user.email} đã được reset: "
                f"{previous_status} -> {user.account_status}"
            )
    async def validate_user_status(self, user: User) -> None:
        """Kiểm tra trạng thái tài khoản người dùng trước khi cho phép thao tác hệ thống"""
        # Kiểm tra tài khoản đã được kích hoạt hay chưa
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản của bạn chưa được kích hoạt",
                    "action": "Vui lòng kích hoạt tài khoản trước",
                },
            )
        # Kiểm tra tài khoản có đang bị khóa hay không
        if user.account_status == AccountStatusSchema.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản của bạn đã bị khóa",
                    "action": "Vui lòng liên hệ với bộ phận hỗ trợ",
                },
            )
        # Kiểm tra tài khoản có đang ở trạng thái inactive hay không
        if user.account_status == AccountStatusSchema.INACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Tài khoản của bạn chưa được kích hoạt",
                    "action": "Vui lòng kích hoạt tài khoản trước",
                },
            )
    async def generate_and_save_otp(
        self,
        user: User,
        session: AsyncSession,
    ) -> tuple[bool, str]:
        """Sinh mã OTP, lưu vào cơ sở dữ liệu và gửi OTP qua email cho người dùng"""
        try:
            # Sinh mã OTP ngẫu nhiên
            otp = generate_otp()
            # Lưu OTP vào đối tượng user
            user.otp = otp
            # Thiết lập thời gian hết hạn OTP
            user.otp_expiry_time = datetime.now(timezone.utc) + timedelta(
                minutes=settings.OTP_EXPIRATION_MINUTES
            )
            # Lưu OTP vào cơ sở dữ liệu
            await session.commit()
            await session.refresh(user)
            # Gửi email OTP tối đa 3 lần
            for attempt in range(3):
                try:
                    # Gửi OTP qua email
                    await send_login_otp_email(user.email, otp)
                    logger.info(f"Mã OTP đã được gửi đến {user.email} thành công")
                    # Gửi thành công
                    return True, otp
                except Exception as e:
                    logger.error(
                        f"Lỗi khi gửi mã OTP qua email (attempt {attempt + 1}): {e}"
                    )
                    # Nếu đã thử đủ 3 lần mà vẫn thất bại
                    if attempt == 2:
                        # Xóa OTP để tránh OTP tồn tại nhưng không được gửi
                        user.otp = ""
                        user.otp_expiry_time = None
                        await session.commit()
                        await session.refresh(user)
                        return False, ""
                    # Backoff: đợi tăng dần trước khi retry (1s, 2s, 4s)
                    await asyncio.sleep(2 ** attempt)
            return False, ""
        except Exception as e:
            logger.error(f"Lỗi khi tạo và lưu mã OTP: {e}")
            # Rollback trạng thái OTP khi có lỗi bất ngờ
            user.otp = ""
            user.otp_expiry_time = None
            await session.commit()
            await session.refresh(user)
            return False, ""
    async def create_user(
        self,
        user_data: UserCreateSchema,
        session: AsyncSession,
    ) -> User:
        """Tạo mới một tài khoản người dùng và gửi email kích hoạt tài khoản"""
        # Chuyển dữ liệu từ schema sang dict
        # Loại bỏ các trường không cần lưu vào DB
        user_data_dict = user_data.model_dump(
            exclude={
                "confirm_password",   # Chỉ dùng để validate, không lưu DB
                "username",           # Sẽ tự sinh username
                "is_active",          # Mặc định chưa kích hoạt
                "account_status",     # Trạng thái sẽ được set thủ công
            }
        )
        # Tách mật khẩu ra để mã hóa
        password = user_data_dict.pop("password")
        # Tạo đối tượng User mới
        new_user = User(
            username=generate_username(),                # Sinh username tự động
            hashed_password=generate_password_hash(password),  # Mã hóa mật khẩu
            is_active=False,                              # Chưa kích hoạt
            account_status=AccountStatusSchema.PENDING,   # Chờ kích hoạt
            **user_data_dict,
        )
        # Thêm user vào session
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        # Tạo token kích hoạt tài khoản
        activation_token = create_activation_token(new_user.id)
        try:
            # Gửi email kích hoạt tài khoản cho người dùng
            await send_activation_email(new_user.email, activation_token)
            logger.info(f"Email kích hoạt tài khoản đã được gửi đến {new_user.email}")
        except Exception as e:
            # Log lỗi nếu gửi email thất bại
            logger.error(f"Lỗi khi gửi email kích hoạt tài khoản đến {new_user.email}: {e}")
            # Ném exception để tầng trên xử lý (rollback, thông báo client, ...)
            raise
        return new_user
    async def activate_user_account(
            self,
            token: str,
            session: AsyncSession,
        ) -> User:
        """Kích hoạt tài khoản người dùng thông qua activation token"""
        try:
            # Giải mã JWT token
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            # Kiểm tra loại token có đúng là token kích hoạt không
            if payload.get("type") != "activation":
                raise ValueError("Loại token không hợp lệ")
            user_id = uuid.UUID(payload["id"])
            # Lấy user kể cả khi chưa active
            user = await self.get_user_by_id(
                user_id,
                session,
                include_inactive=True
            )
            # Không tìm thấy user
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "status": "error",
                        "message": "Không tìm thấy người dùng",
                    },
                )
            # Tài khoản đã được kích hoạt trước đó
            if user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Tài khoản đã được kích hoạt trước đó",
                    },
                )
            # Reset trạng thái bảo mật (OTP, failed login, mở khóa nếu có)
            await self.reset_user_state(
                user,
                session,
                clear_otp=True,
                log_action=True
            )
            # Kích hoạt tài khoản
            user.is_active = True
            user.account_status = AccountStatusSchema.ACTIVE
            await user_role_service.assign_role_to_user(
                session=session,
                user_id=user.id,
                role=RoleChoicesSchema.CUSTOMER
            )
            # Lưu thay đổi vào CSDL
            await session.commit()
            await session.refresh(user)
            return user
        # Token hết hạn
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Token kích hoạt đã hết hạn",
                },
            )
        # Token không hợp lệ
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Token kích hoạt không hợp lệ",
                },
            )
        # Re-raise các HTTPException đã được định nghĩa
        except HTTPException as http_ex:
            raise http_ex
        # Lỗi không xác định
        except Exception as e:
            logger.error(f"Lỗi khi kích hoạt tài khoản: {e}")
            raise
    async def verify_login_otp(
        self,
        email: str,
        otp: str,
        session: AsyncSession,
    ) -> User:
        """ Xác thực OTP đăng nhập cho người dùng."""
        try:
            user = await self.get_user_by_email(email, session)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "status": "error",
                        "message": "Tài khoản không hợp lệ",
                    },
                )
            # Kiểm tra trạng thái tài khoản
            await self.validate_user_status(user)
            # Kiểm tra người dùng có đang bị khóa tạm thời do đăng nhập sai nhiều lần hay không
            await self.check_user_lockout(user, session)
            # OTP không tồn tại hoặc không khớp
            if not user.otp or user.otp != otp:
                 # Tăng số lần đăng nhập sai
                await self.increment_failed_login_attempts(user, session)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Mã OTP không hợp lệ",
                        "action": "Vui lòng kiểm tra lại mã OTP và thử lại",
                    },
                )
            # Kiểm tra thời hạn của OTP
            if user.otp_expiry_time is None or user.otp_expiry_time < datetime.now(
                timezone.utc
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Mã OTP đã hết hạn.",
                        "action": "Vui lòng yêu cầu mã OTP mới.",
                    },
                )
            # Reset trạng thái đăng nhập thất bại, giữ lại OTP nếu cần xử lý bước tiếp theo
            await self.reset_user_state(user, session, clear_otp=False)
            return user
        # Ném lại các lỗi HTTP đã được xử lý trước đó
        except HTTPException as http_ex:
            raise http_ex
        except Exception as e:
            logger.error(f"Lỗi khi xác thực mã OTP: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "message": "Lỗi khi xác thực mã OTP.",
                    "action": "Vui lòng thử lại sau.",
                },
            )
    async def check_user_lockout(
        self,
        user: User,
        session: AsyncSession,
    ) -> None:
        """Kiểm tra trạng thái khóa tài khoản do đăng nhập sai nhiều lần."""
        # Nếu tài khoản không bị khóa thì bỏ qua kiểm tra lockout
        if user.account_status != AccountStatusSchema.LOCKED:
            return
        # Không có thời điểm đăng nhập sai cuối cùng → không thể xác định lockout
        if user.last_failed_login is None:
            return
        # Thời điểm kết thúc khóa tài khoản
        lockout_time = user.last_failed_login + timedelta(
            minutes=settings.LOCKOUT_DURATION_MINUTES
        )
        current_time = datetime.now(timezone.utc)
        # Nếu đã hết thời gian khóa → tự động mở khóa tài khoản
        if current_time >= lockout_time:
            await self.reset_user_state(user, session, clear_otp=False)
            logger.info(f"Thời gian khóa tài khoản đã kết thúc cho người dùng {user.email}")
            return
        # Tính số phút còn lại trước khi có thể đăng nhập lại
        remaining_minutes = int((lockout_time - current_time).total_seconds() / 60)
        logger.warning(f"Phát hiện nỗ lực đăng nhập vào tài khoản đã bị khóa: {user.email}")
        # Từ chối đăng nhập khi tài khoản vẫn đang bị khóa
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Tài khoản của bạn đã bị khóa tạm thời",
                "action": f"Vui lòng thử lại sau {remaining_minutes} phút",
                "lockout_remaining_minutes": remaining_minutes,
            },
        )

    async def increment_failed_login_attempts(
        self,
        user: User,
        session: AsyncSession,
    ) -> None:
        """Tăng số lần đăng nhập thất bại của người dùng."""
        user.failed_login_attempts += 1
        # Ghi nhận thời điểm đăng nhập sai gần nhất
        current_time = datetime.now(timezone.utc)
        user.last_failed_login = current_time
        # Nếu vượt quá số lần đăng nhập sai cho phép → khóa tài khoản
        if user.failed_login_attempts >= settings.LOGIN_ATTEMPTS:
            user.account_status = AccountStatusSchema.LOCKED
            logger.warning(
                f"Tài khoản {user.email} đã bị khóa do quá nhiều lần đăng nhập sai"
            )
            try:
                # Gửi email thông báo tài khoản bị khóa
                await send_account_lockout_email(user.email, current_time)
                logger.info(f"Thông báo tài khoản bị khóa đã được gửi đến {user.email}")
            except Exception as e:
                # Không chặn luồng xử lý nếu gửi email thất bại
                logger.error(
                    f"Lỗi khi gửi thông báo tài khoản bị khóa đến {user.email}: {e}"
                )
            logger.warning(
                f"Tài khoản {user.email} đã bị khóa do quá nhiều lần đăng nhập sai"
            )
        await session.commit()
        await session.refresh(user)
    # thay đổi mật khẩu cho user
    async def change_user_password(
        self,
        user_id: uuid.UUID,
        data: ChangePasswordSchema,
        session: AsyncSession
    ) -> None:
        """Thay đổi mật khẩu cho user"""
        user = await self.get_user_by_id(user_id, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Người dùng không tồn tại"
                }
            )
        # Kiểm tra pass cũ có đúng không
        if not await self.verify_user_password(data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Mật khẩu hiện tại không đúng"
                }
            )
        # Kiểm tra pass mới có khác pass cũ không
        if await self.verify_user_password(data.new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Mật khẩu mới phải khác mật khẩu hiện tại"
                }
            )
        # Cập nhật mật khẩu mới
        user.hashed_password = generate_password_hash(data.new_password)
        logger.info(f"Thay đổi mật khẩu cho user {user.email}")
        await session.commit()
        await session.refresh(user)
    # thay đổi mật khẩu cho user(hệ thống)
    async def change_initial_password(
        self,
        user_id: uuid.UUID,
        data: ChangeInitialPasswordSchema,
        session: AsyncSession
    ) -> None:
        """Thay đổi mật khẩu cho user"""
        user = await self.get_user_by_id(user_id, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Người dùng không tồn tại"
                }
            )
        # Chỉ áp dụng với user bị đánh dấu
        if not user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "User không cần đổi mật khẩu lần đầu."}
            )
        # Cập nhật mật khẩu mới
        user.hashed_password = generate_password_hash(data.new_password)
        user.must_change_password = False
        logger.info(f"Thay đổi mật khẩu cho user {user.email}")
        await session.commit()
        await session.refresh(user)
    # Đặt lại mật khẩu cho người dùng(Khi quên mật khẩu)
    async def reset_password(
        self,
        token: str,
        new_password: str,
        session: AsyncSession,
    ) -> None:
        try:
            # Giải mã JWT token
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            if payload.get("type") != "password_reset":
                raise ValueError("Token reset không hợp lệ")
            # Lấy user ID từ payload
            user_id = uuid.UUID(payload["id"])
            # Lấy user kể cả khi chưa active
            user = await self.get_user_by_id(user_id, session, include_inactive=True)
            # Không tìm thấy user
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tồn tại"},
                )
            # Cập nhật pass mới
            user.hashed_password = generate_password_hash(new_password)
            # Reset trạng thái bảo mật
            await self.reset_user_state(user, session, clear_otp=True, log_action=True)

            await session.commit()
            await session.refresh(user)

            logger.info(f"Thay đổi mật khẩu thành công cho người dùng {user.email}")

        except jwt.ExpiredSignatureError:
            raise ValueError("Token reset mật khẩu đã hết hạn")
        except jwt.InvalidTokenError:
            raise ValueError("Token reset mật khẩu không hợp lệ")
        except Exception as e:
            logger.error(f"Lỗi khi reset mật khẩu: {e} ")
            raise
        
user_auth_service = UserAuthService()