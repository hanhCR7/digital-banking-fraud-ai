import importlib
import os
import pathlib

from backend.app.core.logging import get_logger

logger = get_logger()

PRIORITY_MODELS = [
    "backend.app.user_role.models",        
    "backend.app.role_permission.models",  
    "backend.app.role.models",
    "backend.app.permission.models",
    "backend.app.auth.models",             
    "backend.app.user_profile.models",
    "backend.app.next_of_kin.models",
    "backend.app.bank_account.models",
    "backend.app.virtual_card.models",
    "backend.app.transaction.models",
    "backend.app.core.ai.models",
    "backend.app.core.ml.models",
    "backend.app.core.rate_limit.models",
]

# Hàm phát hiện toàn bộ các file models.py trong dự án
def discover_models() -> list[str]:
    models_modules = []
    root_path = pathlib.Path(__file__).parent.parent

    logger.debug(f"Đang tìm kiếm các file model trong thư mục gốc: {root_path}")
    # Duyệt qua all các folder để tìm file models.py
    for root, _, files in os.walk(root_path):
        # Bỏ qua các thư mục không liên quan như môi trường ảo và cache
        if any(
            excluded in root for excluded in ["venv", "__pycache__", ".pytest_cache"]
        ):
            continue
        # Khi phát hiện file models.py, chuyển đường dẫn thư mục sang module Python
        if "models.py" in files:
            rel_path = os.path.relpath(root, root_path)
            module_path = rel_path.replace(os.path.sep, ".")
            # Xây dựng đường dẫn import đầy đủ cho module
            if module_path == ".":
                full_module_path = "backend.app.models"
            else:
                full_module_path = f"backend.app.{module_path}.models"

            logger.debug(f"Đã phát hiện file models tại module: {full_module_path}")
            models_modules.append(full_module_path)
    return models_modules

# Import toàn bộ các module model đã được phát hiện
def load_models() -> None:
    loaded: set[str] = set()

    # 1. Load các model theo thứ tự ưu tiên trước
    for module_path in PRIORITY_MODELS:
        try:
            importlib.import_module(module_path)
            logger.debug(f"[priority] Import module thành công: {module_path}")
            loaded.add(module_path)
        except ImportError as e:
            logger.error(f"[priority] Import module thất bại: {module_path}. Lỗi: {e}")

    # 2. Load các model còn lại (auto-discover, bỏ qua đã load)
    for module_path in discover_models():
        if module_path not in loaded:
            try:
                importlib.import_module(module_path)
                logger.debug(f"Import module thành công: {module_path}")
            except ImportError as e:
                logger.error(f"Import module thất bại: {module_path}. Lỗi: {e}")
