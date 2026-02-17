______________________________________________________________________

title: Comprehensive Test Harness & Advanced Testing Strategies
owner: Quality Engineering Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
- Windows
  agents:
- qa-strategist
- python-pro
- javascript-pro
- golang-pro
- observability-incident-lead
  required_scripts:
- scripts/test_matrix.py
  risk: medium
  status: active
  id: 01K6EEQRQ3BDHZ1H0CJT2XC8S7
  category: development/testing
  tags:
- testing
- qa
- automation
- chaos-engineering
- property-based-testing
- contract-testing

______________________________________________________________________

## Comprehensive Test Harness & Advanced Testing Strategies

## Context

Modern applications require sophisticated testing approaches beyond basic unit and integration tests. This guide provides comprehensive test infrastructure, advanced testing strategies, and specialized testing techniques including chaos engineering, property-based testing, contract testing, mutation testing, and visual regression testing.

This tool consolidates and enhances `test-harness.md` and `advanced-testing-strategies.md`, providing production-ready test infrastructure and strategies.

## Requirements

- Testing framework for your stack (pytest, Jest, Go testing, etc.)
- CI/CD pipeline for automated test execution
- Access to test environments (staging, QA)
- Basic understanding of testing concepts (unit, integration, E2E)

## Inputs

- `$PROJECT_PATH` — repository under test
- `$STACK` — primary language/framework (python, node, go, rust, etc.)
- `$TEST_TYPES` — testing strategies to implement (unit, integration, property-based, chaos, etc.)
- `$COVERAGE_TARGET` — desired code coverage percentage (e.g., 80%)

## Outputs

- Complete test infrastructure (fixtures, factories, helpers)
- Test suites for selected testing strategies
- CI/CD integration configuration
- Coverage reports and quality metrics
- Test execution and maintenance documentation

______________________________________________________________________

## Part 1: Test Infrastructure & Fixtures

### Reusable Test Fixtures

**Python (pytest) fixtures:**

```python
# conftest.py - Shared fixtures across all tests
import pytest
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base
from app.models import User, Product


# Database fixtures
@pytest.fixture(scope="session")
def test_db_engine():
    """Session-scoped test database engine"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Function-scoped database session with automatic rollback"""
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# API client fixture
@pytest.fixture
def client(db_session) -> TestClient:
    """FastAPI test client with database override"""

    def get_db_override():
        yield db_session

    app.dependency_overrides[get_database] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# Authentication fixtures
@pytest.fixture
def auth_headers(db_session) -> dict:
    """Generate authentication headers for tests"""
    user = User(email="test@example.com", hashed_password=hash_password("testpass"))
    db_session.add(user)
    db_session.commit()

    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db_session) -> User:
    """Create admin user for testing"""
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    return user


# Mock external services
@pytest.fixture
def mock_payment_service(monkeypatch):
    """Mock external payment service"""

    class MockPaymentClient:
        def charge(self, amount: float, card_token: str):
            if amount > 10000:
                raise PaymentError("Amount exceeds limit")
            return {"transaction_id": "mock-txn-123", "status": "success"}

    mock_client = MockPaymentClient()
    monkeypatch.setattr("app.services.payment_client", mock_client)
    return mock_client


# Time-based fixtures
@pytest.fixture
def freeze_time():
    """Freeze time for deterministic testing"""
    import freezegun

    with freezegun.freeze_time("2025-01-15 12:00:00"):
        yield


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_files(tmp_path):
    """Auto-cleanup temporary files after tests"""
    yield
    # Cleanup runs after test completes
    import shutil

    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
```

**JavaScript/TypeScript (Jest) fixtures:**

```typescript
// test/fixtures.ts
import { PrismaClient } from '@prisma/client';
import { mockDeep, mockReset, DeepMockProxy } from 'jest-mock-extended';

// Database mock
export const prismaMock = mockDeep<PrismaClient>();

beforeEach(() => {
  mockReset(prismaMock);
});

// Test data factories
export const createTestUser = (overrides = {}) => ({
  id: '123e4567-e89b-12d3-a456-426614174000',
  email: 'test@example.com',
  name: 'Test User',
  createdAt: new Date('2025-01-01'),
  ...overrides,
});

export const createTestProduct = (overrides = {}) => ({
  id: '123e4567-e89b-12d3-a456-426614174001',
  name: 'Test Product',
  price: 29.99,
  stock: 100,
  ...overrides,
});

// API client fixture
import { FastifyInstance } from 'fastify';
import { buildApp } from '../src/app';

export async function createTestApp(): Promise<FastifyInstance> {
  const app = await buildApp();
  await app.ready();
  return app;
}

// Cleanup helper
export async function cleanupTestApp(app: FastifyInstance) {
  await app.close();
}

// Authentication helper
export function createAuthHeaders(userId: string = 'test-user-id'): Record<string, string> {
  const token = generateTestToken({ userId, role: 'user' });
  return {
    Authorization: `Bearer ${token}`,
  };
}

// Mock external HTTP services
import nock from 'nock';

export function mockExternalAPI() {
  nock('https://api.external-service.com')
    .get('/data')
    .reply(200, { status: 'success', data: [] });

  nock('https://api.payment-provider.com')
    .post('/charge')
    .reply(200, { transactionId: 'mock-txn-123' });
}

// Clean up nock after tests
afterEach(() => {
  nock.cleanAll();
});
```

