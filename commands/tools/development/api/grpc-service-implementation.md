______________________________________________________________________

title: gRPC Service Implementation
owner: Developer Enablement Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6H9DJ3RDGFNDADS8GNG9523
  category: development/api
  agents:
- grpc-specialist
- architecture-council
- observability-incident-lead
  tags:
- grpc
- protobuf
- microservices
- rpc

______________________________________________________________________

## gRPC Service Implementation

You are a gRPC expert specializing in creating high-performance, type-safe RPC services with Protocol Buffers. Design comprehensive gRPC implementations with proper service definitions, streaming, error handling, interceptors, and deployment.

## Context

The user needs to implement a gRPC service with complete setup including Protocol Buffer definitions, server implementation, client generation, streaming patterns, authentication, load balancing, and monitoring. Focus on production-ready code optimized for performance and reliability.

## Requirements for: $ARGUMENTS

1. **Protocol Buffer Definitions**:

   - Service and message definitions
   - Proper field numbering and types
   - Nested messages and enums
   - Import management
   - Documentation comments

1. **Service Implementation**:

   - Unary RPC handlers
   - Server streaming
   - Client streaming
   - Bidirectional streaming
   - Error handling with status codes

1. **Client Generation**:

   - Typed client stubs
   - Connection management
   - Retry logic
   - Deadline/timeout handling
   - Load balancing

1. **Performance**:

   - HTTP/2 multiplexing
   - Connection pooling
   - Compression (gzip)
   - Keep-alive configuration
   - Resource limits

1. **Security**:

   - TLS/SSL configuration
   - Authentication (token-based, mTLS)
   - Authorization interceptors
   - Input validation

1. **Observability**:

   - Request logging
   - Metrics collection
   - Distributed tracing
   - Health checking
   - Reflection API

______________________________________________________________________

## Proto Definitions

### Complete Service Definition

```protobuf
// proto/user_service.proto
syntax = "proto3";

package user.v1;

option go_package = "github.com/example/user/v1;userv1";

import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";
import "google/rpc/status.proto";

// User service for managing user accounts
service UserService {
  // Unary RPC: Get user by ID
  rpc GetUser(GetUserRequest) returns (GetUserResponse);

  // Unary RPC: Create a new user
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);

  // Unary RPC: Update user
  rpc UpdateUser(UpdateUserRequest) returns (UpdateUserResponse);

  // Unary RPC: Delete user
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty);

  // Server streaming: List users with pagination
  rpc ListUsers(ListUsersRequest) returns (stream User);

  // Client streaming: Batch create users
  rpc BatchCreateUsers(stream CreateUserRequest) returns (BatchCreateUsersResponse);

  // Bidirectional streaming: Real-time user updates
  rpc WatchUsers(stream WatchUsersRequest) returns (stream UserEvent);
}

// User message
message User {
  string id = 1;
  string email = 2;
  string username = 3;
  UserRole role = 4;
  google.protobuf.Timestamp created_at = 5;
  google.protobuf.Timestamp updated_at = 6;
  UserProfile profile = 7;
}

// User profile
message UserProfile {
  string bio = 1;
  string avatar_url = 2;
  string website = 3;
}

// User role enum
enum UserRole {
  USER_ROLE_UNSPECIFIED = 0;
  USER_ROLE_USER = 1;
  USER_ROLE_ADMIN = 2;
  USER_ROLE_MODERATOR = 3;
}

// Request/Response messages
message GetUserRequest {
  string id = 1;
}

message GetUserResponse {
  User user = 1;
}

message CreateUserRequest {
  string email = 1;
  string username = 2;
  string password = 3;
  UserRole role = 4;
}

message CreateUserResponse {
  User user = 1;
}

message UpdateUserRequest {
  string id = 1;
  optional string email = 2;
  optional string username = 3;
  optional UserProfile profile = 4;
}

message UpdateUserResponse {
  User user = 1;
}

message DeleteUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
  string filter = 3;
}

message BatchCreateUsersResponse {
  repeated User users = 1;
  int32 total_created = 2;
}

message WatchUsersRequest {
  repeated string user_ids = 1;
}

message UserEvent {
  enum EventType {
    EVENT_TYPE_UNSPECIFIED = 0;
    EVENT_TYPE_CREATED = 1;
    EVENT_TYPE_UPDATED = 2;
    EVENT_TYPE_DELETED = 3;
  }

  EventType type = 1;
  User user = 2;
  google.protobuf.Timestamp timestamp = 3;
}
```

______________________________________________________________________

## Server Implementation

### Go Server

