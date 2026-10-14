"""
services/payment.py — mirrors internal/services/payment.go
Verifies Razorpay payment signatures with HMAC-SHA256 + constant-time compare,
exactly as the Go PaymentService does.
"""
import hashlib
import hmac


class PaymentService:
    def __init__(self, key_secret: str) -> None:
        self._key_secret = key_secret

    def verify_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        signature: str,
    ) -> bool:
        """
        Returns True only if the signature matches what Razorpay would have
        produced for this order_id + payment_id pair.
        Mirrors Go's subtle.ConstantTimeCompare to prevent timing attacks.
        """
        if not all([self._key_secret, razorpay_order_id, razorpay_payment_id, signature]):
            return False

        payload  = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            self._key_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # hmac.compare_digest is constant-time — mirrors Go's subtle.ConstantTimeCompare
        return hmac.compare_digest(expected, signature)