**Go test fixtures:**

```go
// testutil/fixtures.go
package testutil

import (
    "context"
    "database/sql"
    "testing"

    "github.com/stretchr/testify/require"
    _ "github.com/mattn/go-sqlite3"
)

// SetupTestDB creates an in-memory SQLite database for testing
func SetupTestDB(t *testing.T) *sql.DB {
    db, err := sql.Open("sqlite3", ":memory:")
    require.NoError(t, err)

    // Run migrations
    schema := `
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL
        );
    `
    _, err = db.Exec(schema)
    require.NoError(t, err)

    // Cleanup after test
    t.Cleanup(func() {
        db.Close()
    })

    return db
}

// CreateTestUser inserts a test user and returns the ID
func CreateTestUser(t *testing.T, db *sql.DB, email, name string) int64 {
    result, err := db.Exec(
        "INSERT INTO users (email, name) VALUES (?, ?)",
        email, name,
    )
    require.NoError(t, err)

    id, err := result.LastInsertId()
    require.NoError(t, err)

    return id
}

// MockHTTPClient returns an http.Client with mocked responses
func MockHTTPClient(t *testing.T, responses map[string]string) *http.Client {
    return &http.Client{
        Transport: &mockTransport{responses: responses},
    }
}

type mockTransport struct {
    responses map[string]string
}

func (m *mockTransport) RoundTrip(req *http.Request) (*http.Response, error) {
    body, ok := m.responses[req.URL.String()]
    if !ok {
        return &http.Response{
            StatusCode: 404,
            Body:       io.NopCloser(strings.NewReader("Not found")),
        }, nil
    }

    return &http.Response{
        StatusCode: 200,
        Body:       io.NopCloser(strings.NewReader(body)),
    }, nil
}
```

### Test Data Factories

**Factory pattern for test data generation:**

```python
# tests/factories.py
import factory
from factory.faker import Faker
from app.models import User, Product, Order


class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.Sequence(lambda n: n)
    email = Faker("email")
    name = Faker("name")
    created_at = Faker("date_time_this_year")
    is_active = True


class ProductFactory(factory.Factory):
    class Meta:
        model = Product

    id = factory.Sequence(lambda n: n)
    name = Faker("word")
    description = Faker("text")
    price = Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    stock = Faker("random_int", min=0, max=1000)


class OrderFactory(factory.Factory):
    class Meta:
        model = Order

    id = factory.Sequence(lambda n: n)
    user = factory.SubFactory(UserFactory)
    status = factory.Faker(
        "random_element", elements=["pending", "completed", "cancelled"]
    )
    total = Faker("pydecimal", left_digits=4, right_digits=2, positive=True)


# Usage in tests:
def test_order_processing():
    user = UserFactory(email="specific@example.com")
    product = ProductFactory(price=99.99, stock=10)
    order = OrderFactory(user=user, status="pending")

    # Test logic...


# Batch creation:
def test_bulk_operations():
    users = UserFactory.create_batch(100)
    assert len(users) == 100
```

**TypeScript test data builders:**

```typescript
// test/builders.ts
export class UserBuilder {
  private user: Partial<User> = {
    id: crypto.randomUUID(),
    email: 'test@example.com',
    name: 'Test User',
    role: 'user',
    createdAt: new Date(),
  };

  withEmail(email: string): this {
    this.user.email = email;
    return this;
  }

  withRole(role: 'user' | 'admin'): this {
    this.user.role = role;
    return this;
  }

  build(): User {
    return this.user as User;
  }
}

export class ProductBuilder {
  private product: Partial<Product> = {
    id: crypto.randomUUID(),
    name: 'Test Product',
    price: 29.99,
    stock: 100,
  };

  withPrice(price: number): this {
    this.product.price = price;
    return this;
  }

  withStock(stock: number): this {
    this.product.stock = stock;
    return this;
  }

  build(): Product {
    return this.product as Product;
  }
}

// Usage in tests:
test('create order with custom user', async () => {
  const user = new UserBuilder()
    .withEmail('premium@example.com')
    .withRole('admin')
    .build();

  const product = new ProductBuilder()
    .withPrice(199.99)
    .withStock(5)
    .build();

  // Test logic...
});
```

______________________________________________________________________

## Part 2: Advanced Testing Strategies

### Property-Based Testing

**Python with Hypothesis:**