```go
// server/user_service.go
package server

import (
    "context"
    "fmt"
    "io"
    "time"

    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "google.golang.org/protobuf/types/known/emptypb"
    "google.golang.org/protobuf/types/known/timestamppb"

    pb "github.com/example/user/v1"
)

type UserServer struct {
    pb.UnimplementedUserServiceServer
    db *Database
}

func NewUserServer(db *Database) *UserServer {
    return &UserServer{db: db}
}

// Unary RPC: Get user by ID
func (s *UserServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    if req.Id == "" {
        return nil, status.Error(codes.InvalidArgument, "user ID is required")
    }

    user, err := s.db.GetUser(ctx, req.Id)
    if err != nil {
        if err == ErrNotFound {
            return nil, status.Error(codes.NotFound, "user not found")
        }
        return nil, status.Error(codes.Internal, err.Error())
    }

    return &pb.GetUserResponse{
        User: user,
    }, nil
}

// Unary RPC: Create user
func (s *UserServer) CreateUser(ctx context.Context, req *pb.CreateUserRequest) (*pb.CreateUserResponse, error) {
    // Validation
    if req.Email == "" || req.Username == "" {
        return nil, status.Error(codes.InvalidArgument, "email and username are required")
    }

    // Check for duplicates
    exists, err := s.db.UserExists(ctx, req.Email)
    if err != nil {
        return nil, status.Error(codes.Internal, err.Error())
    }
    if exists {
        return nil, status.Error(codes.AlreadyExists, "user with this email already exists")
    }

    user := &pb.User{
        Id:        generateID(),
        Email:     req.Email,
        Username:  req.Username,
        Role:      req.Role,
        CreatedAt: timestamppb.Now(),
        UpdatedAt: timestamppb.Now(),
    }

    if err := s.db.CreateUser(ctx, user); err != nil {
        return nil, status.Error(codes.Internal, err.Error())
    }

    return &pb.CreateUserResponse{
        User: user,
    }, nil
}

// Server streaming: List users
func (s *UserServer) ListUsers(req *pb.ListUsersRequest, stream pb.UserService_ListUsersServer) error {
    pageSize := req.PageSize
    if pageSize == 0 {
        pageSize = 100
    }

    users, err := s.db.ListUsers(stream.Context(), pageSize, req.PageToken, req.Filter)
    if err != nil {
        return status.Error(codes.Internal, err.Error())
    }

    for _, user := range users {
        if err := stream.Send(user); err != nil {
            return status.Error(codes.Internal, err.Error())
        }
    }

    return nil
}

// Client streaming: Batch create users
func (s *UserServer) BatchCreateUsers(stream pb.UserService_BatchCreateUsersServer) error {
    var users []*pb.User
    var count int32

    for {
        req, err := stream.Recv()
        if err == io.EOF {
            // Client finished sending
            return stream.SendAndClose(&pb.BatchCreateUsersResponse{
                Users:        users,
                TotalCreated: count,
            })
        }
        if err != nil {
            return status.Error(codes.Internal, err.Error())
        }

        // Validate and create user
        if req.Email == "" || req.Username == "" {
            continue // Skip invalid requests
        }

        user := &pb.User{
            Id:        generateID(),
            Email:     req.Email,
            Username:  req.Username,
            Role:      req.Role,
            CreatedAt: timestamppb.Now(),
            UpdatedAt: timestamppb.Now(),
        }

        if err := s.db.CreateUser(stream.Context(), user); err != nil {
            continue // Skip failed creates
        }

        users = append(users, user)
        count++
    }
}

// Bidirectional streaming: Watch users
func (s *UserServer) WatchUsers(stream pb.UserService_WatchUsersServer) error {
    // Receive initial watch request
    req, err := stream.Recv()
    if err != nil {
        return status.Error(codes.Internal, err.Error())
    }

    // Subscribe to user events
    eventChan := s.db.SubscribeUserEvents(stream.Context(), req.UserIds)

    for {
        select {
        case <-stream.Context().Done():
            return status.Error(codes.Canceled, "stream canceled")

        case event := <-eventChan:
            if err := stream.Send(event); err != nil {
                return status.Error(codes.Internal, err.Error())
            }
        }
    }
}
```

### Server Setup with Interceptors

