# NextGen Bank — Hệ Thống Ngân Hàng Thế Hệ Mới

> **Project Cá Nhân** — Xây dựng nền tảng ngân hàng số hiện đại tích hợp mô hình Machine Learning phát hiện gian lận giao dịch theo thời gian thực.

---

## 📋 Mục Tiêu Dự Án

NextGen Bank là một hệ thống API ngân hàng số được xây dựng nhằm:

- **Cung cấp dịch vụ ngân hàng cốt lõi** — Đăng ký/đăng nhập, quản lý tài khoản, gửi tiền, rút tiền, chuyển tiền nội bộ, lịch sử giao dịch, sao kê.
- **Quản lý thẻ ảo (Virtual Card)** — Phát hành, kích hoạt, khóa, nạp tiền và hủy thẻ ảo.
- **Phát hiện gian lận thông minh** — Sử dụng mô hình **Gradient Boosting** (Machine Learning) để tự động chấm điểm rủi ro cho mỗi giao dịch, thay thế phương pháp rule-based truyền thống.
- **Vòng lặp CIA (Continuous Improvement Architecture)** — Cho phép huấn luyện lại mô hình từ dữ liệu giao dịch thực tế được xác nhận, rồi tự động hoặc thủ công triển khai mô hình mới lên môi trường sản xuất.
- **Phân quyền RBAC** — Hệ thống phân vai trò (Role-Based Access Control) với permission chi tiết cho từng endpoint.

---

## 🛠️ Công Nghệ Sử Dụng

