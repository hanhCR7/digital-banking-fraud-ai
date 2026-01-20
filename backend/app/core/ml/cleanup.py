import logging
import mlflow
from backend.app.core.ml.config import ml_settings

logger = logging.getLogger(__name__)

def cleanup_mlflow_runs():
    """
    Dọn dẹp (cleanup) các MLflow run còn tồn tại khi hệ thống khởi động.
    Mục đích:
    - Tránh tình trạng còn MLflow run đang active do lần chạy trước bị dừng đột ngột
    - Đảm bảo không có run nào ở trạng thái RUNNING gây sai lệch thống kê, metric
    - Giữ cho MLflow Tracking Server luôn ở trạng thái nhất quán
    Hàm này thường được gọi khi ứng dụng backend khởi động.
    """
    try:
        # Thiết lập địa chỉ MLflow Tracking Server
        mlflow.set_tracking_uri(ml_settings.MLFLOW_TRACKING_URI)
        # Kiểm tra xem trong process hiện tại có MLflow run nào đang active không
        active_run = mlflow.active_run()
        if active_run:
            # Nếu tồn tại run đang active, ghi log cảnh báo
            run_id = active_run.info.run_id
            logger.warning(f"Phát hiện MLflow run đang hoạt động ({run_id}) khi khởi động, tiến hành kết thúc.")
            # Kết thúc run đang active để tránh xung đột với các run mới
            mlflow.end_run()
            logger.info(f"Đã kết thúc thành công MLflow run đang hoạt động ({run_id}).")
        # Khởi tạo MLflow Client để thao tác trực tiếp với Tracking Server
        client = mlflow.MlflowClient()
        try:
            # Lấy thông tin experiment theo tên được cấu hình 
            experiment = mlflow.get_experiment_by_name(ml_settings.MLFLOW_EXPERIMENT_NAME)
            if experiment:
                experiment_id = experiment.experiment_id 
                # Tìm all các run trong experiment đang ở trạng thái RUNNING
                # Các run này có thể bị treo do crash, timeout or dừng bất thường
                running_runs = client.search_runs(
                    experiment_ids=[experiment_id],
                    filter_string="attributes.status = 'RUNNING'"
                )
                # Duyệt qua từng run bị treo và kết thúc chúng
                for run in running_runs:
                    logger.warning(f"hát hiện MLflow run RUNNING bị tồn đọng ({run.info.run_id}), tiến hành kết thúc.")
                    # Đánh dấu run là FINISHED để giải phóng trạng thái RUNNING
                    client.set_terminated(run.info.run_id, "FINISHED")
                logger.info(f"Đã dọn dẹp {len(running_runs)} MLflow run bị tồn đọng.")
        except Exception as e:
            logger.error(f"Lỗi khi dọn dẹp các MLflow run tồn đọng: {e}.")
        logger.info("Hoàn tất quá trình dọn dẹp MLflow run thành công.")
    except Exception as e:
        logger.error(f"Không thể dọn dẹp các MLflow run: {e}.")
