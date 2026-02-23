#!/usr/bin/env python3

import os
import time


def generate_ulid() -> str:

    try:
        from dhruva import generate as generate_ulid_impl

        return generate_ulid_impl()
    except ImportError:
        timestamp_ms = int(time.time() * 1000)
        timestamp_bytes = timestamp_ms.to_bytes(6, byteorder="big")

        randomness = os.urandom(10)

        ulid_bytes = timestamp_bytes + randomness

        alphabet = "0123456789abcdefghjkmnpqrstvwxyz"

        def b32_encode(data):
            return "".join([alphabet[(b >> 35) & 31] for b in data])

        return b32_encode(ulid_bytes)


def is_valid_ulid(value: str) -> bool:
    if len(value) != 26:
        return False
    return all(c in "0123456789abcdefghjkmnpqrstvwxyz" for c in value)


__all__ = [
    "generate_ulid",
    "is_valid_ulid",
]
