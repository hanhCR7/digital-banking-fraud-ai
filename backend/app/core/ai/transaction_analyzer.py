from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Tuple
from uuid import UUID

import numpy as np
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.bank_account.models import BankAccount
from backend.app.core.ai.config import ai_settings
from backend.app.core.logging import get_logger
from backend.app.core.utils.number_format import format_currency
from backend.app.transaction.models import Transaction

logger = get_logger()
class TransactionAnalyzer:
    def __init__(self):
        # Danh sách các đặc trưng (features) dùng để phân tích và đánh giá giao dịch
        self.features = [
            "amount",              # Số tiền của giao dịch hiện tại
            "time_of_day",         # Thời điểm trong ngày (sáng / chiều / tối / đêm)
            "day_of_week",         # Ngày trong tuần (thứ 2 → chủ nhật)
            "frequency",           # Tần suất giao dịch trong một khoảng thời gian
            "pattern_match",       # Mức độ khớp với các mẫu giao dịch đáng ngờ đã biết
            "historical_amount",   # So sánh với số tiền giao dịch trung bình trong quá khứ
            "velocity_amount",     # Tốc độ thay đổi số tiền giữa các giao dịch liên tiếp
        ]
    
    async def get_user_transaction_history(
        self,
        user_id: UUID,
        session: AsyncSession,
        days: int = ai_settings.ANALYSIS_WINDOW_DAYS,
    ) -> list[Transaction]:
        """
        Lấy lịch sử giao dịch gần đây của người dùng (theo vai trò người gửi)
        """
        # Thời điểm cắt dữ liệu: hiện tại - số ngày phân tích
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        # Truy vấn các giao dịch mà user là người gửi và nằm trong khoảng thời gian cho phép
        query = select(Transaction).where(
            Transaction.sender_id == user_id,
            Transaction.created_at >= cutoff_date,
        )
        # Thực thi query bất đồng bộ
        result = await session.exec(query)
        # Chuyển kết quả sang list để dễ xử lý phía sau
        return list(result)
    def _normalize_hour(self, hour: int) -> float:
        """
        Chuẩn hóa mức độ rủi ro theo thời điểm giao dịch trong ngày
        - Giờ hành chính: rủi ro thấp
        - Ngoài giờ hành chính: rủi ro trung bình
        - Đêm khuya (rất sớm / rất muộn): rủi ro cao
        """

        # Khoảng giờ hành chính do hệ thống cấu hình
        banking_hours = (
            ai_settings.BANKING_HOURS_START,
            ai_settings.BANKING_HOURS_END,
        )
        # Giao dịch trong giờ hành chính
        if banking_hours[0] <= hour <= banking_hours[1]:
            return float(ai_settings.BANKING_HOURS_RISK)
        # Giao dịch vào giờ rất khuya hoặc rất sớm
        elif hour < 6 or hour > 22:
            return float(ai_settings.LATE_HOURS_RISK)
        # Các khung giờ còn lại (ngoài giờ hành chính)
        else:
            return float(ai_settings.OFF_HOURS_RISK)
    def _calculate_frequency(
        self,
        transaction: Transaction,
        history: list[Transaction],
    ) -> float:
        """
        Tính điểm rủi ro dựa trên tần suất giao dịch
        Ý tưởng:
        - So sánh khoảng cách thời gian giao dịch hiện tại
          với khoảng cách trung bình giữa các giao dịch trước đó
        - Giao dịch xảy ra dồn dập bất thường → rủi ro cao
        """
        # Không có lịch sử → gán mức trung tính
        if not history:
            return 0.5
        # Lấy danh sách thời điểm giao dịch, sắp xếp tăng dần
        timestamps = sorted(t.created_at for t in history)

        gaps: list[float] = []
        # Tính khoảng cách thời gian giữa các giao dịch liên tiếp (đơn vị: giờ)
        for i in range(1, len(timestamps)):
            gap = (
                timestamps[i] - timestamps[i - 1]
            ).total_seconds() / 3600
            gaps.append(gap)
        # Không đủ dữ liệu để tính tần suất
        if not gaps:
            return 0.5
        # Khoảng cách trung bình giữa các giao dịch
        avg_gap = float(np.mean(gaps))
        # Tránh chia cho 0 (giao dịch xảy ra cùng thời điểm)
        if avg_gap == 0:
            return 1.0
        # Khoảng cách giữa giao dịch hiện tại và giao dịch gần nhất
        current_gap = (
            transaction.created_at - timestamps[-1]
        ).total_seconds() / 3600
        # Chuẩn hóa điểm rủi ro (giới hạn tối đa là 1.0)
        return min(1.0, abs(1 - (current_gap / avg_gap)))

    def _check_round_amounts(
        self,
        transaction: Transaction,
        history: list[Transaction],
    ) -> float:
        """
        Đánh giá rủi ro dựa trên việc số tiền có phải là số tròn hay không
        Ý tưởng:
        - Giao dịch gian lận / rửa tiền thường sử dụng số tiền tròn (1000, 10000, 500000…)
        - Số tiền càng nhiều số 0 ở cuối → mức độ nghi ngờ càng cao
        """

        # Chuyển số tiền sang float để xử lý
        amount = float(transaction.amount)

        # Kiểm tra xem số tiền có phải là số nguyên không (vd: 1000.00)
        is_round = amount.is_integer()

        # Chuyển sang chuỗi để đếm số lượng số 0 ở cuối
        str_amount = str(int(amount))

        # Đếm số chữ số 0 liên tiếp ở cuối (vd: 100000 → 4 số 0)
        zero_count = len(str_amount) - len(str_amount.rstrip("0"))

        # Tính điểm rủi ro:
        # - Mỗi số 0 ở cuối đóng góp 0.2 điểm
        # - Nếu là số tròn hoàn toàn, cộng thêm 0.3 điểm
        risk_score = min(
            1.0,
            (zero_count * 0.2) + (0.3 if is_round else 0),
        )

        return risk_score


    def _check_repeated_amounts(
            self,
            transaction: Transaction,
            history: list[Transaction],
        ) -> float:
            """
            Đánh giá rủi ro dựa trên việc lặp lại cùng một số tiền trong lịch sử giao dịch

            Ý tưởng:
            - Giao dịch lặp lại cùng số tiền nhiều lần có thể là:
                + Chia nhỏ giao dịch (smurfing)
                + Hành vi gian lận có kịch bản sẵn
            """

            # Không có lịch sử → không đủ dữ liệu để đánh giá
            if not history:
                return 0.0

            # Số tiền của giao dịch hiện tại
            current_amount = float(transaction.amount)

            # Đếm số giao dịch trước đó có cùng số tiền (cho phép sai số nhỏ)
            same_amount_count = sum(
                1
                for t in history
                if abs(float(t.amount) - current_amount) < 0.01
            )

            # Chuẩn hóa điểm rủi ro theo tỷ lệ giao dịch trùng số tiền
            return min(1.0, same_amount_count / len(history))
    def _check_velocity(
        self,
        transaction: Transaction,
        history: list[Transaction],
    ) -> dict:
        """
        Phân tích tốc độ giao dịch (transaction velocity)

        Velocity gồm 2 khía cạnh:
        - Tần suất giao dịch trong thời gian ngắn
        - Tổng giá trị giao dịch trong cùng khoảng thời gian

        Thường dùng để phát hiện:
        - Account takeover
        - Fraud automation
        - Rửa tiền tốc độ cao
        """

        # Không có lịch sử → không thể đánh giá velocity
        if not history:
            return {"frequency_score": 0.0, "amount_velocity_score": 0.0}

        # Chỉ xét các giao dịch trong vòng 24 giờ gần nhất
        recent_cutoff = transaction.created_at - timedelta(hours=24)

        recent_transactions = [
            t for t in history if t.created_at >= recent_cutoff
        ]

        # Không có giao dịch gần đây → velocity thấp
        if not recent_transactions:
            return {"frequency_score": 0.0, "amount_velocity_score": 0.0}

        # Số lượng giao dịch trong 24h
        tx_count = len(recent_transactions)

        # Chuẩn hóa tần suất theo ngưỡng cấu hình
        freq_score = min(
            1.0,
            tx_count / ai_settings.FREQUENCY_THRESHOLD,
        )

        # Tổng khối lượng tiền giao dịch (bao gồm giao dịch hiện tại)
        total_volume = (
            sum(float(t.amount) for t in recent_transactions)
            + float(transaction.amount)
        )

        # Chuẩn hóa tốc độ dòng tiền theo ngưỡng cấu hình
        amount_velocity_score = float(
            min(
                1.0,
                total_volume / float(ai_settings.VELOCITY_THRESHOLD),
            )
        )

        # Nếu cả tần suất và khối lượng đều cao → rủi ro tối đa
        if freq_score > 0.7 and amount_velocity_score > 0.7:
            combined_score = 1.0
        else:
            # Ngược lại lấy trung bình
            combined_score = (freq_score + amount_velocity_score) / 2

        return {
            "frequency_score": freq_score,
            "amount_velocity_score": amount_velocity_score,
            "combined_score": combined_score,
        }


    def _calculate_amount_risk(
        self,
        amount_ratio: float,
        current_amount: float,
    ) -> float:
        """
        Đánh giá rủi ro dựa trên quy mô số tiền giao dịch

        - amount_ratio: so sánh với trung bình lịch sử
        - current_amount: so sánh với ngưỡng giá trị tuyệt đối
        """

        # Rủi ro tương đối so với lịch sử
        base_risk = min(1.0, amount_ratio / 5)

        # Rủi ro tuyệt đối theo ngưỡng hệ thống
        amount_risk = float(
            min(
                1.0,
                current_amount / float(ai_settings.HIGH_AMOUNT_THRESHOLD),
            )
        )
        # Lấy rủi ro lớn hơn để tránh bỏ sót giao dịch lớn bất thường
        return max(base_risk, amount_risk)


    def _calculate_time_risk(
        self,
        time_of_day: float,
        day_of_week: float,
    ) -> float:
        """
        Kết hợp rủi ro theo thời gian:
        - Khung giờ trong ngày
        - Ngày trong tuần

        Dùng trọng số cấu hình để dễ tuning
        """

        weights = ai_settings.TIME_RISK_WEIGHTS

        return (
            time_of_day * float(weights["time_of_day"])
            + day_of_week * float(weights["day_of_week"])
        )


    def _detect_patterns(
        self,
        transaction: Transaction,
        history: list[Transaction],
    ) -> float:
        """
        Phát hiện các pattern giao dịch bất thường

        Bao gồm:
        - Số tiền tròn
        - Lặp lại cùng số tiền
        - Velocity cao
        """

        # Không có lịch sử → mức trung tính
        if not history:
            return 0.5

        patterns = {
            "round_amounts": self._check_round_amounts(transaction, history),
            "repeated_amounts": self._check_repeated_amounts(transaction, history),
            "velocity": self._check_velocity(transaction, history)["combined_score"],
        }

        # Tổng hợp điểm pattern theo trọng số cấu hình
        return sum(
            score * ai_settings.PATTERN_WEIGHTS[pattern]
            for pattern, score in patterns.items()
        )


    def extract_features(
        self,
        transaction: Transaction,
        history: list[Transaction],
    ) -> dict:
        """
        Trích xuất feature vector phục vụ AI / rule-based scoring

        Output là dict các feature đã được chuẩn hóa
        """

        features: dict = {}

        # Giá trị giao dịch hiện tại
        features["amount"] = float(transaction.amount)

        # Danh sách số tiền lịch sử (fallback nếu không có)
        amounts = (
            [float(t.amount) for t in history]
            if history
            else [features["amount"]]
        )

        # Giá trị trung bình lịch sử
        avg_amount = float(np.mean(amounts))

        # Tỷ lệ so với trung bình
        features["amount_ratio"] = (
            features["amount"] / avg_amount if avg_amount else 1
        )

        # Giờ giao dịch
        hour = transaction.created_at.hour
        features["time_of_day"] = self._normalize_hour(hour)

        # Ngày trong tuần (0–6 → chuẩn hóa về 0–1)
        features["day_of_week"] = transaction.created_at.weekday() / 6

        # Tần suất giao dịch
        features["frequency"] = self._calculate_frequency(
            transaction,
            history,
        )

        # Điểm pattern bất thường
        features["pattern_match"] = self._detect_patterns(
            transaction,
            history,
        )

        # Velocity – khối lượng giao dịch
        velocity_metrics = self._check_velocity(transaction, history)
        features["velocity_amount"] = velocity_metrics["amount_velocity_score"]

        return features
    async def analyze_transaction(
        self,
        transaction: Transaction,
        user_id: UUID,
        session: AsyncSession,
    ) -> Tuple[float, dict]:
        """
        Phân tích rủi ro tổng thể cho một giao dịch

        Trả về:
        - final_score: điểm rủi ro (0.0 – 1.0)
        - risk_factors: dữ liệu chi tiết giải thích vì sao giao dịch bị đánh giá rủi ro
        """

        try:
            # 1. Lấy lịch sử giao dịch của user trong window phân tích
            history = await self.get_user_transaction_history(
                user_id,
                session,
                ai_settings.ANALYSIS_WINDOW_DAYS,
            )

            # 2. Trích xuất feature vector
            features = self.extract_features(transaction, history)

            # 3. Phân tích velocity (tần suất + khối lượng)
            velocity_metrics = self._check_velocity(transaction, history)

            # 4. Tính điểm rủi ro cho từng nhóm yếu tố
            risk_scores = {
                "amount": self._calculate_amount_risk(
                    features["amount_ratio"],
                    float(transaction.amount),
                ),
                "time": self._calculate_time_risk(
                    features["time_of_day"],
                    features["day_of_week"],
                ),
                "frequency": velocity_metrics["frequency_score"],
                "pattern": features["pattern_match"],
                "velocity_amount": velocity_metrics["amount_velocity_score"],
            }

            # 5. Lấy trọng số cho từng yếu tố
            weights = ai_settings.RISK_WEIGHTS

            # 6. Tính điểm rủi ro cơ bản (weighted sum)
            base_score = sum(
                score * weights[factor]
                for factor, score in risk_scores.items()
            )

            # 7. Rule tăng mức rủi ro:
            # Nếu số tiền lớn + tần suất cao -> ép mức nguy hiểm cao
            final_score = (
                max(base_score, 0.9)
                if (
                    risk_scores["amount"] > 0.7
                    and risk_scores["frequency"] > 0.7
                )
                else base_score
            )

            final_score = round(final_score, 2)

            # 8. Xác định các trigger gây rủi ro cao
            high_risk_triggers = []

            if final_score > ai_settings.HIGH_RISK_SCORE_THRESHOLD:
                if risk_scores["amount"] > 0.7:
                    high_risk_triggers.append("high_amount")

                if risk_scores["frequency"] > 0.7:
                    high_risk_triggers.append("high_frequency")

                if risk_scores["velocity_amount"] > 0.7:
                    high_risk_triggers.append("high_velocity")

            # 9. Chuẩn bị dữ liệu giải thích chi tiết cho audit / log
            risk_factors = {
                factor: {
                    "score": round(score, 2),
                    "weight": weights[factor],
                    "contribution": round(score * weights[factor], 2),
                }
                for factor, score in risk_scores.items()
            }

            # 10. Tổng hợp trigger và ngưỡng đánh giá
            risk_factors["risk_triggers"] = {
                "triggers": high_risk_triggers,
                "score": final_score,
                "threshold": ai_settings.HIGH_RISK_SCORE_THRESHOLD,
            }

            # 11. Tóm tắt giao dịch phục vụ logging / monitoring
            # Lưu ý: currency không nằm trong Transaction
            # -> được xác định theo tài khoản gửi (BankAccount)
            sender_account = await session.get(
                BankAccount,
                transaction.sender_account_id,
            )

            currency = sender_account.currency if sender_account else "USD"
            risk_factors["transaction_summary"] = {
                # Số tiền giao dịch (format để hiển thị / log)
                "amount": format_currency( transaction.amount),
                "time": transaction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                # Tổng khối lượng giao dịch trong 24h gần nhất
                "24h_total_volume": format_currency(
                    sum(
                        float(t.amount)
                        for t in history
                        if (transaction.created_at - t.created_at).total_seconds() <= 86400
                    )
                ),
                # Số lượng giao dịch trong 24h gần nhất
                "24h_transaction_count": sum(
                    1
                    for t in history
                    if (transaction.created_at - t.created_at).total_seconds() <= 86400
                ),
            }
            return final_score, risk_factors
        except Exception as e:
            # Fallback an toàn: ưu tiên đánh giá rủi ro cao khi có lỗi
            logger.error(f"Error analyzing transaction: {str(e)}")
            return 0.8, {"error": str(e)}