```python
import pytest
from hypothesis import given, strategies as st, assume, example
from app.utils import calculate_total, validate_email


# Basic property test
@given(st.integers(min_value=0, max_value=10000))
def test_calculate_discount_properties(price):
    """Discount should always be less than original price"""
    discount = calculate_discount(price, percent=20)

    # Properties that should always hold:
    assert discount >= 0
    assert discount <= price
    assert discount == price * 0.2


# Complex strategies
@given(st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=100))
def test_calculate_total_properties(prices):
    """Total should equal sum of individual prices"""
    items = [{"price": p, "quantity": 1} for p in prices]
    total = calculate_total(items)

    assert total == sum(prices)
    assert total > 0


# Testing with custom strategies
email_strategy = st.builds(
    lambda user, domain: f"{user}@{domain}",
    user=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=1,
        max_size=20,
    ),
    domain=st.sampled_from(["example.com", "test.org", "demo.net"]),
)


@given(email_strategy)
def test_email_validation(email):
    """Valid email formats should always pass validation"""
    result = validate_email(email)
    assert result is True


# Stateful testing - Shopping cart
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant


class ShoppingCartMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.cart = ShoppingCart()
        self.expected_total = 0

    @rule(product_id=st.integers(1, 100), price=st.floats(1.0, 1000.0))
    def add_item(self, product_id, price):
        self.cart.add_item(product_id, price)
        self.expected_total += price

    @rule(product_id=st.integers(1, 100))
    def remove_item(self, product_id):
        if product_id in self.cart.items:
            price = self.cart.items[product_id]
            self.cart.remove_item(product_id)
            self.expected_total -= price

    @invariant()
    def total_matches(self):
        """Cart total should always match expected total"""
        assert abs(self.cart.get_total() - self.expected_total) < 0.01


TestShoppingCart = ShoppingCartMachine.TestCase

# Run with: pytest test_shopping_cart.py
```

**JavaScript with fast-check:**

```typescript
import fc from 'fast-check';
import { calculateDiscount, validateEmail, ShoppingCart } from '../src/utils';

describe('Property-based tests', () => {
  test('discount is always less than or equal to original price', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 10000 }),
        fc.integer({ min: 0, max: 100 }),
        (price, percent) => {
          const discount = calculateDiscount(price, percent);
          return discount >= 0 && discount <= price;
        }
      )
    );
  });

  test('email validation accepts valid emails', () => {
    const emailArbitrary = fc.emailAddress();

    fc.assert(
      fc.property(emailArbitrary, (email) => {
        return validateEmail(email) === true;
      })
    );
  });

  test('shopping cart operations maintain consistency', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.integer({ min: 1, max: 100 }),
            price: fc.float({ min: 1, max: 1000, noNaN: true }),
          })
        ),
        (items) => {
          const cart = new ShoppingCart();

          // Add all items
          items.forEach((item) => cart.addItem(item.id, item.price));

          // Calculate expected total
          const expectedTotal = items.reduce((sum, item) => sum + item.price, 0);

          // Property: total should match sum of prices
          return Math.abs(cart.getTotal() - expectedTotal) < 0.01;
        }
      )
    );
  });

  test('string reverse is involutive (reversing twice returns original)', () => {
    fc.assert(
      fc.property(fc.string(), (str) => {
        const reversed = str.split('').reverse().join('');
        const doubleReversed = reversed.split('').reverse().join('');
        return doubleReversed === str;
      })
    );
  });
});
```

**Go with gopter:**

```go
package utils_test

import (
    "testing"

    "github.com/leanovate/gopter"
    "github.com/leanovate/gopter/gen"
    "github.com/leanovate/gopter/prop"
)

func TestCalculateDiscountProperties(t *testing.T) {
    properties := gopter.NewProperties(nil)

    properties.Property("discount is always <= original price", prop.ForAll(
        func(price uint, percent uint) bool {
            if percent > 100 {
                return true // Skip invalid percentages
            }

            discount := CalculateDiscount(price, percent)
            return discount >= 0 && discount <= price
        },
        gen.UIntRange(0, 10000),
        gen.UIntRange(0, 100),
    ))

    properties.TestingRun(t)
}

func TestShoppingCartProperties(t *testing.T) {
    properties := gopter.NewProperties(nil)

    properties.Property("cart total equals sum of item prices", prop.ForAll(
        func(items []Item) bool {
            cart := NewShoppingCart()

            expectedTotal := 0.0
            for _, item := range items {
                cart.AddItem(item.ID, item.Price)
                expectedTotal += item.Price
            }

            total := cart.GetTotal()
            return math.Abs(total-expectedTotal) < 0.01
        },
        gen.SliceOf(gen.Struct(reflect.TypeOf(&Item{}), map[string]gopter.Gen{
            "ID":    gen.IntRange(1, 100),
            "Price": gen.Float64Range(1.0, 1000.0),
        })),
    ))

    properties.TestingRun(t)
}
```

### Contract Testing (Pact)

**Consumer-driven contract testing:**

**Consumer side (TypeScript):**

