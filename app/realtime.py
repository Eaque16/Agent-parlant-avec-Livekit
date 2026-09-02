"""Émission de jetons LiveKit éphémères et restreints à une room."""
import base64
import hashlib
import hmac
import json
import time


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_livekit_token(*, api_key: str, api_secret: str, identity: str,
                         room_name: str, ttl_seconds: int = 300) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": api_key, "sub": identity, "nbf": now - 5, "iat": now,
               "exp": now + min(max(ttl_seconds, 60), 600), "jti": f"{identity}-{now}",
               "video": {"roomJoin": True, "room": room_name, "canPublish": True, "canSubscribe": True},
               "metadata": json.dumps({"poc": True, "anonymous": True})}
    signing_input = ".".join((_b64(json.dumps(header, separators=(",", ":")).encode()),
                              _b64(json.dumps(payload, separators=(",", ":")).encode())))
    signature = hmac.new(api_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"