```go
// main.go
package main

import (
    "context"
    "log"
    "net"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/credentials"
    "google.golang.org/grpc/health"
    "google.golang.org/grpc/health/grpc_health_v1"
    "google.golang.org/grpc/keepalive"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/reflection"
    "google.golang.org/grpc/status"

    pb "github.com/example/user/v1"
)

// Authentication interceptor
func authInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Error(codes.Unauthenticated, "missing metadata")
    }

    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Error(codes.Unauthenticated, "missing authorization token")
    }

    // Validate token
    userID, err := validateToken(tokens[0])
    if err != nil {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }

    // Add user ID to context
    ctx = context.WithValue(ctx, "userID", userID)

    return handler(ctx, req)
}

// Logging interceptor
func loggingInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    start := time.Now()

    // Call handler
    resp, err := handler(ctx, req)

    // Log request
    duration := time.Since(start)
    statusCode := codes.OK
    if err != nil {
        statusCode = status.Code(err)
    }

    log.Printf("method=%s duration=%v status=%s", info.FullMethod, duration, statusCode)

    return resp, err
}

// Rate limiting interceptor
func rateLimitInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    // Get client IP from metadata
    md, _ := metadata.FromIncomingContext(ctx)
    clientIP := md.Get("x-forwarded-for")

    // Check rate limit
    if !checkRateLimit(clientIP) {
        return nil, status.Error(codes.ResourceExhausted, "rate limit exceeded")
    }

    return handler(ctx, req)
}

func main() {
    // TLS credentials
    creds, err := credentials.NewServerTLSFromFile("cert.pem", "key.pem")
    if err != nil {
        log.Fatalf("Failed to load TLS keys: %v", err)
    }

    // Create gRPC server with interceptors
    server := grpc.NewServer(
        grpc.Creds(creds),
        grpc.ChainUnaryInterceptor(
            loggingInterceptor,
            rateLimitInterceptor,
            authInterceptor,
        ),
        grpc.KeepaliveParams(keepalive.ServerParameters{
            MaxConnectionIdle: 5 * time.Minute,
            MaxConnectionAge:  10 * time.Minute,
            Time:              1 * time.Minute,
            Timeout:           10 * time.Second,
        }),
        grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
            MinTime:             30 * time.Second,
            PermitWithoutStream: true,
        }),
        grpc.MaxRecvMsgSize(10 * 1024 * 1024), // 10MB
        grpc.MaxSendMsgSize(10 * 1024 * 1024), // 10MB
    )

    // Register services
    db := NewDatabase()
    userService := NewUserServer(db)
    pb.RegisterUserServiceServer(server, userService)

    // Register health check
    healthServer := health.NewServer()
    grpc_health_v1.RegisterHealthServer(server, healthServer)
    healthServer.SetServingStatus("user.v1.UserService", grpc_health_v1.HealthCheckResponse_SERVING)

    // Register reflection (for grpcurl, etc.)
    reflection.Register(server)

    // Start server
    lis, err := net.Listen("tcp", ":50051")
    if err != nil {
        log.Fatalf("Failed to listen: %v", err)
    }

    log.Println("gRPC server listening on :50051")
    if err := server.Serve(lis); err != nil {
        log.Fatalf("Failed to serve: %v", err)
    }
}
```

______________________________________________________________________

## Client Implementation

### Go Client with Connection Pool

```go
// client/user_client.go
package client

import (
    "context"
    "fmt"
    "io"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
    "google.golang.org/grpc/credentials/insecure"
    "google.golang.org/grpc/metadata"

    pb "github.com/example/user/v1"
)

type UserClient struct {
    conn   *grpc.ClientConn
    client pb.UserServiceClient
    token  string
}

func NewUserClient(address string, token string, useTLS bool) (*UserClient, error) {
    var opts []grpc.DialOption

    if useTLS {
        creds, err := credentials.NewClientTLSFromFile("ca.pem", "")
        if err != nil {
            return nil, fmt.Errorf("failed to load TLS credentials: %w", err)
        }
        opts = append(opts, grpc.WithTransportCredentials(creds))
    } else {
        opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
    }

    // Connection pool and keepalive
    opts = append(opts,
        grpc.WithKeepaliveParams(keepalive.ClientParameters{
            Time:                1 * time.Minute,
            Timeout:             10 * time.Second,
            PermitWithoutStream: true,
        }),
        grpc.WithDefaultCallOptions(
            grpc.MaxCallRecvMsgSize(10*1024*1024),
            grpc.MaxCallSendMsgSize(10*1024*1024),
        ),
    )

    conn, err := grpc.Dial(address, opts...)
    if err != nil {
        return nil, fmt.Errorf("failed to dial: %w", err)
    }

    return &UserClient{
        conn:   conn,
        client: pb.NewUserServiceClient(conn),
        token:  token,
    }, nil
}

func (c *UserClient) Close() error {
    return c.conn.Close()
}

// Add authorization metadata to context
func (c *UserClient) withAuth(ctx context.Context) context.Context {
    return metadata.AppendToOutgoingContext(ctx, "authorization", c.token)
}

// Get user with retry logic
func (c *UserClient) GetUser(ctx context.Context, id string) (*pb.User, error) {
    ctx = c.withAuth(ctx)
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    resp, err := c.client.GetUser(ctx, &pb.GetUserRequest{Id: id})
    if err != nil {
        return nil, fmt.Errorf("failed to get user: %w", err)
    }

    return resp.User, nil
}

// Stream list users
func (c *UserClient) ListUsers(ctx context.Context, pageSize int32, filter string) ([]*pb.User, error) {
    ctx = c.withAuth(ctx)

    stream, err := c.client.ListUsers(ctx, &pb.ListUsersRequest{
        PageSize: pageSize,
        Filter:   filter,
    })
    if err != nil {
        return nil, fmt.Errorf("failed to list users: %w", err)
    }

    var users []*pb.User
    for {
        user, err := stream.Recv()
        if err == io.EOF {
            break
        }
        if err != nil {
            return nil, fmt.Errorf("failed to receive user: %w", err)
        }
        users = append(users, user)
    }

    return users, nil
}

// Batch create users (client streaming)
func (c *UserClient) BatchCreateUsers(ctx context.Context, requests []*pb.CreateUserRequest) (*pb.BatchCreateUsersResponse, error) {
    ctx = c.withAuth(ctx)

    stream, err := c.client.BatchCreateUsers(ctx)
    if err != nil {
        return nil, fmt.Errorf("failed to start batch create: %w", err)
    }

    // Send all requests
    for _, req := range requests {
        if err := stream.Send(req); err != nil {
            return nil, fmt.Errorf("failed to send create request: %w", err)
        }
    }

    // Close and receive response
    resp, err := stream.CloseAndRecv()
    if err != nil {
        return nil, fmt.Errorf("failed to receive batch response: %w", err)
    }

    return resp, nil
}

// Watch users (bidirectional streaming)
func (c *UserClient) WatchUsers(ctx context.Context, userIDs []string, eventHandler func(*pb.UserEvent)) error {
    ctx = c.withAuth(ctx)

    stream, err := c.client.WatchUsers(ctx)
    if err != nil {
        return fmt.Errorf("failed to start watch: %w", err)
    }

    // Send initial watch request
    if err := stream.Send(&pb.WatchUsersRequest{UserIds: userIDs}); err != nil {
        return fmt.Errorf("failed to send watch request: %w", err)
    }

    // Receive events
    for {
        event, err := stream.Recv()
        if err == io.EOF {
            return nil
        }
        if err != nil {
            return fmt.Errorf("failed to receive event: %w", err)
        }

        eventHandler(event)
    }
}
```