```typescript
// consumer/test/pact/user-service.pact.test.ts
import { Pact } from '@pact-foundation/pact';
import { UserServiceClient } from '../src/services/user-service';

describe('User Service Pact', () => {
  const provider = new Pact({
    consumer: 'OrderService',
    provider: 'UserService',
    port: 8080,
    log: 'logs/pact.log',
    dir: 'pacts',
  });

  beforeAll(() => provider.setup());
  after all(() => provider.finalize());
  afterEach(() => provider.verify());

  test('get user by id', async () => {
    // Define expected interaction
    await provider.addInteraction({
      state: 'user 123 exists',
      uponReceiving: 'a request for user 123',
      withRequest: {
        method: 'GET',
        path: '/users/123',
        headers: {
          Accept: 'application/json',
        },
      },
      willRespondWith: {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
        body: {
          id: '123',
          email: 'user@example.com',
          name: 'Test User',
        },
      },
    });

    // Test your client
    const client = new UserServiceClient('http://localhost:8080');
    const user = await client.getUser('123');

    expect(user.id).toBe('123');
    expect(user.email).toBe('user@example.com');
  });

  test('create new user', async () => {
    await provider.addInteraction({
      state: 'no user exists',
      uponReceiving: 'a request to create user',
      withRequest: {
        method: 'POST',
        path: '/users',
        headers: {
          'Content-Type': 'application/json',
        },
        body: {
          email: 'newuser@example.com',
          name: 'New User',
        },
      },
      willRespondWith: {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
        },
        body: {
          id: '456',
          email: 'newuser@example.com',
          name: 'New User',
        },
      },
    });

    const client = new UserServiceClient('http://localhost:8080');
    const user = await client.createUser({
      email: 'newuser@example.com',
      name: 'New User',
    });

    expect(user.id).toBe('456');
  });
});
```

**Provider side verification (Python):**

```python
# provider/tests/test_pact_verification.py
import pytest
from pact import Verifier
from app.main import app


@pytest.fixture(scope="session")
def pact_verifier():
    return Verifier(provider="UserService", provider_base_url="http://localhost:8000")


def test_verify_pacts(pact_verifier):
    """Verify that provider satisfies consumer contracts"""

    # State setup for each interaction
    def provider_state_setup(state):
        if state == "user 123 exists":
            # Setup: Create user with ID 123 in test database
            from app.database import db
            from app.models import User

            db.session.add(User(id="123", email="user@example.com", name="Test User"))
            db.session.commit()
        elif state == "no user exists":
            # Setup: Ensure clean state
            from app.database import db

            db.session.query(User).delete()
            db.session.commit()

    success, logs = pact_verifier.verify_pacts(
        "./pacts/OrderService-UserService.json",
        provider_states_setup_url="http://localhost:8000/_pact/provider-states",
        enable_pending=False,
        verbose=True,
    )

    assert success, f"Pact verification failed: {logs}"
```

**Contract testing with gRPC (Pact):**

```python
# gRPC contract testing
from pact import Consumer, Provider, Format
import grpc
from generated.user_pb2 import GetUserRequest
from generated.user_pb2_grpc import UserServiceStub

pact = Consumer("OrderService").has_pact_with(
    Provider("UserServiceGRPC"), pact_dir="./pacts"
)

pact.start_service()


def test_grpc_get_user():
    expected = {"id": "123", "email": "user@example.com", "name": "Test User"}

    (
        pact.given("user 123 exists")
        .upon_receiving("a gRPC request for user 123")
        .with_request(
            method="GetUser", body={"userId": "123"}, content_type=Format.PROTOBUF
        )
        .will_respond_with(200, body=expected, content_type=Format.PROTOBUF)
    )

    with pact:
        channel = grpc.insecure_channel(f"localhost:{pact.port}")
        client = UserServiceStub(channel)

        response = client.GetUser(GetUserRequest(user_id="123"))

        assert response.id == "123"
        assert response.email == "user@example.com"
```

### Mutation Testing

**Python with mutmut:**

```bash
# Install mutmut
pip install mutmut

# Run mutation testing
mutmut run

# Example output:
# - Mutation testing starting -
#
# Running tests without mutations... Done
#
# Mutating code:
#   app/utils.py: 15 mutations
#   app/services.py: 23 mutations
#
# Legend:
# 🎉 Killed mutants (Good!)
# ⏰ Timeout
# 🤔 Suspicious (Mutant survived - weak test!)
# 🙁 Untested

# Show survived mutants (need better tests)
mutmut results

# Example: Survived mutant in calculate_discount
# --- app/utils.py
# +++ app/utils.py
# @@ -10,7 +10,7 @@
#  def calculate_discount(price, percent):
# -    return price * (percent / 100)
# +    return price * (percent / 99)  # Mutant survived!

# Fix: Add test for exact discount calculation
def test_discount_exact_calculation():
    assert calculate_discount(100, 20) == 20.0  # Now catches the mutant
```

**JavaScript with Stryker:**

```bash
# Install Stryker
npm install --save-dev @stryker-mutator/core @stryker-mutator/jest-runner

# stryker.conf.json
{
  "mutator": "javascript",
  "packageManager": "npm",
  "reporters": ["clear-text", "progress", "html"],
  "testRunner": "jest",
  "coverageAnalysis": "perTest",
  "mutate": [
    "src/**/*.ts",
    "!src/**/*.test.ts"
  ]
}

# Run mutation testing
npx stryker run

# Example output showing survived mutant:
# Mutant survived in src/utils.ts:calculateDiscount
# -  return price * (percent / 100);
# +  return price * (percent / 101);  // Survived!
#
# Tests need improvement to catch this mutation
```

**Interpreting mutation scores:**

