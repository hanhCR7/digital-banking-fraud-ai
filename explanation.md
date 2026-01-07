# System Breakdown

## Transaction Risk Analysis

Mỗi giao dịch sẽ được **phân tích và đánh giá** dựa trên nhiều **yếu tố rủi ro (risk factors)** khác nhau, bao gồm:

* **Amount**
  Đánh giá cả **giá trị tuyệt đối của giao dịch** và **mức độ chênh lệch so với lịch sử giao dịch của người dùng**.

* **Time**
  Xem xét **khung giờ giao dịch**, bao gồm giờ hành chính ngân hàng và các **thời điểm bất thường** (ngoài giờ, ban đêm).

* **Frequency**
  Theo dõi **tần suất giao dịch**, xác định các trường hợp giao dịch diễn ra quá thường xuyên trong một khoảng thời gian ngắn.

* **Pattern**
  Phát hiện các **mẫu giao dịch đáng ngờ**, chẳng hạn như:

  * Số tiền tròn
  * Lặp lại cùng một giá trị giao dịch nhiều lần

* **Velocity**
  Theo dõi **tổng khối lượng giao dịch trong vòng 24 giờ**, nhằm phát hiện hành vi giao dịch dồn dập.

---

## Risk Scoring System

Mỗi yếu tố rủi ro được đề cập ở trên sẽ được gán một **risk score** trong khoảng từ `0` đến `1`
(`0 = low risk`, `1 = high risk`).

### Weighting of Factors

Các yếu tố rủi ro sẽ được **gán trọng số khác nhau** để tính toán **final risk score** cho mỗi giao dịch:

* **Amount**: chiếm **30%** tổng điểm rủi ro
* **Frequency**: chiếm **20%**
* **Pattern**: chiếm **20%**
* **Velocity Amount**: chiếm **20%**
* **Time**: chiếm **10%**

---

## Automatic Risk Amplification

* **Risk score sẽ tự động được tăng lên** khi có nhiều yếu tố rủi ro cao xuất hiện đồng thời.
  *Ví dụ: Amount cao + Frequency cao ⇒ risk score được đẩy lên mức `0.9`.*

* Hệ thống cũng định nghĩa sẵn các **ngưỡng rủi ro (thresholds)**, bao gồm:

  * **High Amount**: giá trị giao dịch lớn hơn `10,000`
  * **Velocity**: tổng giá trị giao dịch vượt `50,000` trong vòng 24 giờ
  * **Frequency**: nhiều hơn `5` giao dịch trong vòng 24 giờ

---

## Response System

Các giao dịch có **risk score > 0.7** sẽ được **tự động đánh dấu (flagged)**.

Những giao dịch bị flagged sẽ:

* Bị **tạm thời chặn**
* Được **chuyển cho account executives / bộ phận kiểm soát rủi ro** để rà soát
* Được **ghi log kèm theo phân tích rủi ro chi tiết**
* Sau quá trình kiểm tra, giao dịch sẽ được:

  * Phê duyệt nếu hợp lệ
  * Hoặc xác nhận là gian lận (fraud) nếu phát hiện vi phạm

---

## Record Keeping

* Tất cả kết quả phân tích rủi ro sẽ được lưu trữ trong bảng **`TransactionRiskScore`**.
* Hệ thống duy trì **lịch sử giao dịch trong 90 ngày** để phục vụ phân tích pattern.
* **Risk scores và các lý do đánh giá** được ghi nhận đầy đủ nhằm phục vụ **audit và kiểm tra tuân thủ**.