______________________________________________________________________

## Load Balancing and Service Discovery

### Client-Side Load Balancing

```go
// client/loadbalancer.go
package client

import (
    "context"
    "fmt"

    "google.golang.org/grpc"
    "google.golang.org/grpc/balancer/roundrobin"
    "google.golang.org/grpc/resolver"
    "google.golang.org/grpc/resolver/manual"
)

func NewLoadBalancedClient(endpoints []string, token string) (*UserClient, error) {
    // Manual resolver for static endpoints
    r := manual.NewBuilderWithScheme("example")

    var addrs []resolver.Address
    for _, endpoint := range endpoints {
        addrs = append(addrs, resolver.Address{Addr: endpoint})
    }

    // Create connection with round-robin load balancing
    conn, err := grpc.Dial(
        r.Scheme()+":///unused",
        grpc.WithResolvers(r),
        grpc.WithDefaultServiceConfig(fmt.Sprintf(`{"loadBalancingPolicy":"%s"}`, roundrobin.Name)),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    if err != nil {
        return nil, fmt.Errorf("failed to dial: %w", err)
    }

    // Update resolver with addresses
    r.UpdateState(resolver.State{Addresses: addrs})

    return &UserClient{
        conn:   conn,
        client: pb.NewUserServiceClient(conn),
        token:  token,
    }, nil
}
```

______________________________________________________________________

## Observability

### Prometheus Metrics

```go
// middleware/metrics.go
package middleware

import (
    "context"
    "time"

    "github.com/prometheus/client_golang/prometheus"
    "google.golang.org/grpc"
    "google.golang.org/grpc/status"
)

var (
    grpcRequestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "grpc_requests_total",
            Help: "Total number of gRPC requests",
        },
        []string{"method", "status"},
    )

    grpcRequestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "grpc_request_duration_seconds",
            Help:    "Duration of gRPC requests",
            Buckets: prometheus.DefBuckets,
        },
        []string{"method"},
    )
)

func init() {
    prometheus.MustRegister(grpcRequestsTotal)
    prometheus.MustRegister(grpcRequestDuration)
}

func MetricsInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    start := time.Now()

    resp, err := handler(ctx, req)

    duration := time.Since(start).Seconds()
    statusCode := "OK"
    if err != nil {
        statusCode = status.Code(err).String()
    }

    grpcRequestsTotal.WithLabelValues(info.FullMethod, statusCode).Inc()
    grpcRequestDuration.WithLabelValues(info.FullMethod).Observe(duration)

    return resp, err
}
```

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `grpc-specialist` - gRPC service design and optimization
- `architecture-council` - Microservices architecture
- `observability-incident-lead` - Performance optimization

**Supporting Specialists**:

- `golang-pro` - Go implementation
- `python-pro` - Python client implementation
- `docker-specialist` - Containerization

**Quality & Operations**:

- `qa-strategist` - Testing strategies
- `observability-incident-lead` - Monitoring and tracing
- `security-auditor` - Security review

______________________________________________________________________

## Security Considerations

### TLS/SSL Configuration

**Server-side TLS**:

```go
// server/main.go
import (
    "crypto/tls"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
)

func main() {
    // Load TLS certificate
    cert, err := tls.LoadX509KeyPair("server.crt", "server.key")
    if err != nil {
        log.Fatalf("Failed to load key pair: %v", err)
    }

    // Create TLS credentials
    tlsConfig := &tls.Config{
        Certificates: []tls.Certificate{cert},
        ClientAuth:   tls.RequireAndVerifyClientCert, // mTLS
        MinVersion:   tls.VersionTLS13,
    }

    creds := credentials.NewTLS(tlsConfig)

    // Create server with TLS
    server := grpc.NewServer(grpc.Creds(creds))

    userv1.RegisterUserServiceServer(server, &userServer{})

    listener, _ := net.Listen("tcp", ":50051")
    server.Serve(listener)
}
```

