"""Data factories for generating test data for session-mgmt-mcp tests.

Uses factory_boy and faker to generate realistic test data for:
- Session management
- Reflections and conversations
- User data
- Project structures
"""

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import factory
from faker import Faker

fake = Faker()


class SessionDataFactory(factory.Factory):
    """Factory for session management test data."""

    class Meta:
        model = dict

    session_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    project_name = factory.LazyAttribute(lambda obj: fake.slug())
    working_directory = factory.LazyAttribute(
        lambda obj: f"/tmp/test-projects/{obj.project_name}",
    )
    start_time = factory.LazyFunction(datetime.now)
    end_time = factory.LazyAttribute(
        lambda obj: obj.start_time + timedelta(hours=random.randint(1, 8)),
    )
    status = factory.Iterator(["active", "completed", "failed", "interrupted"])
    quality_score = factory.LazyAttribute(lambda obj: random.uniform(0.6, 0.98))

    # Session configuration
    auto_checkpoint = factory.Iterator([True, False])
    checkpoint_frequency = factory.Iterator([300, 600, 900, 1800])  # seconds
    trusted_operations = factory.LazyFunction(lambda: set())

    # Health metrics
    health_checks = factory.LazyFunction(
        lambda: {
            "database": random.choice([True, False]),
            "permissions": random.choice([True, False]),
            "toolkit_integration": random.choice([True, False]),
            "uv_available": random.choice([True, False]),
        },
    )


class ReflectionDataFactory(factory.Factory):
    """Factory for reflection and conversation test data."""

    class Meta:
        model = dict

    id = factory.Sequence(lambda n: n)
    content = factory.LazyAttribute(lambda obj: fake.paragraph(nb_sentences=3))
    project = factory.LazyAttribute(lambda obj: fake.slug())
    timestamp = factory.LazyFunction(
        lambda: datetime.now()
        - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        ),
    )
    tags = factory.LazyFunction(
        lambda: random.sample(
            [
                "authentication",
                "database",
                "api",
                "frontend",
                "backend",
                "testing",
                "deployment",
                "security",
                "performance",
                "bug-fix",
                "feature",
                "refactoring",
                "documentation",
                "monitoring",
            ],
            k=random.randint(1, 4),
        ),
    )

    # Embedding simulation (384-dimensional vector)
    embedding = factory.LazyFunction(
        lambda: [random.uniform(-1, 1) for _ in range(384)],
    )

    # Conversation metadata
    conversation_length = factory.LazyAttribute(lambda obj: random.randint(100, 2000))
    tool_calls_count = factory.LazyAttribute(lambda obj: random.randint(0, 20))
    error_count = factory.LazyAttribute(lambda obj: random.randint(0, 3))


class UserDataFactory(factory.Factory):
    """Factory for user-related test data."""

    class Meta:
        model = dict

    user_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    email = factory.LazyAttribute(lambda obj: fake.email())
    username = factory.LazyAttribute(lambda obj: fake.user_name())
    full_name = factory.LazyAttribute(lambda obj: fake.name())

    # User preferences
    preferred_language = factory.Iterator(
        ["python", "javascript", "typescript", "go", "rust"],
    )
    timezone = factory.LazyAttribute(lambda obj: fake.timezone())
    theme = factory.Iterator(["light", "dark", "auto"])

    # Activity data
    last_active = factory.LazyFunction(
        lambda: datetime.now() - timedelta(hours=random.randint(0, 72)),
    )
    session_count = factory.LazyAttribute(lambda obj: random.randint(1, 100))
    total_interactions = factory.LazyAttribute(lambda obj: random.randint(10, 1000))


