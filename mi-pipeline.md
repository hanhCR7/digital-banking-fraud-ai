# Limitations of Rule-Based AI in Fraud Detection

*(Hạn chế của AI dựa trên luật trong phát hiện gian lận)*

Các hệ thống AI dựa trên luật (rule-based), mặc dù ban đầu có thể mang lại hiệu quả, nhưng tồn tại nhiều hạn chế khi áp dụng vào bài toán phát hiện gian lận:

- **Khả năng thích nghi hạn chế**  
  Các hệ thống dựa trên luật không thể tự động điều chỉnh để thích ứng với các mô hình gian lận mới nếu không có sự can thiệp thủ công.

- **Thiếu khả năng cá nhân hóa**  
  Cùng một tập luật được áp dụng cho tất cả khách hàng, bỏ qua sự khác biệt trong hành vi của từng cá nhân.

- **Gánh nặng bảo trì**  
  Khi các thủ đoạn gian lận liên tục thay đổi, hệ thống cần được cập nhật thủ công thường xuyên, gây tốn kém thời gian và nguồn lực.

- **Vấn đề về khả năng mở rộng (Scalability)**  
  Khi xuất hiện nhiều kịch bản gian lận mới, độ phức tạp của tập luật tăng theo cấp số nhân, khiến hệ thống ngày càng khó quản lý và kiểm soát.

- **Khó xử lý các mối quan hệ phức tạp**  
  Việc triển khai rule-based chỉ dựa trên logic đơn giản `if–then`, do đó gặp khó khăn trong việc mô hình hóa sự tương tác giữa nhiều biến cùng lúc.

- **Nhận thức ngữ cảnh hạn chế (Limited Context Awareness)**  
  Các hệ thống dựa trên luật gặp khó khăn trong việc khai thác lịch sử người dùng và các mẫu hành vi — những yếu tố mà các mô hình Machine Learning xử lý một cách tự nhiên và hiệu quả hơn.

---

# Moving Beyond Rules: Introducing Gradient Boosting

*(Vượt qua hệ thống luật: Giới thiệu mô hình Gradient Boosting)*

Để khắc phục những hạn chế nêu trên, chúng tôi nâng cấp hệ thống phát hiện gian lận bằng cách tích hợp **Machine Learning**, cụ thể là mô hình **Gradient Boosting**.

Gradient Boosting đặc biệt hiệu quả trong bài toán phát hiện gian lận giao dịch tài chính nhờ các ưu điểm sau:

1. **Hoạt động hiệu quả trên dữ liệu mất cân bằng (Imbalanced Data)**  
   Mô hình vẫn đạt hiệu suất cao ngay cả khi giao dịch gian lận chiếm chưa đến 1% tổng số giao dịch.

2. **Cung cấp chỉ số tầm quan trọng của đặc trưng (Feature Importance)**  
   Mô hình cho phép xác định các thuộc tính giao dịch nào có ảnh hưởng lớn nhất đến việc phát hiện gian lận.

3. **Nhận diện các mẫu phi tuyến (Nonlinear Patterns)**  
   Thông qua tập hợp nhiều cây quyết định (ensemble), Gradient Boosting có khả năng nắm bắt các mối quan hệ phức tạp giữa các biến.

4. **Tối ưu cho dữ liệu có cấu trúc (Structured Data)**  
   Mô hình hoạt động đặc biệt tốt với dữ liệu dạng bảng như: số tiền giao dịch, thời gian, mã tài khoản, lịch sử giao dịch,…

5. **Khả năng chống nhiễu và ngoại lệ (Robust Against Outliers)**  
   Các giao dịch gian lận thường xuất hiện như những điểm bất thường trong dữ liệu, và Gradient Boosting xử lý các trường hợp này rất hiệu quả.

---

Bằng việc áp dụng Gradient Boosting, hệ thống hướng tới việc **nâng cao đáng kể khả năng phát hiện gian lận**, đạt được tính **thích nghi cao hơn**, **dễ mở rộng**, và **nhận thức ngữ cảnh tốt hơn** so với phương pháp dựa trên luật truyền thống.