**Client-side TLS**:

```go
// client/main.go
func main() {
    // Load CA certificate
    caCert, err := os.ReadFile("ca.crt")
    if err != nil {
        log.Fatal(err)
    }

    certPool := x509.NewCertPool()
    certPool.AppendCertsFromPEM(caCert)

    // Create TLS credentials
    creds := credentials.NewTLS(&tls.Config{
        RootCAs:    certPool,
        MinVersion: tls.VersionTLS13,
    })

    // Connect with TLS
    conn, err := grpc.Dial(
        "localhost:50051",
        grpc.WithTransportCredentials(creds),
    )
    defer conn.Close()

    client := userv1.NewUserServiceClient(conn)
}
```

### Authentication & Authorization

**Token-based Authentication (Interceptor)**:

```go
// server/auth_interceptor.go
import (
    "context"
    "strings"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/status"
)

type AuthInterceptor struct {
    jwtSecret string
}

func (i *AuthInterceptor) Unary() grpc.UnaryServerInterceptor {
    return func(
        ctx context.Context,
        req interface{},
        info *grpc.UnaryServerInfo,
        handler grpc.UnaryHandler,
    ) (interface{}, error) {
        // Skip auth for certain methods
        if isPublicMethod(info.FullMethod) {
            return handler(ctx, req)
        }

        // Extract metadata
        md, ok := metadata.FromIncomingContext(ctx)
        if !ok {
            return nil, status.Error(codes.Unauthenticated, "missing metadata")
        }

        // Get authorization header
        values := md.Get("authorization")
        if len(values) == 0 {
            return nil, status.Error(codes.Unauthenticated, "missing token")
        }

        token := strings.TrimPrefix(values[0], "Bearer ")

        // Verify token
        claims, err := verifyJWT(token, i.jwtSecret)
        if err != nil {
            return nil, status.Error(codes.Unauthenticated, "invalid token")
        }

        // Add user info to context
        ctx = context.WithValue(ctx, "user_id", claims.UserID)
        ctx = context.WithValue(ctx, "roles", claims.Roles)

        return handler(ctx, req)
    }
}

func isPublicMethod(method string) bool {
    publicMethods := map[string]bool{
        "/user.v1.UserService/HealthCheck": true,
    }
    return publicMethods[method]
}
```

**Client sending token**:

```go
// client/main.go
type TokenAuth struct {
    token string
}

func (t TokenAuth) GetRequestMetadata(ctx context.Context, uri ...string) (map[string]string, error) {
    return map[string]string{
        "authorization": "Bearer " + t.token,
    }, nil
}

func (TokenAuth) RequireTransportSecurity() bool {
    return true // Require TLS
}

func main() {
    token := "your-jwt-token"

    conn, err := grpc.Dial(
        "localhost:50051",
        grpc.WithTransportCredentials(credentials.NewTLS(&tls.Config{})),
        grpc.WithPerRPCCredentials(TokenAuth{token: token}),
    )

    client := userv1.NewUserServiceClient(conn)
}
```

### Input Validation

**Validate proto messages**:

```go
// server/validation.go
import (
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

func (s *userServer) CreateUser(ctx context.Context, req *userv1.CreateUserRequest) (*userv1.CreateUserResponse, error) {
    // Validate required fields
    if req.GetEmail() == "" {
        return nil, status.Error(codes.InvalidArgument, "email is required")
    }

    if req.GetUsername() == "" {
        return nil, status.Error(codes.InvalidArgument, "username is required")
    }

    // Validate email format
    if !isValidEmail(req.GetEmail()) {
        return nil, status.Error(codes.InvalidArgument, "invalid email format")
    }

    // Validate length constraints
    if len(req.GetUsername()) < 3 || len(req.GetUsername()) > 50 {
        return nil, status.Error(codes.InvalidArgument, "username must be 3-50 characters")
    }

    // Sanitize inputs
    sanitizedUsername := sanitizeString(req.GetUsername())

    // Continue with business logic
    user, err := s.db.CreateUser(ctx, sanitizedUsername, req.GetEmail())
    if err != nil {
        return nil, status.Error(codes.Internal, "failed to create user")
    }

    return &userv1.CreateUserResponse{User: user}, nil
}
```

### Rate Limiting

**Rate limiting interceptor**:

