## **Tóm tắt kiến trúc Pipeline Machine Learning của chúng tôi**

## **Cách hệ thống hoạt động trong thực tế**

1. Khách hàng khởi tạo một giao dịch  
2. Giao dịch được xử lý và lưu trữ trong cơ sở dữ liệu  
3. Pipeline Machine Learning trích xuất các đặc trưng từ giao dịch  
4. Mô hình đã được triển khai chấm điểm rủi ro gian lận cho giao dịch  
5. Nếu điểm rủi ro vượt quá ngưỡng quy định, giao dịch sẽ bị gắn cờ  
6. Nhân viên kiểm tra các giao dịch bị gắn cờ và xác nhận hoặc bác bỏ gian lận  
7. Các trường hợp được xác nhận sẽ được đưa ngược lại làm dữ liệu huấn luyện  
8. Mô hình được huấn luyện lại định kỳ với dữ liệu mới  
9. Các mô hình có hiệu năng tốt hơn sẽ được triển khai vào môi trường sản xuất  

Hệ thống của chúng tôi cung cấp hai cách để triển khai các mô hình có hiệu năng tốt hơn:

### **Triển khai thủ công (Manual Deployment)**

Quản trị viên có thể chọn một mô hình cụ thể theo **ID** và triển khai bằng endpoint:  
`/api/v1/ml/deploy`

### **Triển khai tự động (Auto-Deployment)**

Hệ thống có thể tự động tìm và triển khai mô hình có hiệu năng tốt nhất, vượt qua ngưỡng đánh giá, thông qua endpoint:  
`/api/v1/ml/auto-deploy`
