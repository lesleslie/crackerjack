#!/usr/bin/env python3
"""Stateless/Serverless Mode for Session Management MCP Server.

Enables request-scoped sessions with external storage backends (Redis, S3, DynamoDB).
Allows the session management server to operate in cloud/serverless environments.
"""

import asyncio
import gzip
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class SessionState:
    """Represents complete session state for serialization."""

    session_id: str
    user_id: str
    project_id: str
    created_at: str
    last_activity: str
    permissions: list[str]
    conversation_history: list[dict[str, Any]]
    reflection_data: dict[str, Any]
    app_monitoring_state: dict[str, Any]
    llm_provider_configs: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Create from dictionary."""
        return cls(**data)

    def get_compressed_size(self) -> int:
        """Get compressed size of session state."""
        serialized = json.dumps(self.to_dict())
        compressed = gzip.compress(serialized.encode("utf-8"))
        return len(compressed)


class SessionStorage(ABC):
    """Abstract base class for session storage backends."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.logger = logging.getLogger(f"serverless.{self.__class__.__name__.lower()}")

    @abstractmethod
    async def store_session(
        self,
        session_state: SessionState,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store session state with optional TTL."""

    @abstractmethod
    async def retrieve_session(self, session_id: str) -> SessionState | None:
        """Retrieve session state by ID."""

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete session state."""

    @abstractmethod
    async def list_sessions(
        self,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """List session IDs matching criteria."""

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions, return count removed."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if storage backend is available."""


class RedisStorage(SessionStorage):
    """Redis-based session storage."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 6379)
        self.db = config.get("db", 0)
        self.password = config.get("password")
        self.key_prefix = config.get("key_prefix", "session_mgmt:")
        self._redis = None

    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=False,  # We handle encoding ourselves
                )
            except ImportError:
                msg = "Redis package not installed. Install with: pip install redis"
                raise ImportError(
                    msg,
                )
        return self._redis

    def _get_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.key_prefix}session:{session_id}"

    def _get_index_key(self, index_type: str) -> str:
        """Get Redis key for index."""
        return f"{self.key_prefix}index:{index_type}"

    async def store_session(
        self,
        session_state: SessionState,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store session in Redis with optional TTL."""
        try:
            redis_client = await self._get_redis()

            # Serialize and compress session state
            serialized = json.dumps(session_state.to_dict())
            compressed = gzip.compress(serialized.encode("utf-8"))

            # Store session data
            key = self._get_key(session_state.session_id)
            await redis_client.set(key, compressed, ex=ttl_seconds)

            # Update indexes
            user_index_key = self._get_index_key(f"user:{session_state.user_id}")
            project_index_key = self._get_index_key(
                f"project:{session_state.project_id}",
            )

            await redis_client.sadd(user_index_key, session_state.session_id)
            await redis_client.sadd(project_index_key, session_state.session_id)

            # Set TTL on indexes if specified
            if ttl_seconds:
                await redis_client.expire(user_index_key, ttl_seconds)
                await redis_client.expire(project_index_key, ttl_seconds)

            return True

        except Exception as e:
            self.logger.exception(
                f"Failed to store session {session_state.session_id}: {e}",
            )
            return False

    async def retrieve_session(self, session_id: str) -> SessionState | None:
        """Retrieve session from Redis."""
        try:
            redis_client = await self._get_redis()
            key = self._get_key(session_id)

            compressed_data = await redis_client.get(key)
            if not compressed_data:
                return None

            # Decompress and deserialize
            serialized = gzip.decompress(compressed_data).decode("utf-8")
            session_data = json.loads(serialized)

            return SessionState.from_dict(session_data)

        except Exception as e:
            self.logger.exception(f"Failed to retrieve session {session_id}: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis."""
        try:
            redis_client = await self._get_redis()

            # Get session to find user/project for index cleanup
            session_state = await self.retrieve_session(session_id)

            # Delete session data
            key = self._get_key(session_id)
            deleted = await redis_client.delete(key)

            # Clean up indexes
            if session_state:
                user_index_key = self._get_index_key(f"user:{session_state.user_id}")
                project_index_key = self._get_index_key(
                    f"project:{session_state.project_id}",
                )

                await redis_client.srem(user_index_key, session_id)
                await redis_client.srem(project_index_key, session_id)

            return deleted > 0

        except Exception as e:
            self.logger.exception(f"Failed to delete session {session_id}: {e}")
            return False

    async def list_sessions(
        self,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """List sessions by user or project."""
        try:
            redis_client = await self._get_redis()

            if user_id:
                index_key = self._get_index_key(f"user:{user_id}")
                session_ids = await redis_client.smembers(index_key)
                return [
                    sid.decode("utf-8") if isinstance(sid, bytes) else sid
                    for sid in session_ids
                ]

            if project_id:
                index_key = self._get_index_key(f"project:{project_id}")
                session_ids = await redis_client.smembers(index_key)
                return [
                    sid.decode("utf-8") if isinstance(sid, bytes) else sid
                    for sid in session_ids
                ]

            # List all sessions (expensive operation)
            pattern = self._get_key("*")
            keys = await redis_client.keys(pattern)
            return [
                key.decode("utf-8").split(":")[-1]
                if isinstance(key, bytes)
                else key.split(":")[-1]
                for key in keys
            ]

        except Exception as e:
            self.logger.exception(f"Failed to list sessions: {e}")
            return []

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        # Redis automatically handles TTL expiration
        # This method could scan for orphaned index entries
        try:
            redis_client = await self._get_redis()

            # Scan for index entries that point to non-existent sessions
            cleaned = 0
            index_pattern = self._get_index_key("*")
            index_keys = await redis_client.keys(index_pattern)

            for index_key in index_keys:
                if isinstance(index_key, bytes):
                    index_key = index_key.decode("utf-8")

                session_ids = await redis_client.smembers(index_key)
                for session_id in session_ids:
                    if isinstance(session_id, bytes):
                        session_id = session_id.decode("utf-8")

                    session_key = self._get_key(session_id)
                    exists = await redis_client.exists(session_key)

                    if not exists:
                        await redis_client.srem(index_key, session_id)
                        cleaned += 1

            return cleaned

        except Exception as e:
            self.logger.exception(f"Failed to cleanup expired sessions: {e}")
            return 0

    async def is_available(self) -> bool:
        """Check if Redis is available."""
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            return True
        except Exception:
            return False


class S3Storage(SessionStorage):
    """S3-based session storage."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.bucket_name = config.get("bucket_name", "session-mgmt-mcp")
        self.region = config.get("region", "us-east-1")
        self.key_prefix = config.get("key_prefix", "sessions/")
        self.access_key_id = config.get("access_key_id")
        self.secret_access_key = config.get("secret_access_key")
        self._s3_client = None

    async def _get_s3_client(self):
        """Get or create S3 client."""
        if self._s3_client is None:
            try:
                import boto3
                from botocore.client import Config

                session = boto3.Session(
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region,
                )

                self._s3_client = session.client(
                    "s3",
                    config=Config(retries={"max_attempts": 3}, max_pool_connections=50),
                )
            except ImportError:
                msg = "Boto3 package not installed. Install with: pip install boto3"
                raise ImportError(
                    msg,
                )

        return self._s3_client

    def _get_key(self, session_id: str) -> str:
        """Get S3 key for session."""
        return f"{self.key_prefix}{session_id}.json.gz"

    async def store_session(
        self,
        session_state: SessionState,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store session in S3."""
        try:
            s3_client = await self._get_s3_client()

            # Serialize and compress session state
            serialized = json.dumps(session_state.to_dict())
            compressed = gzip.compress(serialized.encode("utf-8"))

            # Prepare S3 object metadata
            metadata = {
                "user_id": session_state.user_id,
                "project_id": session_state.project_id,
                "created_at": session_state.created_at,
                "last_activity": session_state.last_activity,
            }

            # Set expiration if TTL specified
            expires = None
            if ttl_seconds:
                expires = datetime.utcnow() + timedelta(seconds=ttl_seconds)

            # Upload to S3
            key = self._get_key(session_state.session_id)

            put_args = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": compressed,
                "ContentType": "application/json",
                "ContentEncoding": "gzip",
                "Metadata": metadata,
            }

            if expires:
                put_args["Expires"] = expires

            # Execute in thread pool since boto3 is synchronous
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: s3_client.put_object(**put_args))

            return True

        except Exception as e:
            self.logger.exception(
                f"Failed to store session {session_state.session_id}: {e}",
            )
            return False

    async def retrieve_session(self, session_id: str) -> SessionState | None:
        """Retrieve session from S3."""
        try:
            s3_client = await self._get_s3_client()
            key = self._get_key(session_id)

            # Download from S3
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: s3_client.get_object(Bucket=self.bucket_name, Key=key),
            )

            # Decompress and deserialize
            compressed_data = response["Body"].read()
            serialized = gzip.decompress(compressed_data).decode("utf-8")
            session_data = json.loads(serialized)

            return SessionState.from_dict(session_data)

        except Exception as e:
            self.logger.exception(f"Failed to retrieve session {session_id}: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from S3."""
        try:
            s3_client = await self._get_s3_client()
            key = self._get_key(session_id)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: s3_client.delete_object(Bucket=self.bucket_name, Key=key),
            )

            return True

        except Exception as e:
            self.logger.exception(f"Failed to delete session {session_id}: {e}")
            return False

    async def list_sessions(
        self,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """List sessions in S3."""
        try:
            s3_client = await self._get_s3_client()

            # List objects with prefix
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=self.key_prefix,
                ),
            )

            session_ids = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                session_id = key.replace(self.key_prefix, "").replace(".json.gz", "")

                # Filter by user_id or project_id if specified
                if user_id or project_id:
                    # Get object metadata to filter
                    head_response = await loop.run_in_executor(
                        None,
                        lambda: s3_client.head_object(Bucket=self.bucket_name, Key=key),
                    )

                    metadata = head_response.get("Metadata", {})

                    if user_id and metadata.get("user_id") != user_id:
                        continue
                    if project_id and metadata.get("project_id") != project_id:
                        continue

                session_ids.append(session_id)

            return session_ids

        except Exception as e:
            self.logger.exception(f"Failed to list sessions: {e}")
            return []

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from S3."""
        try:
            s3_client = await self._get_s3_client()

            # S3 lifecycle policies handle expiration automatically
            # This could implement custom logic for old sessions

            now = datetime.utcnow()
            cleaned = 0

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=self.key_prefix,
                ),
            )

            for obj in response.get("Contents", []):
                # Check if object is expired (custom logic)
                last_modified = obj["LastModified"].replace(tzinfo=None)
                age_days = (now - last_modified).days

                if age_days > 30:  # Cleanup sessions older than 30 days
                    await loop.run_in_executor(
                        None,
                        lambda: s3_client.delete_object(
                            Bucket=self.bucket_name,
                            Key=obj["Key"],
                        ),
                    )
                    cleaned += 1

            return cleaned

        except Exception as e:
            self.logger.exception(f"Failed to cleanup expired sessions: {e}")
            return 0

    async def is_available(self) -> bool:
        """Check if S3 is available."""
        try:
            s3_client = await self._get_s3_client()

            # Test bucket access
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: s3_client.head_bucket(Bucket=self.bucket_name),
            )

            return True
        except Exception:
            return False


class LocalFileStorage(SessionStorage):
    """Local file-based session storage (for development/testing)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.storage_dir = Path(
            config.get("storage_dir", Path.home() / ".claude" / "data" / "sessions"),
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_file(self, session_id: str) -> Path:
        """Get file path for session."""
        return self.storage_dir / f"{session_id}.json.gz"

    async def store_session(
        self,
        session_state: SessionState,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store session in local file."""
        try:
            # Serialize and compress session state
            serialized = json.dumps(session_state.to_dict())
            compressed = gzip.compress(serialized.encode("utf-8"))

            # Write to file
            session_file = self._get_session_file(session_state.session_id)
            with open(session_file, "wb") as f:
                f.write(compressed)

            return True

        except Exception as e:
            self.logger.exception(
                f"Failed to store session {session_state.session_id}: {e}",
            )
            return False

    async def retrieve_session(self, session_id: str) -> SessionState | None:
        """Retrieve session from local file."""
        try:
            session_file = self._get_session_file(session_id)

            if not session_file.exists():
                return None

            # Read and decompress
            with open(session_file, "rb") as f:
                compressed_data = f.read()

            serialized = gzip.decompress(compressed_data).decode("utf-8")
            session_data = json.loads(serialized)

            return SessionState.from_dict(session_data)

        except Exception as e:
            self.logger.exception(f"Failed to retrieve session {session_id}: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session file."""
        try:
            session_file = self._get_session_file(session_id)

            if session_file.exists():
                session_file.unlink()
                return True

            return False

        except Exception as e:
            self.logger.exception(f"Failed to delete session {session_id}: {e}")
            return False

    async def list_sessions(
        self,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[str]:
        """List session files."""
        try:
            session_ids = []

            for session_file in self.storage_dir.glob("*.json.gz"):
                session_id = session_file.stem.replace(".json", "")

                # Filter by user_id or project_id if specified
                if user_id or project_id:
                    session_state = await self.retrieve_session(session_id)
                    if not session_state:
                        continue

                    if user_id and session_state.user_id != user_id:
                        continue
                    if project_id and session_state.project_id != project_id:
                        continue

                session_ids.append(session_id)

            return session_ids

        except Exception as e:
            self.logger.exception(f"Failed to list sessions: {e}")
            return []

    async def cleanup_expired_sessions(self) -> int:
        """Clean up old session files."""
        try:
            now = datetime.now()
            cleaned = 0

            for session_file in self.storage_dir.glob("*.json.gz"):
                # Check file age
                file_age = now - datetime.fromtimestamp(session_file.stat().st_mtime)

                if file_age.days > 7:  # Cleanup sessions older than 7 days
                    session_file.unlink()
                    cleaned += 1

            return cleaned

        except Exception as e:
            self.logger.exception(f"Failed to cleanup expired sessions: {e}")
            return 0

    async def is_available(self) -> bool:
        """Check if local storage is available."""
        return self.storage_dir.exists() and self.storage_dir.is_dir()


class ServerlessSessionManager:
    """Main session manager for serverless/stateless operation."""

    def __init__(self, storage_backend: SessionStorage) -> None:
        self.storage = storage_backend
        self.logger = logging.getLogger("serverless.session_manager")
        self.session_cache = {}  # In-memory cache for current request

    async def create_session(
        self,
        user_id: str,
        project_id: str,
        session_data: dict[str, Any] | None = None,
        ttl_hours: int = 24,
    ) -> str:
        """Create new session."""
        session_id = self._generate_session_id(user_id, project_id)

        session_state = SessionState(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            created_at=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat(),
            permissions=[],
            conversation_history=[],
            reflection_data={},
            app_monitoring_state={},
            llm_provider_configs={},
            metadata=session_data or {},
        )

        # Store with TTL
        ttl_seconds = ttl_hours * 3600
        success = await self.storage.store_session(session_state, ttl_seconds)

        if success:
            self.session_cache[session_id] = session_state
            return session_id
        msg = "Failed to create session"
        raise RuntimeError(msg)

    async def get_session(self, session_id: str) -> SessionState | None:
        """Get session state."""
        # Check cache first
        if session_id in self.session_cache:
            return self.session_cache[session_id]

        # Load from storage
        session_state = await self.storage.retrieve_session(session_id)
        if session_state:
            self.session_cache[session_id] = session_state

        return session_state

    async def update_session(
        self,
        session_id: str,
        updates: dict[str, Any],
        ttl_hours: int | None = None,
    ) -> bool:
        """Update session state."""
        session_state = await self.get_session(session_id)
        if not session_state:
            return False

        # Apply updates
        for key, value in updates.items():
            if hasattr(session_state, key):
                setattr(session_state, key, value)

        # Update last activity
        session_state.last_activity = datetime.now().isoformat()

        # Store updated state
        ttl_seconds = ttl_hours * 3600 if ttl_hours else None
        success = await self.storage.store_session(session_state, ttl_seconds)

        if success:
            self.session_cache[session_id] = session_state

        return success

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        # Remove from cache
        self.session_cache.pop(session_id, None)

        # Delete from storage
        return await self.storage.delete_session(session_id)

    async def list_user_sessions(self, user_id: str) -> list[str]:
        """List sessions for user."""
        return await self.storage.list_sessions(user_id=user_id)

    async def list_project_sessions(self, project_id: str) -> list[str]:
        """List sessions for project."""
        return await self.storage.list_sessions(project_id=project_id)

    async def cleanup_sessions(self) -> int:
        """Clean up expired sessions."""
        return await self.storage.cleanup_expired_sessions()

    def _generate_session_id(self, user_id: str, project_id: str) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        data = f"{user_id}:{project_id}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "cached_sessions": len(self.session_cache),
            "storage_backend": self.storage.__class__.__name__,
            "storage_config": {
                k: v for k, v in self.storage.config.items() if "key" not in k.lower()
            },
        }


class ServerlessConfigManager:
    """Manages configuration for serverless mode."""

    @staticmethod
    def load_config(config_path: str | None = None) -> dict[str, Any]:
        """Load serverless configuration."""
        default_config = {
            "storage_backend": "local",
            "session_ttl_hours": 24,
            "cleanup_interval_hours": 6,
            "backends": {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                    "db": 0,
                    "key_prefix": "session_mgmt:",
                },
                "s3": {
                    "bucket_name": "session-mgmt-mcp",
                    "region": "us-east-1",
                    "key_prefix": "sessions/",
                },
                "local": {
                    "storage_dir": str(Path.home() / ".claude" / "data" / "sessions"),
                },
            },
        }

        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except (OSError, json.JSONDecodeError):
                pass

        return default_config

    @staticmethod
    def create_storage_backend(config: dict[str, Any]) -> SessionStorage:
        """Create storage backend from config."""
        backend_type = config.get("storage_backend", "local")
        backend_config = config.get("backends", {}).get(backend_type, {})

        if backend_type == "redis":
            return RedisStorage(backend_config)
        if backend_type == "s3":
            return S3Storage(backend_config)
        if backend_type == "local":
            return LocalFileStorage(backend_config)
        msg = f"Unsupported storage backend: {backend_type}"
        raise ValueError(msg)

    @staticmethod
    async def test_storage_backends(config: dict[str, Any]) -> dict[str, bool]:
        """Test all configured storage backends."""
        results = {}

        for backend_name, backend_config in config.get("backends", {}).items():
            try:
                if backend_name == "redis":
                    storage = RedisStorage(backend_config)
                elif backend_name == "s3":
                    storage = S3Storage(backend_config)
                elif backend_name == "local":
                    storage = LocalFileStorage(backend_config)
                else:
                    results[backend_name] = False
                    continue

                results[backend_name] = await storage.is_available()

            except Exception:
                results[backend_name] = False

        return results