```go
// server/rate_limit.go
import (
    "context"
    "sync"
    "time"

    "golang.org/x/time/rate"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

type RateLimiter struct {
    limiters map[string]*rate.Limiter
    mu       sync.RWMutex
    rate     rate.Limit
    burst    int
}

func NewRateLimiter(r rate.Limit, b int) *RateLimiter {
    return &RateLimiter{
        limiters: make(map[string]*rate.Limiter),
        rate:     r,
        burst:    b,
    }
}

func (rl *RateLimiter) getLimiter(key string) *rate.Limiter {
    rl.mu.Lock()
    defer rl.mu.Unlock()

    limiter, exists := rl.limiters[key]
    if !exists {
        limiter = rate.NewLimiter(rl.rate, rl.burst)
        rl.limiters[key] = limiter
    }

    return limiter
}

func (rl *RateLimiter) UnaryInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    // Get user ID from context (set by auth interceptor)
    userID, _ := ctx.Value("user_id").(string)
    if userID == "" {
        userID = "anonymous"
    }

    limiter := rl.getLimiter(userID)

    if !limiter.Allow() {
        return nil, status.Error(codes.ResourceExhausted, "rate limit exceeded")
    }

    return handler(ctx, req)
}
```

### Security Checklist

- [ ] TLS 1.3 enabled for all connections
- [ ] Certificate rotation automated
- [ ] mTLS configured for service-to-service communication
- [ ] JWT authentication implemented
- [ ] Authorization checks on all sensitive methods
- [ ] Input validation on all requests
- [ ] Rate limiting per user/IP implemented
- [ ] SQL injection protection (use parameterized queries)
- [ ] No sensitive data in logs
- [ ] Error messages don't leak internal details
- [ ] Security headers configured
- [ ] Regular security audits performed
- [ ] Dependency vulnerabilities scanned

______________________________________________________________________

## Testing & Validation

### Unit Testing gRPC Services

```go
// server/user_service_test.go
package server

import (
    "context"
    "testing"

    userv1 "github.com/example/user/v1"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

// Mock database
type MockDB struct {
    mock.Mock
}

func (m *MockDB) GetUser(ctx context.Context, id string) (*userv1.User, error) {
    args := m.Called(ctx, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*userv1.User), args.Error(1)
}

func TestGetUser_Success(t *testing.T) {
    // Setup
    mockDB := new(MockDB)
    server := &userServer{db: mockDB}

    expectedUser := &userv1.User{
        Id:       "123",
        Email:    "test@example.com",
        Username: "testuser",
    }

    mockDB.On("GetUser", mock.Anything, "123").Return(expectedUser, nil)

    // Execute
    req := &userv1.GetUserRequest{Id: "123"}
    resp, err := server.GetUser(context.Background(), req)

    // Assert
    assert.NoError(t, err)
    assert.Equal(t, expectedUser, resp.GetUser())
    mockDB.AssertExpectations(t)
}

func TestGetUser_NotFound(t *testing.T) {
    mockDB := new(MockDB)
    server := &userServer{db: mockDB}

    mockDB.On("GetUser", mock.Anything, "999").Return(nil, ErrNotFound)

    req := &userv1.GetUserRequest{Id: "999"}
    resp, err := server.GetUser(context.Background(), req)

    assert.Nil(t, resp)
    assert.Error(t, err)

    st, ok := status.FromError(err)
    assert.True(t, ok)
    assert.Equal(t, codes.NotFound, st.Code())
}

func TestCreateUser_ValidationError(t *testing.T) {
    server := &userServer{db: nil}

    req := &userv1.CreateUserRequest{
        Email:    "", // Invalid: empty email
        Username: "testuser",
    }

    resp, err := server.CreateUser(context.Background(), req)

    assert.Nil(t, resp)
    assert.Error(t, err)

    st, ok := status.FromError(err)
    assert.True(t, ok)
    assert.Equal(t, codes.InvalidArgument, st.Code())
}
```

### Integration Testing

```go
// integration/user_service_test.go
package integration

import (
    "context"
    "net"
    "testing"

    userv1 "github.com/example/user/v1"
    "github.com/stretchr/testify/assert"
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    "google.golang.org/grpc/test/bufconn"
)

const bufSize = 1024 * 1024

var lis *bufconn.Listener

func init() {
    lis = bufconn.Listen(bufSize)
    server := grpc.NewServer()
    userv1.RegisterUserServiceServer(server, newUserServer())
    go func() {
        if err := server.Serve(lis); err != nil {
            panic(err)
        }
    }()
}

func bufDialer(context.Context, string) (net.Conn, error) {
    return lis.Dial()
}

func TestUserService_Integration(t *testing.T) {
    ctx := context.Background()

    conn, err := grpc.DialContext(
        ctx,
        "bufnet",
        grpc.WithContextDialer(bufDialer),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    assert.NoError(t, err)
    defer conn.Close()

    client := userv1.NewUserServiceClient(conn)

    // Test create user
    createReq := &userv1.CreateUserRequest{
        Email:    "integration@example.com",
        Username: "integrationuser",
    }

    createResp, err := client.CreateUser(ctx, createReq)
    assert.NoError(t, err)
    assert.NotEmpty(t, createResp.GetUser().GetId())

    // Test get user
    getReq := &userv1.GetUserRequest{
        Id: createResp.GetUser().GetId(),
    }

    getResp, err := client.GetUser(ctx, getReq)
    assert.NoError(t, err)
    assert.Equal(t, createReq.GetEmail(), getResp.GetUser().GetEmail())
}
```

