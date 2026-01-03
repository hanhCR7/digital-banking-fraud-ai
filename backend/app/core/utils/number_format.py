from decimal import Decimal, ROUND_HALF_UP
from typing import Union


CURRENCY_FORMATS = {
    "USD": {
        "symbol": "$",
        "decimal_places": 2,
        "symbol_position": "before",
    },
    "EUR": {
        "symbol": "€",
        "decimal_places": 2,
        "symbol_position": "before",
    },
    "GBP": {
        "symbol": "£",
        "decimal_places": 2,
        "symbol_position": "before",
    },
    "KES": {
        "symbol": "KSh",
        "decimal_places": 2,
        "symbol_position": "before",
    },
    "VND": {
        "symbol": "₫",
        "decimal_places": 0,
        "symbol_position": "after",
    },
}

def format_currency(
    amount: Union[Decimal, float, int, str],
    currency: str,
) -> str:
    """
    Định dạng số tiền theo chuẩn tiền tệ (USD / EUR / GBP / KES / VND)
    - Dùng Decimal (tránh sai số)
    - Làm tròn ROUND_HALF_UP
    - Có dấu phân cách hàng nghìn
    - Có ký hiệu tiền tệ
    """
    try:
        currency = currency.upper()
        if currency not in CURRENCY_FORMATS:
            raise ValueError(f"Unsupported currency: {currency}")
        config = CURRENCY_FORMATS[currency]
        decimal_amount = Decimal(str(amount))
        # Làm tròn theo số chữ số thập phân
        quantize_value = (
            "1" if config["decimal_places"] == 0
            else f"1.{'0' * config['decimal_places']}"
        )
        decimal_amount = decimal_amount.quantize(
            Decimal(quantize_value),
            rounding=ROUND_HALF_UP,
        )
        # Format số
        format_str = f",.{config['decimal_places']}f"
        formatted_number = format(decimal_amount, format_str)
        # Gắn ký hiệu tiền
        if config["symbol_position"] == "before":
            return f"{config['symbol']}{formatted_number}"
        return f"{formatted_number} {config['symbol']}"
    except Exception:
        return str(amount)

def parse_decimal(amount: Union[str, float, int, Decimal]) -> Decimal:
    """
    Chuẩn hoá giá trị tiền về Decimal để xử lý nghiệp vụ.
    Hỗ trợ:
    - "$1,234.56"
    - "€9,876.54"
    - "£1,000.00"
    - "KSh1,234.50"
    - "1,000,000 ₫"
    """
    try:
        if isinstance(amount, Decimal):
            return amount
        if isinstance(amount, str):
            for symbol in ["$", "€", "£", "KSh", "₫", ","]:
                amount = amount.replace(symbol, "")
            amount = amount.strip()
        return Decimal(str(amount))
    except Exception:
        raise ValueError(f"Could not convert '{amount}' to Decimal")

