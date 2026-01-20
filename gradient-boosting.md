# Hiểu về Gradient Boosting: Giải thích đơn giản

Mô hình **Gradient Boosting** có thể được hình dung như một **đội ngũ các chuyên gia**, mỗi người phối hợp với nhau để cải thiện kết quả cuối cùng. Mỗi mô hình trong chuỗi sẽ học từ những sai sót của các mô hình trước đó.

## Cách Gradient Boosting hoạt động

1. **Bắt đầu với một mô hình đơn giản**  
   Quá trình khởi đầu bằng một mô hình cơ bản — thường là một cây quyết định đơn lẻ — để đưa ra các dự đoán ban đầu. Những dự đoán này thường còn nhiều sai sót.

2. **Sửa các lỗi**  
   Một mô hình thứ hai được huấn luyện với mục tiêu cụ thể là sửa những lỗi mà mô hình đầu tiên mắc phải.

3. **Tinh chỉnh thêm**  
   Một mô hình thứ ba được bổ sung để tiếp tục khắc phục các lỗi còn sót lại mà hai mô hình trước chưa giải quyết được.

4. **Cải thiện lặp đi lặp lại**  
   Quá trình này tiếp diễn qua nhiều vòng lặp. Mỗi mô hình mới tập trung vào phần sai lệch (*residual errors*) còn lại của tất cả các mô hình trước đó.

5. **Dự đoán cuối cùng**  
   Tất cả các mô hình được kết hợp lại để tạo ra dự đoán cuối cùng. Mỗi mô hình chỉ đóng góp một phần nhỏ, nhưng khi cộng lại sẽ cho kết quả chính xác hơn rất nhiều.

---

Tóm lại, **Gradient Boosting** là một **kỹ thuật mạnh mẽ**, trong đó **mỗi mô hình học từ những sai lầm trong quá khứ**, giúp **hiệu năng được cải thiện dần theo thời gian**.