### Testing Streaming RPCs

```go
// server/user_service_stream_test.go
func TestListUsers_ServerStreaming(t *testing.T) {
    // Setup in-memory server
    ctx := context.Background()
    conn, err := grpc.DialContext(
        ctx,
        "bufnet",
        grpc.WithContextDialer(bufDialer),
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    assert.NoError(t, err)
    defer conn.Close()

    client := userv1.NewUserServiceClient(conn)

    // Call server streaming RPC
    stream, err := client.ListUsers(ctx, &userv1.ListUsersRequest{})
    assert.NoError(t, err)

    users := make([]*userv1.User, 0)
    for {
        resp, err := stream.Recv()
        if err == io.EOF {
            break
        }
        assert.NoError(t, err)
        users = append(users, resp.GetUser())
    }

    assert.NotEmpty(t, users)
}

func TestBatchCreateUsers_ClientStreaming(t *testing.T) {
    ctx := context.Background()
    conn, _ := grpc.DialContext(ctx, "bufnet", grpc.WithContextDialer(bufDialer), grpc.WithTransportCredentials(insecure.NewCredentials()))
    defer conn.Close()

    client := userv1.NewUserServiceClient(conn)

    stream, err := client.BatchCreateUsers(ctx)
    assert.NoError(t, err)

    // Send multiple requests
    for i := 1; i <= 5; i++ {
        err := stream.Send(&userv1.CreateUserRequest{
            Email:    fmt.Sprintf("user%d@example.com", i),
            Username: fmt.Sprintf("user%d", i),
        })
        assert.NoError(t, err)
    }

    resp, err := stream.CloseAndRecv()
    assert.NoError(t, err)
    assert.Equal(t, int32(5), resp.GetCreatedCount())
}
```

### Load Testing with ghz

```bash
# Install ghz
go install github.com/bojand/ghz/cmd/ghz@latest

# Run load test
ghz --insecure \
    --proto proto/user_service.proto \
    --call user.v1.UserService/GetUser \
    -d '{"id":"123"}' \
    -c 100 \    # 100 concurrent connections
    -n 10000 \  # 10,000 total requests
    localhost:50051
```

**Load test with authentication**:

```bash
ghz --insecure \
    --proto proto/user_service.proto \
    --call user.v1.UserService/GetUser \
    -d '{"id":"123"}' \
    -m '{"authorization":"Bearer YOUR_TOKEN"}' \
    -c 100 -n 10000 \
    localhost:50051
```

### Testing Checklist

- [ ] All RPC methods have unit tests
- [ ] Integration tests cover full client-server workflow
- [ ] Streaming RPCs tested (server, client, bidirectional)
- [ ] Authentication/authorization tested
- [ ] Input validation tested with invalid inputs
- [ ] Error handling tested for all error codes
- [ ] Timeout/deadline behavior tested
- [ ] Interceptors tested independently
- [ ] Load testing performed (>1000 req/s)
- [ ] Connection pooling verified
- [ ] Code coverage ≥80%

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: "rpc error: code = Unavailable desc = connection refused"

**Symptoms:**

- Client cannot connect to server
- "connection refused" errors
- Immediate failure on dial

**Causes:**

- Server not running
- Wrong address/port
- Firewall blocking connection
- Server crashed on startup

**Solutions:**

1. **Verify server is running**:

```bash
# Check if process is listening
lsof -i :50051

# Check server logs
tail -f server.log
```

2. **Test connection**:

```bash
# Using grpcurl
grpcurl -plaintext localhost:50051 list
```

3. **Check firewall**:

```bash
# macOS
sudo pfctl -sr | grep 50051

# Linux
sudo iptables -L -n | grep 50051
```

**Prevention:**

- Implement health check endpoint
- Use proper error logging on startup
- Validate configuration before starting server

______________________________________________________________________

#### Issue: "rpc error: code = DeadlineExceeded"

**Symptoms:**

- Requests timeout
- "deadline exceeded" errors
- Client receives no response

**Causes:**

- Server processing too slow
- Deadline set too short
- Network latency
- Database query timeout

**Solutions:**

1. **Increase client timeout**:

```go
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()

resp, err := client.GetUser(ctx, req)
```

2. **Add server-side logging**:

```go
func (s *userServer) GetUser(ctx context.Context, req *userv1.GetUserRequest) (*userv1.GetUserResponse, error) {
    start := time.Now()
    defer func() {
        log.Printf("GetUser took %v", time.Since(start))
    }()

    // ... implementation
}
```

3. **Check database performance**:

