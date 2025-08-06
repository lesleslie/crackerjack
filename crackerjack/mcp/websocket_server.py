from .websocket import WebSocketServer, main

__all__ = ["main", "WebSocketServer"]


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8675
    main(port)
