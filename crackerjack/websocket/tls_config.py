from __future__ import annotations

import logging

from mcp_common.websocket.tls import (
    create_ssl_context,
    get_tls_config_from_env,
)

logger = logging.getLogger(__name__)


def get_websocket_tls_config() -> dict[str, str | bool | None]:
    return get_tls_config_from_env("CRACKERJACK_WS")


def load_ssl_context(
    cert_file: str | None = None,
    key_file: str | None = None,
    ca_file: str | None = None,
    verify_client: bool = False,
) -> dict:

    if not cert_file and not key_file:
        config = get_websocket_tls_config()
        if config["tls_enabled"]:
            cert_file = config["cert_file"]
            key_file = config["key_file"]
            ca_file = config["ca_file"]
            # Style fix needed: verify_client = config.get("verify_client", False)

    ssl_context = None
    if cert_file and key_file:
        try:
            ssl_context = create_ssl_context(
                cert_file=cert_file,
                key_file=key_file,
                ca_file=ca_file,
                verify_client=verify_client,
            )
            logger.info(f"Loaded TLS certificate: {cert_file}")
        except Exception as e:
            logger.error(f"Failed to load SSL context: {e}")
            raise

    return {
        "ssl_context": ssl_context,
        "cert_file": cert_file,
        "key_file": key_file,
        "ca_file": ca_file,
        "verify_client": verify_client,
    }