### Backend
| Thành phần | Công nghệ |
|---|---|
| **API Framework** | [FastAPI](https://fastapi.tiangolo.com/) 0.115 + [Uvicorn](https://www.uvicorn.org/) |
| **ORM / Database** | [SQLModel](https://sqlmodel.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 (async) |
| **Database** | PostgreSQL 16 (với `asyncpg`) |
| **Cache / Message Broker** | Redis 7 + RabbitMQ 3.13 |
| **Task Queue** | [Celery](https://docs.celeryq.dev/) 5.3 + Celery Beat (lịch tác vụ) + Flower (giám sát) |
| **Auth** | JWT (PyJWT) + Argon2 password hashing |
| **Email** | FastAPI-Mail + Mailpit (local SMTP) |
| **File Storage** | Cloudinary (ảnh đại diện) |
| **Logging** | Loguru + structured logging |
| **Rate Limiting** | Custom middleware |
| **Monitoring** | OpenTelemetry + Prometheus client |

### Machine Learning & MLOps
| Thành phần | Công nghệ |
|---|---|
| **ML Model** | Gradient Boosting (scikit-learn 1.6) |
| **ML Experiment Tracking** | [MLflow](https://mlflow.org/) 2.20 |
| **Data Processing** | Pandas, NumPy, SciPy |
| **Visualization** | Matplotlib |

### Frontend
| Thành phần | Công nghệ |
|---|---|
| **Framework** | React (Next.js) |
| **Containerization** | Docker + Docker Compose |

### Infrastructure
| Thành phần | Công nghệ |
|---|---|
| **Reverse Proxy / Load Balancer** | [Traefik](https://traefik.io/) |
| **Containerization** | Docker + Docker Compose |
| **DB Migration** | Alembic |

---

## 🤖 Mô Hình AI — Phát Hiện Gian Lận Giao Dịch

### Tại Sao Không Dùng Rule-Based?

Các hệ thống phát hiện gian lận truyền thống dựa trên luật (`if–then`) gặp nhiều hạn chế:

- Không thể tự thích nghi với các chiêu trò gian lận mới.
- Không cá nhân hóa theo hành vi từng khách hàng.
- Khó mở rộng khi số lượng kịch bản gian lận tăng.
- Chỉ xử lý được quan hệ tuyến tính đơn giản.

### Giải Pháp: Gradient Boosting

Mô hình **Gradient Boosting** được chọn vì:

1. **Hoạt động hiệu quả trên dữ liệu mất cân bằng** — Giao dịch gian lận thường chiếm dưới 1% tổng giao dịch.
2. **Feature Importance** — Cho biết đặc trưng nào ảnh hưởng nhất đến kết quả dự đoán.
3. **Nhận diện mẫu phi tuyến** — Khai thác quan hệ phức tạp giữa các biến (số tiền, thời điểm, lịch sử,...).
4. **Chống nhiễu tốt** — Xử lý hiệu quả các điểm ngoại lệ (outliers) thường gặp trong giao dịch gian lận.
5. **Tối ưu cho dữ liệu dạng bảng** — Phù hợp với cấu trúc dữ liệu giao dịch tài chính.

### Pipeline ML Trong Thực Tế

```
Giao dịch mới
     │
     ▼
Trích xuất đặc trưng (Feature Extraction)
     │
     ▼
Mô hình Gradient Boosting chấm điểm rủi ro
     │
     ├─ Điểm rủi ro thấp → Giao dịch được duyệt
     │
     └─ Điểm rủi ro CAO → Gắn cờ (Flag) để kiểm tra
                               │
                               ▼
                      Chuyên viên xem xét & xác nhận
                               │
                               ▼
                      Dữ liệu xác nhận → Huấn luyện lại mô hình
                               │
                               ▼
                      Triển khai mô hình mới (Manual / Auto-Deploy)
```

### API Endpoints ML

| Endpoint | Mô tả |
|---|---|
| `POST /api/v1/ml/train` | Huấn luyện mô hình mới từ dữ liệu hiện có |
| `POST /api/v1/ml/deploy` | Triển khai thủ công một mô hình theo ID |
| `POST /api/v1/ml/auto-deploy` | Tự động chọn và triển khai mô hình tốt nhất |
| `GET /api/v1/transaction/fraud-review` | Xem danh sách giao dịch bị gắn cờ |
| `GET /api/v1/transaction/risk-history` | Lịch sử điểm rủi ro của giao dịch |

---

## 📁 Cấu Trúc Dự Án

```
src/
├── backend/
│   ├── app/
│   │   ├── api/            # Routes & Services (Auth, Account, Card, ML, Admin…)
│   │   ├── auth/           # JWT token handler
│   │   ├── bank_account/   # Logic tài khoản ngân hàng
│   │   ├── core/           # Config, DB, Logging, RBAC bootstrap, Rate Limit
│   │   ├── transaction/    # Xử lý và phân tích giao dịch
│   │   ├── virtual_card/   # Quản lý thẻ ảo
│   │   └── main.py         # Entry point FastAPI
│   ├── docker/             # Dockerfile cho từng môi trường
│   └── requirements.txt
├── frontend/
│   └── nextgen_banking/    # Ứng dụng React (Next.js)
├── migrations/             # Alembic DB migrations
├── local.yml               # Docker Compose (môi trường local)
└── Makefile                # Các lệnh phổ biến
```

---

## 🚀 Hướng Dẫn Chạy Dự Án (Local)

### Yêu Cầu

- [Docker](https://www.docker.com/) & Docker Compose
- Python 3.12+ (nếu chạy ngoài Docker)
- Node.js 20+ (nếu chạy frontend ngoài Docker)

### 1. Clone Repository

```bash
git clone <repository-url>
cd nextgen-bank-fastapi/src
```

### 2. Tạo File Biến Môi Trường

```bash
cp .envs/.env.example .envs/.env.local
# Cập nhật các giá trị trong .env.local
```

### 3. Tạo Docker Network

```bash
docker network create nextgen_local_nw
```

### 4. Build & Khởi Động Services

```bash
# Sử dụng Makefile
make build-local
make up-local

# Hoặc trực tiếp với Docker Compose
docker compose -f local.yml up --build
```

### 5. Chạy Migrations

```bash
make migrate-local
# hoặc
docker compose -f local.yml exec api alembic upgrade head
```

### 6. Truy Cập Các Services

| Service | URL |
|---|---|
| **API (FastAPI Docs)** | http://api.localhost/api/v1/docs |
| **Frontend** | http://frontend.localhost |
| **MLflow UI** | http://mlflow.localhost |
| **Flower (Celery Monitor)** | http://flower.localhost |
| **RabbitMQ Management** | http://rabbitmq.localhost |
| **Mailpit (Email)** | http://localhost:8025 |
| **Traefik Dashboard** | http://localhost:8081 |

---

## 🔐 Phân Quyền (RBAC)

Hệ thống sử dụng **Role-Based Access Control** với 6 vai trò chính:

| Vai trò | Mô tả |
|---|---|
| `super-admin` | Toàn quyền hệ thống, quản lý người dùng & mô hình ML |
| `admin` | Quản lý người dùng & mô hình ML |
| `branch-manager` | Quản lý chi nhánh, giao dịch rủi ro |
| `account-executive` | Xem xét giao dịch bị gắn cờ, phê duyệt/từ chối gian lận |
| `teller` | nhân viên giao dịch |
| `customer` | khách hàng |

---

## 📊 Các Tính Năng Chính

- [x] Đăng ký, xác thực email, đăng nhập, đổi mật khẩu, quên mật khẩu
- [x] Quản lý hồ sơ cá nhân & người thân (Next of Kin)
- [x] Tạo & quản lý tài khoản ngân hàng
- [x] Gửi tiền, rút tiền, chuyển tiền
- [x] Sao kê giao dịch (PDF export)
- [x] Phát hành & quản lý thẻ ảo
- [x] Phát hiện gian lận bằng Gradient Boosting
- [x] MLflow experiment tracking & model registry
- [x] Triển khai mô hình ML tự động / thủ công
- [x] Dashboard quản trị giao dịch rủi ro
- [x] Phân quyền RBAC đầy đủ
- [x] Rate limiting & health check endpoint
- [x] Gửi email thông báo qua Celery task queue


