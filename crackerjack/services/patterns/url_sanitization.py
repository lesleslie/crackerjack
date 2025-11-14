"""URL sanitization patterns for security."""

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "sanitize_localhost_urls": ValidatedPattern(
        name="sanitize_localhost_urls",
        pattern=r"https?: //localhost: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize localhost URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //localhost: 8000/api/test", "[INTERNAL_URL]"),
            ("https: //localhost: 3000/dashboard", "[INTERNAL_URL]"),
            (
                "Visit http: //localhost: 8080/admin for details",
                "Visit [INTERNAL_URL] for details",
            ),
            ("https: //example.com/test", "https: //example.com/test"),
        ],
    ),
    "sanitize_127_urls": ValidatedPattern(
        name="sanitize_127_urls",
        pattern=r"https?: //127\.0\.0\.1: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize 127.0.0.1 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //127.0.0.1: 8000/api", "[INTERNAL_URL]"),
            ("https: //127.0.0.1: 3000/test", "[INTERNAL_URL]"),
            ("Connect to http: //127.0.0.1: 5000/status", "Connect to [INTERNAL_URL]"),
            (
                "https: //192.168.1.1: 8080/test",
                "https: //192.168.1.1: 8080/test",
            ),
        ],
    ),
    "sanitize_any_localhost_urls": ValidatedPattern(
        name="sanitize_any_localhost_urls",
        pattern=r"https?: //0\.0\.0\.0: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize 0.0.0.0 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //0.0.0.0: 8000/api", "[INTERNAL_URL]"),
            ("https: //0.0.0.0: 3000/test", "[INTERNAL_URL]"),
            ("https: //1.1.1.1: 8080/test", "https: //1.1.1.1: 8080/test"),
        ],
    ),
    "sanitize_ws_localhost_urls": ValidatedPattern(
        name="sanitize_ws_localhost_urls",
        pattern=r"ws: //localhost: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize WebSocket localhost URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("ws: //localhost: 8675/websocket", "[INTERNAL_URL]"),
            ("ws: //localhost: 3000/socket", "[INTERNAL_URL]"),
            ("Connect to ws: //localhost: 8000/ws", "Connect to [INTERNAL_URL]"),
            (
                "wss: //example.com: 443/socket",
                "wss: //example.com: 443/socket",
            ),
        ],
    ),
    "sanitize_ws_127_urls": ValidatedPattern(
        name="sanitize_ws_127_urls",
        pattern=r"ws: //127\.0\.0\.1: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize WebSocket 127.0.0.1 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("ws: //127.0.0.1: 8675/websocket", "[INTERNAL_URL]"),
            ("ws: //127.0.0.1: 3000/socket", "[INTERNAL_URL]"),
            (
                "ws: //192.168.1.1: 8080/socket",
                "ws: //192.168.1.1: 8080/socket",
            ),
        ],
    ),
    "sanitize_simple_localhost_urls": ValidatedPattern(
        name="sanitize_simple_localhost_urls",
        pattern=r"http: //localhost[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize simple localhost URLs without explicit ports for security",
        global_replace=True,
        test_cases=[
            ("http: //localhost/api/test", "[INTERNAL_URL]"),
            ("http: //localhost/dashboard", "[INTERNAL_URL]"),
            ("Visit http: //localhost/admin", "Visit [INTERNAL_URL]"),
            (
                "https: //localhost: 443/test",
                "https: //localhost: 443/test",
            ),
        ],
    ),
    "sanitize_simple_ws_localhost_urls": ValidatedPattern(
        name="sanitize_simple_ws_localhost_urls",
        pattern=r"ws: //localhost[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize simple WebSocket localhost URLs without explicit ports"
        " for security",
        global_replace=True,
        test_cases=[
            ("ws: //localhost/websocket", "[INTERNAL_URL]"),
            ("ws: //localhost/socket", "[INTERNAL_URL]"),
            ("Connect to ws: //localhost/ws", "Connect to [INTERNAL_URL]"),
            (
                "wss: //localhost: 443/socket",
                "wss: //localhost: 443/socket",
            ),
        ],
    ),
}