class ProjectDataFactory(factory.Factory):
    """Factory for project structure test data."""

    class Meta:
        model = dict

    name = factory.LazyAttribute(lambda obj: fake.slug())
    path = factory.LazyAttribute(lambda obj: f"/Users/test/Projects/{obj.name}")
    type = factory.Iterator(
        ["python", "javascript", "typescript", "go", "rust", "java"],
    )
    framework = factory.LazyAttribute(
        lambda obj: {
            "python": random.choice(["fastapi", "django", "flask", "starlette"]),
            "javascript": random.choice(["express", "nextjs", "react", "vue"]),
            "typescript": random.choice(["nestjs", "nextjs", "angular"]),
            "go": random.choice(["gin", "echo", "fiber"]),
            "rust": random.choice(["axum", "warp", "rocket"]),
            "java": random.choice(["spring", "quarkus", "micronaut"]),
        }.get(obj.type, "unknown"),
    )

    # Project health metrics
    has_tests = factory.Iterator([True, False])
    has_docs = factory.Iterator([True, False])
    has_ci = factory.Iterator([True, False])
    test_coverage = factory.LazyAttribute(
        lambda obj: random.uniform(0.3, 0.95) if obj.has_tests else 0.0,
    )

    # File structure
    file_count = factory.LazyAttribute(lambda obj: random.randint(5, 200))
    line_count = factory.LazyAttribute(lambda obj: random.randint(100, 50000))

    # Git information
    git_initialized = factory.Iterator([True, False])
    commit_count = factory.LazyAttribute(
        lambda obj: random.randint(1, 500) if obj.git_initialized else 0,
    )
    branch_name = factory.Iterator(["main", "master", "develop", "feature/test"])

    # Dependencies
    dependency_count = factory.LazyAttribute(lambda obj: random.randint(0, 50))
    outdated_dependencies = factory.LazyAttribute(
        lambda obj: random.randint(0, obj.dependency_count // 3),
    )


class DatabaseTestDataFactory(factory.Factory):
    """Factory for database-related test data."""

    class Meta:
        model = dict

    database_type = factory.Iterator(["duckdb", "sqlite", "postgresql"])
    connection_string = factory.LazyAttribute(
        lambda obj: f"{obj.database_type}://test.db",
    )
    table_count = factory.LazyAttribute(lambda obj: random.randint(1, 20))
    record_count = factory.LazyAttribute(lambda obj: random.randint(0, 10000))

    # Performance metrics
    query_time_avg = factory.LazyAttribute(lambda obj: random.uniform(0.001, 0.1))
    connection_time = factory.LazyAttribute(lambda obj: random.uniform(0.01, 0.5))

    # Health status
    is_healthy = factory.Iterator([True, False])
    last_backup = factory.LazyFunction(
        lambda: datetime.now() - timedelta(days=random.randint(0, 7)),
    )


class ErrorDataFactory(factory.Factory):
    """Factory for error and exception test data."""

    class Meta:
        model = dict

    error_type = factory.Iterator(
        [
            "ConnectionError",
            "TimeoutError",
            "ValidationError",
            "PermissionError",
            "FileNotFoundError",
            "DatabaseError",
        ],
    )
    error_message = factory.LazyAttribute(lambda obj: fake.sentence())
    stack_trace = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    timestamp = factory.LazyFunction(datetime.now)
    context = factory.LazyFunction(
        lambda: {
            "function": fake.word(),
            "line_number": random.randint(1, 1000),
            "file_path": f"/src/{fake.file_name()}",
        },
    )

    # Error categorization
    severity = factory.Iterator(["low", "medium", "high", "critical"])
    is_recoverable = factory.Iterator([True, False])
    retry_count = factory.LazyAttribute(lambda obj: random.randint(0, 5))


class PerformanceDataFactory(factory.Factory):
    """Factory for performance testing data."""

    class Meta:
        model = dict

    operation_name = factory.Iterator(
        [
            "database_query",
            "api_call",
            "file_read",
            "network_request",
            "computation",
            "memory_allocation",
        ],
    )
    duration_ms = factory.LazyAttribute(lambda obj: random.uniform(1, 5000))
    memory_usage_mb = factory.LazyAttribute(lambda obj: random.uniform(1, 500))
    cpu_usage_percent = factory.LazyAttribute(lambda obj: random.uniform(0, 100))

    # Concurrency data
    concurrent_requests = factory.LazyAttribute(lambda obj: random.randint(1, 100))
    success_rate = factory.LazyAttribute(lambda obj: random.uniform(0.8, 1.0))
    error_rate = factory.LazyAttribute(lambda obj: 1.0 - obj.success_rate)

    # Benchmarking
    baseline_duration = factory.LazyAttribute(lambda obj: obj.duration_ms * 0.9)
    performance_regression = factory.LazyAttribute(
        lambda obj: obj.duration_ms > obj.baseline_duration * 1.1,
    )


# Specialized Factories for Complex Scenarios


class LargeDatasetFactory(factory.Factory):
    """Factory for large dataset testing."""

    class Meta:
        model = dict

    @classmethod
    def generate_large_reflection_dataset(cls, count: int = 1000) -> list[dict]:
        """Generate large reflection dataset for performance testing."""
        return ReflectionDataFactory.build_batch(count)

    @classmethod
    def generate_project_portfolio(cls, project_count: int = 50) -> list[dict]:
        """Generate portfolio of projects for testing."""
        return ProjectDataFactory.build_batch(project_count)

    @classmethod
    def generate_conversation_history(cls, days: int = 30) -> list[dict]:
        """Generate conversation history over specified days."""
        reflections = []
        for day in range(days):
            day_reflections = ReflectionDataFactory.build_batch(random.randint(1, 10))
            for reflection in day_reflections:
                reflection["timestamp"] = datetime.now() - timedelta(days=day)
            reflections.extend(day_reflections)
        return reflections


class SecurityTestDataFactory(factory.Factory):
    """Factory for security testing data."""

    class Meta:
        model = dict

    # Authentication data
    valid_token = factory.LazyFunction(lambda: str(uuid.uuid4()))
    invalid_token = factory.LazyFunction(lambda: "invalid_" + str(uuid.uuid4()))
    expired_token = factory.LazyFunction(lambda: "expired_" + str(uuid.uuid4()))

    # Permission data
    operation = factory.Iterator(
        [
            "read_reflections",
            "write_reflections",
            "delete_reflections",
            "session_init",
            "session_checkpoint",
            "session_end",
            "database_access",
            "file_system_access",
        ],
    )
    permission_level = factory.Iterator(["none", "read", "write", "admin"])

    # Security threats
    malicious_input = factory.Iterator(
        [
            "'; DROP TABLE reflections; --",
            "<script>alert('xss')</script>",
            "../../../../etc/passwd",
            "rm -rf /*",
        ],
    )

    # Rate limiting
    request_rate = factory.LazyAttribute(lambda obj: random.randint(1, 1000))
    rate_limit_threshold = factory.Iterator([10, 50, 100, 500])


# Utility functions for test data generation


def create_test_project_structure(base_path: Path, project_data: dict) -> Path:
    """Create realistic project structure on filesystem for testing."""
    project_path = base_path / project_data["name"]
    project_path.mkdir(parents=True, exist_ok=True)

    # Create common files
    files_to_create = {
        "README.md": f"# {project_data['name']}\\n\\nTest project for session management.",
        "pyproject.toml": f"""[project]
name = "{project_data["name"]}"
version = "0.1.0"
description = "Test project"
""",
        "src/main.py": "print('Hello from test project')",
        "tests/test_main.py": "def test_main(): assert True",
        ".gitignore": "*.pyc\\n__pycache__/\\n.env",
    }

    for file_path, content in files_to_create.items():
        full_path = project_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    return project_path


def generate_realistic_embedding(text: str) -> list[float]:
    """Generate pseudo-realistic embedding for text (for testing)."""
    # Simple hash-based embedding simulation
    import hashlib

    hash_obj = hashlib.md5(text.encode())
    hash_hex = hash_obj.hexdigest()

    # Convert hash to 384-dimensional vector
    embedding = []
    for i in range(0, len(hash_hex), 2):
        # Convert hex pairs to floats between -1 and 1
        hex_pair = hash_hex[i : i + 2]
        value = int(hex_pair, 16) / 255.0 * 2 - 1
        embedding.append(value)

    # Pad or truncate to 384 dimensions
    while len(embedding) < 384:
        embedding.extend(embedding[: 384 - len(embedding)])

    return embedding[:384]