```markdown
## Mutation Score Interpretation

**Mutation Score = (Killed Mutants / Total Mutants) × 100%**

- **90%+**: Excellent test suite, high confidence
- **75-89%**: Good test coverage, minor gaps
- **60-74%**: Adequate, needs improvement
- **<60%**: Weak test suite, significant gaps

## Common Mutation Operators

1. **Arithmetic**: `+` → `-`, `*` → `/`
2. **Relational**: `<` → `<=`, `==` → `!=`
3. **Logical**: `&&` → `||`, `!` → empty
4. **Constant**: `0` → `1`, `true` → `false`
5. **Statement Removal**: Delete return, delete call

## Prioritizing Mutation Fixes

Focus on survived mutants in:
1. Critical business logic
2. Security-sensitive code
3. Financial calculations
4. User-facing features
```

### Visual Regression Testing

**Playwright visual testing:**

```typescript
// tests/visual-regression.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Visual regression tests', () => {
  test('homepage renders correctly', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Take screenshot and compare to baseline
    await expect(page).toHaveScreenshot('homepage.png', {
      fullPage: true,
      maxDiffPixels: 100, // Allow minor differences
    });
  });

  test('product card layout', async ({ page }) => {
    await page.goto('http://localhost:3000/products/123');

    // Screenshot specific element
    const productCard = page.locator('[data-testid="product-card"]');
    await expect(productCard).toHaveScreenshot('product-card.png');
  });

  test('responsive layout on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.goto('http://localhost:3000');

    await expect(page).toHaveScreenshot('homepage-mobile.png');
  });

  test('dark mode renders correctly', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.click('[data-testid="theme-toggle"]');
    await page.waitForTimeout(500); // Wait for transition

    await expect(page).toHaveScreenshot('homepage-dark.png');
  });
});

// Update baselines when UI intentionally changes:
// npx playwright test --update-snapshots
```

**Percy visual testing (CI integration):**

```typescript
// tests/percy.spec.ts
import { test } from '@playwright/test';
import percySnapshot from '@percy/playwright';

test('visual snapshots with Percy', async ({ page }) => {
  await page.goto('http://localhost:3000');

  // Percy handles baseline storage and diff detection
  await percySnapshot(page, 'Homepage');

  // Test different states
  await page.click('[data-testid="login-button"]');
  await percySnapshot(page, 'Login Modal');

  await page.fill('[data-testid="email-input"]', 'user@example.com');
  await page.fill('[data-testid="password-input"]', 'password123');
  await percySnapshot(page, 'Login Form Filled');
});

// Responsive snapshots
test('responsive layouts', async ({ page }) => {
  await page.goto('http://localhost:3000');

  await percySnapshot(page, 'Homepage Responsive', {
    widths: [375, 768, 1280], // Mobile, tablet, desktop
  });
});
```

**BackstopJS configuration:**

```javascript
// backstop.json
{
  "id": "visual_regression_test",
  "viewports": [
    {
      "label": "phone",
      "width": 375,
      "height": 667
    },
    {
      "label": "tablet",
      "width": 768,
      "height": 1024
    },
    {
      "label": "desktop",
      "width": 1920,
      "height": 1080
    }
  ],
  "scenarios": [
    {
      "label": "Homepage",
      "url": "http://localhost:3000",
      "delay": 1000,
      "misMatchThreshold": 0.1
    },
    {
      "label": "Product Page",
      "url": "http://localhost:3000/products/123",
      "delay": 1000
    },
    {
      "label": "Checkout Flow",
      "url": "http://localhost:3000/checkout",
      "delay": 1000,
      "clickSelector": "[data-testid='payment-method-card']",
      "postInteractionWait": 500
    }
  ],
  "paths": {
    "bitmaps_reference": "backstop_data/bitmaps_reference",
    "bitmaps_test": "backstop_data/bitmaps_test",
    "html_report": "backstop_data/html_report"
  },
  "report": ["browser", "CI"]
}

// Run tests:
// backstop test                    # Run tests against reference
// backstop approve                 # Approve new baselines
// backstop reference              # Create new reference images
```

______________________________________________________________________

## Part 3: Chaos Engineering

### Chaos Testing Fundamentals

**Python chaos testing with pytest:**

```python
# tests/chaos/test_resilience.py
import pytest
import time
from chaos_toolkit import chaos
from app.services import OrderService


class NetworkChaos:
    """Simulate network failures"""

    @staticmethod
    def introduce_latency(duration_ms=1000):
        """Add network latency"""
        time.sleep(duration_ms / 1000)

    @staticmethod
    def drop_packets(probability=0.5):
        """Randomly drop network packets"""
        import random

        if random.random() < probability:
            raise ConnectionError("Packet dropped")


@pytest.mark.chaos
def test_order_service_with_network_latency():
    """Verify graceful degradation under network latency"""
    service = OrderService()

    # Inject 2s latency
    with mock.patch("httpx.AsyncClient.post") as mock_post:

        async def slow_post(*args, **kwargs):
            await asyncio.sleep(2)  # Simulate latency
            return mock.MagicMock(status_code=200, json=lambda: {"id": "123"})

        mock_post.side_effect = slow_post

        start = time.time()
        result = await service.create_order({"items": [{"id": 1, "qty": 2}]})
        duration = time.time() - start

        # Should timeout and fallback gracefully
        assert duration < 5, "Should timeout within 5s"
        assert result is not None or service.get_last_error() is not None


@pytest.mark.chaos
def test_database_connection_failure():
    """Test behavior when database is unavailable"""
    service = OrderService()

    with mock.patch("sqlalchemy.engine.Engine.connect") as mock_connect:
        mock_connect.side_effect = OperationalError("Connection refused", None, None)

        with pytest.raises(ServiceUnavailableError) as exc_info:
            service.get_order("123")

        # Should return proper error, not crash
        assert "database unavailable" in str(exc_info.value).lower()


@pytest.mark.chaos
def test_circuit_breaker_activation():
    """Verify circuit breaker opens after failures"""
    from circuitbreaker import CircuitBreaker

    service = OrderService()

    # Simulate 5 consecutive failures
    with mock.patch.object(service, "_call_payment_api") as mock_api:
        mock_api.side_effect = RequestException("Service down")

        for i in range(5):
            with pytest.raises(RequestException):
                service.process_payment(100)

        # Circuit should be open now
        assert service.payment_circuit_breaker.current_state == "open"

        # Subsequent calls should fail fast
        start = time.time()
        with pytest.raises(CircuitBreakerError):
            service.process_payment(100)
        duration = time.time() - start

        assert duration < 0.1, "Circuit breaker should fail fast"
```