```sql
-- PostgreSQL: Check slow queries
SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

**Prevention:**

- Set reasonable timeouts (5-30s for normal operations)
- Monitor RPC duration metrics
- Optimize database queries
- Use caching for frequent reads

______________________________________________________________________

#### Issue: "rpc error: code = ResourceExhausted"

**Symptoms:**

- Server rejects requests
- "resource exhausted" errors
- Works initially, fails under load

**Causes:**

- Rate limiting triggered
- Connection limit reached
- Memory exhaustion
- Too many concurrent streams

**Solutions:**

1. **Check rate limits**:

```go
// Increase rate limit
limiter := NewRateLimiter(rate.Limit(1000), 100) // 1000 req/s, burst 100
```

2. **Increase connection limits**:

```go
server := grpc.NewServer(
    grpc.MaxConcurrentStreams(1000), // Default is 100
)
```

3. **Monitor resources**:

```bash
# Check memory usage
top -p $(pgrep -f "your-grpc-server")

# Check connection count
netstat -an | grep :50051 | wc -l
```

______________________________________________________________________

#### Issue: TLS Handshake Failures

**Symptoms:**

- "tls: bad certificate" errors
- "x509: certificate signed by unknown authority"
- "transport: authentication handshake failed"

**Causes:**

- Certificate/key mismatch
- Expired certificates
- Wrong CA certificate
- Client and server TLS config mismatch

**Solutions:**

1. **Verify certificates**:

```bash
# Check certificate validity
openssl x509 -in server.crt -text -noout

# Check certificate expiry
openssl x509 -in server.crt -noout -enddate
```

2. **Test TLS connection**:

```bash
# Test with openssl
openssl s_client -connect localhost:50051

# Test with grpcurl
grpcurl -cacert ca.crt localhost:50051 list
```

3. **Debug TLS in code**:

```go
// Enable debug logging
grpc.EnableTracing = true
```

______________________________________________________________________

#### Issue: Streaming RPC Stops Receiving

**Symptoms:**

- Stream receives some messages then stops
- No error received
- Stream appears stuck

**Causes:**

- Server stopped sending
- Context canceled
- Network interruption
- Stream not closed properly

**Solutions:**

1. **Add timeout to stream**:

```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
defer cancel()

stream, err := client.ListUsers(ctx, req)
```

2. **Check for errors properly**:

```go
for {
    resp, err := stream.Recv()
    if err == io.EOF {
        log.Println("Stream completed normally")
        break
    }
    if err != nil {
        log.Printf("Stream error: %v", err)
        break
    }
    // Process resp
}
```

3. **Server-side stream debugging**:

```go
func (s *userServer) ListUsers(req *userv1.ListUsersRequest, stream userv1.UserService_ListUsersServer) error {
    users, err := s.db.GetAllUsers()
    if err != nil {
        return status.Error(codes.Internal, err.Error())
    }

    for _, user := range users {
        if err := stream.Send(&userv1.ListUsersResponse{User: user}); err != nil {
            log.Printf("Failed to send user %s: %v", user.Id, err)
            return err
        }
        log.Printf("Sent user %s", user.Id)
    }

    return nil
}
```

______________________________________________________________________

### Debugging Strategies

1. **Enable gRPC logging**:

```bash
# Set environment variable
export GRPC_GO_LOG_VERBOSITY_LEVEL=99
export GRPC_GO_LOG_SEVERITY_LEVEL=info
```

2. **Use grpcurl for manual testing**:

```bash
# List services
grpcurl -plaintext localhost:50051 list

# Describe service
grpcurl -plaintext localhost:50051 describe user.v1.UserService

# Call method
grpcurl -plaintext -d '{"id":"123"}' localhost:50051 user.v1.UserService/GetUser
```

3. **Add comprehensive logging**:

```go
import "github.com/grpc-ecosystem/go-grpc-middleware/logging/zap"

server := grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        grpc_zap.UnaryServerInterceptor(logger),
    ),
)
```

______________________________________________________________________

### Getting Help

**Check Logs:**

- Server logs for error details
- Client logs for request failures
- System logs for resource issues

**Related Tools:**

- Use `distributed-tracing-setup.md` for request tracing
- Use `debugging-guide.md` for advanced debugging
- Use `observability-incident-lead` agent for optimization

**Agents to Consult:**

- `grpc-specialist` - gRPC specific issues
- `architecture-council` - Architecture decisions
- `observability-incident-lead` - Performance problems
- `security-auditor` - Security concerns

**Known Limitations:**

- HTTP/1.1 proxies don't support gRPC (need HTTP/2)
- Browser JavaScript requires grpc-web (different from standard gRPC)
- Some cloud load balancers need special gRPC configuration
- Reflection API should be disabled in production

______________________________________________________________________

## Best Practices

1. **Protocol Buffers**: Use proper field numbering and never reuse numbers
1. **Error Handling**: Use appropriate gRPC status codes
1. **Streaming**: Use streaming for large datasets or real-time updates
1. **Performance**: Enable HTTP/2 multiplexing and compression
1. **Security**: Always use TLS in production
1. **Observability**: Implement comprehensive logging and metrics
1. **Load Balancing**: Use client-side or proxy load balancing
1. **Timeouts**: Set reasonable deadlines for all RPCs
1. **Retries**: Implement exponential backoff for transient failures
1. **Health Checks**: Implement health check service for monitoring
