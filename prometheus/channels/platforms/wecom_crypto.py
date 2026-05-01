from __future__ import annotations

import base64
import hashlib
import logging
import struct
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from Crypto.Cipher import AES
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


def _pkcs7_unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    return data[:-pad_len]


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def encrypt(message: str, key: str) -> str:
    if not CRYPTO_AVAILABLE:
        logger.error("pycryptodome 未安装: pip install pycryptodome")
        raise ImportError("pycryptodome required")
    aes_key = base64.b64decode(key + "=")
    aes_key = aes_key[:32]
    nonce = struct.pack(">I", int(time.time()))
    msg_bytes = message.encode("utf-8")
    msg_len = struct.pack(">I", len(msg_bytes))
    plaintext = nonce + msg_len + msg_bytes
    plaintext = _pkcs7_pad(plaintext)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    ciphertext = cipher.encrypt(plaintext)
    return base64.b64encode(ciphertext).decode("utf-8")


def decrypt(encrypted: str, key: str) -> str:
    if not CRYPTO_AVAILABLE:
        logger.error("pycryptodome 未安装: pip install pycryptodome")
        raise ImportError("pycryptodome required")
    aes_key = base64.b64decode(key + "=")
    aes_key = aes_key[:32]
    ciphertext = base64.b64decode(encrypted)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    plaintext = cipher.decrypt(ciphertext)
    plaintext = _pkcs7_unpad(plaintext)
    msg_len = struct.unpack(">I", plaintext[4:8])[0]
    message = plaintext[8 : 8 + msg_len].decode("utf-8")
    return message


def verify_signature(signature: str, timestamp: str, nonce: str, token: str) -> bool:
    if not token:
        return False
    items = [token, timestamp, nonce]
    items.sort()
    joined = "".join(items)
    calculated = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return calculated == signature
