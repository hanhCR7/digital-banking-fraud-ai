from celery import Celery
from backend.app.core.config import settings
from backend.app.core.ml.config import ml_settings
from celery.schedules import crontab

celery_app = Celery(
    "worker",
    broker=f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
)

celery_app.conf.update(
    task_serializer="json",
    task_track_starttd=True,
    result_serializer="json",
    accept_content=["application/json"],
    result_backend_max_retries=10,
    task_send_sent_event=True,
    result_extended=True,
    result_backend_always_retry=True,
    result_expiration=3600,
    task_time_limit= 5 * 60,
    task_soft_time_limit= 5 * 60,
    worker_send_task_events=True,
    task_ack_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=30,
    task_max_retries=3,
    task_default_queue="nextgen_tasks",
    task_create_missing_queues=True,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=50000,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

celery_app.autodiscover_tasks(
    packages=["backend.app.core.tasks"],
    related_name="tasks",
    force=True,
)

celery_app.conf.beat_scheduler = "celery.beat.PersistentScheduler"
celery_app.conf.beat_schedule_filename = "/tmp/celerybeat-schedule"


celery_app.conf.beat_schedule = {
    #  Train model gian lận hàng ngày
    "train-fraud-model-daily": {
        "task": "train_fraud_detection_model",
        "schedule": crontab(hour="2", minute="0"), # 02:00 hàng ngày
        "kwargs": {
            "days_lookback": ml_settings.DEFAULT_TRAINING_LOOKBACK_DAYS,
            "hyperparams": ml_settings.DEFAULT_GRADIENT_BOOSTING_PARAMS
        },
        "options": {"queue": "ml_tasks"}, # Chạy trên queue ML

    },
    # Train model chuyên sâu hàng tuần
    "train-fraud-model-weekly": {
        "task": "train_fraud_detection_model",
        "schedule": crontab(hour="3", minute="0", day_of_week="0"), # CN: 03:00
        "kwargs": {
            "days_lookback": 180, # Data 6 tháng
            "hyperparams": {
                **ml_settings.DEFAULT_GRADIENT_BOOSTING_PARAMS,
                "n_estimators": 200,                # Nhiều cây hơn
                "learning_rate": 0.05,              # Learning rate nhỏ hơn
            }
        },
        "options": {"queue": "ml_tasks"}
    },
    # Đánh giá hiệu năng model hàng này
    "evaluate-fraud-model-daily": {
        "task": "evaluate_fraud_model_performance",
        "schedule": crontab(hour="6", minute="0"), # 06:00 hàng ngày
        "kwargs": {"days": 7}, # Evalyate 7 ngày gần nhất
        "options": {"queue": "ml_tasks"}
    }, 
    # Tự động deploy model tốt nhất hàng tuần
    "auto-deploy-weekly": {
        "task": "auto_deploy_best_model",
        "schedule": crontab(hour="8", minute="0", day_of_week="1"), # Thứ 2
        "kwargs": {
            "performance_threshold": ml_settings.DEFAULT_PERFORMANCE_THRESHOLD
        },
        "options": {"queue":"ml_tasks"}
    }
}