**Chaos Toolkit integration:**

```yaml
# chaos-experiments/network-latency.yaml
version: 1.0.0
title: Network latency impact on order processing
description: Introduce 2s latency to payment service and verify graceful handling

steady-state-hypothesis:
  title: Orders process successfully within 5s
  probes:
    - name: order-success-rate
      type: probe
      provider:
        type: python
        module: probes.orders
        func: get_order_success_rate
      tolerance: [95, 100]

method:
  - type: action
    name: introduce-network-latency
    provider:
      type: python
      module: actions.network
      func: add_latency
      arguments:
        target_service: payment-service
        latency_ms: 2000
        duration: 60

  - type: probe
    name: verify-order-processing
    provider:
      type: python
      module: probes.orders
      func: create_test_order
    tolerance:
      - type: regex
        target: status
        pattern: "success|degraded"

rollbacks:
  - type: action
    name: remove-network-latency
    provider:
      type: python
      module: actions.network
      func: remove_latency
      arguments:
        target_service: payment-service

# Run with: chaos run network-latency.yaml
```

**Kubernetes chaos testing (Chaos Mesh):**

```yaml
# chaos-mesh/pod-failure.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: order-service-pod-kill
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      "app": "order-service"
  scheduler:
    cron: "@every 10m"

---
# Network chaos
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: payment-service-network-delay
  namespace: chaos-testing
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      "app": "payment-service"
  delay:
    latency: "2s"
    correlation: "50"
    jitter: "500ms"
  duration: "5m"
  scheduler:
    cron: "0 */6 * * *"  # Every 6 hours

---
# Stress testing
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-pressure
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      "app": "order-service"
  stressors:
    memory:
      workers: 4
      size: "1GB"
  duration: "10m"
```

**Chaos testing best practices:**

```python
# chaos/framework.py
from dataclasses import dataclass
from typing import Callable, List
import time


@dataclass
class ChaosExperiment:
    """Framework for chaos experiments"""

    name: str
    steady_state_check: Callable[[], bool]
    chaos_action: Callable[[], None]
    rollback_action: Callable[[], None]
    duration_seconds: int = 60

    def run(self):
        """Execute chaos experiment with safety checks"""
        print(f"Starting chaos experiment: {self.name}")

        # 1. Verify steady state
        if not self.steady_state_check():
            raise RuntimeError("System not in steady state - aborting experiment")

        print("✓ Steady state verified")

        # 2. Introduce chaos
        print(f"Introducing chaos for {self.duration_seconds}s...")
        try:
            self.chaos_action()

            # Monitor during chaos
            time.sleep(self.duration_seconds)

            # 3. Verify system still functional (degraded ok)
            if not self.steady_state_check():
                print("⚠ System degraded but operational")
            else:
                print("✓ System maintained steady state under chaos")

        finally:
            # 4. Always rollback
            print("Rolling back chaos...")
            self.rollback_action()

            # 5. Verify recovery
            time.sleep(5)
            if not self.steady_state_check():
                raise RuntimeError("System failed to recover - ALERT!")

            print("✓ System recovered successfully")


# Usage:
def check_order_service_health():
    response = requests.get("http://order-service/health")
    return response.status_code == 200


def introduce_cpu_stress():
    subprocess.run(["stress-ng", "--cpu", "4", "--timeout", "60s"])


def stop_cpu_stress():
    subprocess.run(["pkill", "stress-ng"])


experiment = ChaosExperiment(
    name="CPU stress test on order service",
    steady_state_check=check_order_service_health,
    chaos_action=introduce_cpu_stress,
    rollback_action=stop_cpu_stress,
    duration_seconds=60,
)

experiment.run()
```

______________________________________________________________________

## Part 4: Load & Performance Testing

### Load Testing Strategies

**Locust (Python) load testing:**

