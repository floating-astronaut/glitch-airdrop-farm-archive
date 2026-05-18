"""Encrypted at-rest wallet keys. AEAD via libsodium secretbox."""

from __future__ import annotations

import base64
import secrets

from eth_account import Account
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random

from farm.config import settings


def _box() -> SecretBox:
    key = base64.b64decode(settings.wallet_key)
    if len(key) != 32:
        raise ValueError("FARM_WALLET_KEY must decode to 32 bytes")
    return SecretBox(key)


def seal(privkey_hex: str) -> bytes:
    """Encrypt a 0x-hex private key. Returns nonce||ciphertext bytes."""
    nonce = nacl_random(SecretBox.NONCE_SIZE)
    return _box().encrypt(privkey_hex.encode(), nonce=nonce)


def unseal(blob: bytes) -> str:
    """Decrypt previously sealed key."""
    return _box().decrypt(blob).decode()


def new_evm_wallet() -> tuple[str, str]:
    """(address, privkey_hex). Independent 256-bit random per wallet."""
    Account.enable_unaudited_hdwallet_features()
    acct = Account.create(secrets.token_bytes(32))
    return acct.address, acct.key.hex()
