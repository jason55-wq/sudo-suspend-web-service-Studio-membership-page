from __future__ import annotations

import hashlib
import json
import os
import random
import string
from datetime import datetime
from typing import Any
from urllib.parse import quote


class PaymentServiceError(RuntimeError):
    pass


def _bool_from_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class PaymentService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.provider = os.environ.get("PAYMENT_PROVIDER", "ecpay").strip().lower()

    def build_checkout(self, order, product) -> dict[str, Any]:
        if self.provider != "ecpay":
            raise PaymentServiceError(
                "PAYMENT_PROVIDER is currently supported only for ecpay."
            )

        merchant_id = os.environ.get("ECPAY_MERCHANT_ID", "").strip()
        hash_key = os.environ.get("ECPAY_HASH_KEY", "").strip()
        hash_iv = os.environ.get("ECPAY_HASH_IV", "").strip()
        if not merchant_id or not hash_key or not hash_iv:
            raise PaymentServiceError("ECPay environment variables are not configured.")

        merchant_trade_no = order.merchant_trade_no or self._generate_merchant_trade_no(order.id)
        return_url = f"{self.base_url}/payment/notify"
        client_back_url = f"{self.base_url}/payment/return"
        now = datetime.now().astimezone()
        trade_date = now.strftime("%Y/%m/%d %H:%M:%S")
        item_name = product.name[:50]
        total_amount = int(product.price or 0)
        fields = {
            "ChoosePayment": "ALL",
            "ClientBackURL": client_back_url,
            "EncryptType": 1,
            "ItemName": item_name,
            "MerchantID": merchant_id,
            "MerchantTradeDate": trade_date,
            "MerchantTradeNo": merchant_trade_no,
            "PaymentType": "aio",
            "ReturnURL": return_url,
            "TradeDesc": "Studio membership purchase",
            "TotalAmount": total_amount,
        }
        fields["CheckMacValue"] = self._ecpay_check_mac_value(fields, hash_key, hash_iv)
        action = self._ecpay_checkout_url()
        return {
            "action": action,
            "method": "post",
            "fields": fields,
            "merchant_trade_no": merchant_trade_no,
            "provider": "ecpay",
        }

    def verify_notification(self, form_data: dict[str, Any]) -> bool:
        if self.provider != "ecpay":
            raise PaymentServiceError(
                "PAYMENT_PROVIDER is currently supported only for ecpay."
            )

        hash_key = os.environ.get("ECPAY_HASH_KEY", "").strip()
        hash_iv = os.environ.get("ECPAY_HASH_IV", "").strip()
        if not hash_key or not hash_iv:
            raise PaymentServiceError("ECPay environment variables are not configured.")

        provided = str(form_data.get("CheckMacValue", "")).strip().upper()
        if not provided:
            return False

        expected = self._ecpay_check_mac_value(
            {key: value for key, value in form_data.items() if key != "CheckMacValue"},
            hash_key,
            hash_iv,
        )
        return provided == expected

    def parse_notification(self, form_data: dict[str, Any], raw_payload: str | None = None) -> dict[str, Any]:
        payment_date = form_data.get("PaymentDate") or form_data.get("TradeDate")
        if isinstance(payment_date, str):
            parsed_payment_date = payment_date
        else:
            parsed_payment_date = None

        order_info = {
            "provider": "ecpay",
            "merchant_trade_no": str(form_data.get("MerchantTradeNo", "")).strip(),
            "gateway_trade_no": str(form_data.get("TradeNo", "")).strip(),
            "trade_status": str(form_data.get("TradeStatus", "")).strip(),
            "trade_amount": form_data.get("TradeAmt"),
            "payment_date": parsed_payment_date,
            "raw_payload": raw_payload or json.dumps(form_data, ensure_ascii=False),
        }
        return order_info

    def _ecpay_checkout_url(self) -> str:
        if _bool_from_env(os.environ.get("ECPAY_STAGE")):
            return "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        return "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"

    def _generate_merchant_trade_no(self, order_id: int) -> str:
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"OD{order_id:010d}{suffix}"[:20]

    def _ecpay_check_mac_value(self, fields: dict[str, Any], hash_key: str, hash_iv: str) -> str:
        filtered = {
            key: value
            for key, value in fields.items()
            if key != "CheckMacValue" and value is not None and str(value) != ""
        }
        sorted_pairs = []
        for key in sorted(filtered):
            sorted_pairs.append(f"{key}={filtered[key]}")
        raw = f"HashKey={hash_key}&" + "&".join(sorted_pairs) + f"&HashIV={hash_iv}"
        encoded = quote(raw, safe="-_.!*()").lower()
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()