```python
# locustfile.py
from locust import HttpUser, task, between, events
import random


class OrderServiceUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3s between requests
    host = "http://localhost:8000"

    def on_start(self):
        """Login before starting tasks"""
        response = self.client.post(
            "/auth/login", json={"email": "test@example.com", "password": "testpass"}
        )
        self.token = response.json()["access_token"]

    @task(3)  # Weight: 3x more likely than other tasks
    def browse_products(self):
        """Simulate browsing product catalog"""
        page = random.randint(1, 10)
        self.client.get(
            f"/products?page={page}&limit=20",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/products?page=[page]",  # Group by pattern
        )

    @task(2)
    def view_product_details(self):
        """View specific product"""
        product_id = random.randint(1, 1000)
        self.client.get(
            f"/products/{product_id}", headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def create_order(self):
        """Create an order (less frequent, more expensive)"""
        response = self.client.post(
            "/orders",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "items": [
                    {
                        "product_id": random.randint(1, 100),
                        "quantity": random.randint(1, 5),
                    }
                    for _ in range(random.randint(1, 3))
                ]
            },
        )

        if response.status_code != 201:
            # Custom failure metric
            events.request_failure.fire(
                request_type="POST",
                name="/orders",
                response_time=response.elapsed.total_seconds() * 1000,
                exception=f"Order creation failed: {response.status_code}",
            )


# Run with:
# locust -f locustfile.py --users 100 --spawn-rate 10 --run-time 10m
#
# Web UI: http://localhost:8089
```

**k6 load testing (JavaScript):**

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp up to 100 users
    { duration: '5m', target: 100 },   // Stay at 100 for 5m
    { duration: '2m', target: 200 },   // Ramp to 200
    { duration: '5m', target: 200 },   // Stay at 200 for 5m
    { duration: '2m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
    errors: ['rate<0.1'],              // Custom error rate < 10%
  },
};

export default function () {
  // Login
  const loginRes = http.post('http://localhost:8000/auth/login', JSON.stringify({
    email: 'test@example.com',
    password: 'testpass',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(loginRes, {
    'login successful': (r) => r.status === 200,
  }) || errorRate.add(1);

  const token = loginRes.json('access_token');

  sleep(1);

  // Browse products
  const productsRes = http.get('http://localhost:8000/products?page=1&limit=20', {
    headers: { Authorization: `Bearer ${token}` },
  });

  check(productsRes, {
    'products loaded': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  sleep(2);

  // Create order
  const orderRes = http.post('http://localhost:8000/orders', JSON.stringify({
    items: [
      { product_id: 1, quantity: 2 },
      { product_id: 5, quantity: 1 },
    ],
  }), {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  check(orderRes, {
    'order created': (r) => r.status === 201,
  }) || errorRate.add(1);

  sleep(1);
}

// Run with: k6 run load-test.js
```

**Artillery load testing (YAML):**

```yaml
# artillery-config.yml
config:
  target: "http://localhost:8000"
  phases:
    - duration: 60
      arrivalRate: 10
      name: Warm up
    - duration: 300
      arrivalRate: 50
      name: Sustained load
    - duration: 120
      arrivalRate: 100
      name: Peak load
  variables:
    testEmail: "test@example.com"
    testPassword: "testpass"
  processor: "./load-test-processor.js"

scenarios:
  - name: "User journey: Browse and purchase"
    weight: 70
    flow:
      - post:
          url: "/auth/login"
          json:
            email: "{{ testEmail }}"
            password: "{{ testPassword }}"
          capture:
            - json: "$.access_token"
              as: "token"
      - get:
          url: "/products?page=1&limit=20"
          headers:
            Authorization: "Bearer {{ token }}"
      - get:
          url: "/products/{{ $randomNumber(1, 1000) }}"
          headers:
            Authorization: "Bearer {{ token }}"
      - post:
          url: "/orders"
          headers:
            Authorization: "Bearer {{ token }}"
          json:
            items:
              - product_id: "{{ $randomNumber(1, 100) }}"
                quantity: "{{ $randomNumber(1, 5) }}"

  - name: "Search products"
    weight: 30
    flow:
      - post:
          url: "/auth/login"
          json:
            email: "{{ testEmail }}"
            password: "{{ testPassword }}"
          capture:
            - json: "$.access_token"
              as: "token"
      - get:
          url: "/products/search?q={{ $randomString(5) }}"
          headers:
            Authorization: "Bearer {{ token }}"

# Run with: artillery run artillery-config.yml
# Generate report: artillery run --output report.json artillery-config.yml
#                  artillery report report.json
```

______________________________________________________________________

## Security Considerations

### Secure Test Data Management

```python
# Avoid hardcoded secrets in tests
import os
from pathlib import Path


class TestSecrets:
    """Secure test secrets management"""

    @staticmethod
    def load_test_credentials():
        """Load from environment or secure vault"""
        # Option 1: Environment variables
        db_password = os.getenv("TEST_DB_PASSWORD")

        # Option 2: Secret file (gitignored)
        secrets_file = Path(".test-secrets.env")
        if secrets_file.exists():
            from dotenv import load_dotenv

            load_dotenv(secrets_file)

        # Option 3: Vault for CI/CD
        if os.getenv("CI"):
            import hvac

            client = hvac.Client(url=os.getenv("VAULT_ADDR"))
            secrets = client.secrets.kv.v2.read_secret_version(path="test/credentials")
            return secrets["data"]["data"]

        return {
            "db_password": db_password,
            "api_key": os.getenv("TEST_API_KEY"),
        }


# Never commit:
# ❌ API_KEY = "sk-1234567890abcdef"
# ✅ API_KEY = os.getenv("TEST_API_KEY")
```

### Test Isolation & Data Cleanup

```python
# Ensure tests don't leak data
@pytest.fixture(autouse=True)
def isolate_test_data(db_session):
    """Automatic transaction rollback after each test"""
    yield

    # Rollback all changes
    db_session.rollback()

    # Verify no data leaked
    user_count = db_session.query(User).count()
    assert user_count == 0, f"Test leaked {user_count} users"


# Anonymize production data for testing
def anonymize_user_data(user: User) -> User:
    """Sanitize PII for test datasets"""
    import hashlib

    user.email = f"test+{hashlib.md5(user.email.encode()).hexdigest()[:8]}@example.com"
    user.name = f"Test User {user.id}"
    user.phone = None
    user.address = None
    return user
```

______________________________________________________________________

## Testing & Validation

### Test Coverage Analysis

```bash
# Python coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# JavaScript coverage
npm test -- --coverage --coverageReporters=html --coverageReporters=text

# Go coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out -o coverage.html

# Coverage thresholds in CI
pytest --cov=app --cov-fail-under=80  # Fail if coverage < 80%
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: |
          npm ci
          npm test -- --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: npm run test:integration

  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run pact tests
        run: npm run test:pact
      - name: Publish pacts
        run: npm run pact:publish

  mutation-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run mutation testing
        run: npx stryker run
      - name: Check mutation score
        run: |
          SCORE=$(jq '.mutationScore' reports/mutation/mutation-score.json)
          if (( $(echo "$SCORE < 75" | bc -l) )); then
            echo "Mutation score $SCORE% below threshold"
            exit 1
          fi
```

______________________________________________________________________

## Troubleshooting

### Common Testing Issues

**Issue 1: Flaky tests**

```python
# Problem: Test passes sometimes, fails others
def test_async_operation():
    result = async_function()  # Race condition!
    assert result.status == "complete"


# Solution 1: Proper waiting
def test_async_operation_fixed():
    result = async_function()

    # Wait for completion with timeout
    for _ in range(10):
        if result.status == "complete":
            break
        time.sleep(0.1)
    else:
        pytest.fail("Operation didn't complete in time")

    assert result.status == "complete"


# Solution 2: Use async/await properly
@pytest.mark.asyncio
async def test_async_operation_proper():
    result = await async_function()
    assert result.status == "complete"


# Solution 3: Retry flaky tests (last resort)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_potentially_flaky():
    result = external_api_call()
    assert result.success
```

**Issue 2: Slow test suite**

```python
# Problem: Tests take too long
# Solution: Parallelize with pytest-xdist
# pytest -n auto  # Use all CPU cores

# Solution: Skip slow tests in development
@pytest.mark.slow
def test_expensive_operation():
    # Long-running test
    pass


# Run fast tests only:
# pytest -m "not slow"


# Solution: Use test markers for selective execution
@pytest.mark.integration
def test_database_integration():
    pass


# pytest -m unit              # Only unit tests
# pytest -m "unit or integration"  # Unit + integration
```

**Issue 3: Test dependencies**

```python
# Problem: Tests depend on execution order (BAD!)
# tests/test_bad.py
def test_create_user():
    global user_id
    user_id = create_user("test@example.com")


def test_update_user():
    update_user(user_id, name="Updated")  # Depends on previous test!


# Solution: Independent tests with fixtures
@pytest.fixture
def test_user(db_session):
    user = User(email="test@example.com")
    db_session.add(user)
    db_session.commit()
    return user


def test_update_user(db_session, test_user):
    test_user.name = "Updated"
    db_session.commit()
    assert test_user.name == "Updated"
```

______________________________________________________________________

## Related Tools & Resources

- **quality-validation.md** - High-level test orchestration and release readiness
- **debugging-guide.md** - Test debugging strategies and techniques
- **qa-strategist agent** - Test planning, strategy expertise, and advanced testing techniques
- **observability-incident-lead agent** - Performance testing optimization and monitoring

______________________________________________________________________

## Summary

This comprehensive guide provides production-ready test infrastructure and advanced testing strategies:

1. **Test Infrastructure**: Fixtures, factories, database setup, mocking
1. **Advanced Strategies**: Property-based, contract, mutation, visual regression testing
1. **Chaos Engineering**: Resilience testing, failure injection, recovery validation
1. **Load Testing**: Locust, k6, Artillery for performance validation
1. **Security**: Secure secrets, data isolation, anonymization
1. **CI/CD Integration**: Automated execution, coverage thresholds, quality gates

**Key Principles:**

- Tests should be independent, isolated, and deterministic
- Use appropriate testing strategies for different scenarios
- Automate everything in CI/CD
- Maintain high test coverage with mutation testing
- Practice chaos engineering for production resilience
- Secure test data and credentials

This tool consolidates `test-harness.md` and `advanced-testing-strategies.md` into a single comprehensive testing resource.
