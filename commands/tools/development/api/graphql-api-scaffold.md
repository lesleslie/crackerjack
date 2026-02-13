______________________________________________________________________

title: GraphQL API Scaffold
owner: Developer Enablement Guild
last_reviewed: 2025-10-01
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6H9DJ3RDGFNDADS8GNG9522
  category: development/api
  agents:
- graphql-architect
- architecture-council
- qa-strategist
  tags:
- graphql
- api
- schema
- apollo

______________________________________________________________________

## GraphQL API Scaffold Generator

You are a GraphQL API expert specializing in creating production-ready, scalable GraphQL APIs with modern frameworks. Design comprehensive GraphQL implementations with proper schema design, resolver optimization, subscriptions, and federation.

## Context

The user needs to create a GraphQL API with complete implementation including schema, resolvers, DataLoaders, subscriptions, authentication, testing, and deployment configuration. Focus on production-ready code that follows GraphQL best practices.

## Requirements for: $ARGUMENTS

1. **Schema Design**:

   - Type definitions with proper relationships
   - Input types and custom scalars
   - Interface and union types
   - Directive definitions
   - Schema documentation

1. **Resolver Implementation**:

   - Query resolvers with DataLoader pattern
   - Mutation resolvers with validation
   - Subscription resolvers for real-time
   - Field-level resolvers
   - N+1 problem prevention

1. **Performance Optimization**:

   - DataLoader batching and caching
   - Query complexity analysis
   - Depth limiting
   - Pagination (cursor and offset)
   - Response caching

1. **Security**:

   - Authentication and authorization
   - Input validation and sanitization
   - Rate limiting
   - Query cost analysis
   - CORS configuration

1. **Real-time Features**:

   - WebSocket subscriptions
   - PubSub implementation
   - Event filtering
   - Connection management

1. **Testing**:

   - Schema validation tests
   - Resolver unit tests
   - Integration tests
   - Load testing
   - Subscription tests

1. **Federation** (if applicable):

   - Federated schema design
   - Entity resolvers
   - Service composition
   - Gateway configuration

______________________________________________________________________

## Implementation Patterns

### 1. Complete Apollo Server Setup

```typescript
// src/server.ts
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { ApolloServerPluginDrainHttpServer } from '@apollo/server/plugin/drainHttpServer';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { WebSocketServer } from 'ws';
import { useServer } from 'graphql-ws/lib/use/ws';
import express from 'express';
import http from 'http';
import cors from 'cors';
import { typeDefs } from './schema';
import { resolvers } from './resolvers';
import { context } from './context';

const app = express();
const httpServer = http.createServer(app);

// Create schema
const schema = makeExecutableSchema({ typeDefs, resolvers });

// WebSocket server for subscriptions
const wsServer = new WebSocketServer({
  server: httpServer,
  path: '/graphql',
});

const serverCleanup = useServer(
  {
    schema,
    context: async (ctx) => {
      return context({ req: ctx.extra.request });
    },
  },
  wsServer
);

// Apollo Server
const server = new ApolloServer({
  schema,
  plugins: [
    // Drain HTTP server on shutdown
    ApolloServerPluginDrainHttpServer({ httpServer }),

    // Drain WebSocket server on shutdown
    {
      async serverWillStart() {
        return {
          async drainServer() {
            await serverCleanup.dispose();
          },
        };
      },
    },

    // Query complexity plugin
    {
      async requestDidStart() {
        return {
          async didResolveOperation({ request, document }) {
            const complexity = getQueryComplexity({
              schema,
              query: document,
              variables: request.variables,
            });

            if (complexity > 1000) {
              throw new Error(
                `Query is too complex: ${complexity}. Maximum allowed complexity: 1000`
              );
            }
          },
        };
      },
    },
  ],
});

await server.start();

app.use(
  '/graphql',
  cors<cors.CorsRequest>(),
  express.json(),
  expressMiddleware(server, {
    context,
  })
);

const PORT = process.env.PORT || 4000;
httpServer.listen(PORT, () => {
  console.log(`🚀 Server ready at http://localhost:${PORT}/graphql`);
  console.log(`🔌 Subscriptions ready at ws://localhost:${PORT}/graphql`);
});
```

### 2. Schema Design with Best Practices

```graphql
# schema/types.graphql

"""
Custom scalar for DateTime
"""
scalar DateTime

"""
Custom scalar for Email
"""
scalar Email

"""
User account in the system
"""
type User {
  id: ID!
  email: Email!
  username: String!
  profile: UserProfile
  posts(
    first: Int = 10
    after: String
    orderBy: PostOrderBy
  ): PostConnection!
  createdAt: DateTime!
  updatedAt: DateTime!
}

"""
User profile information
"""
type UserProfile {
  id: ID!
  user: User!
  bio: String
  avatar: String
  website: String
}

"""
Blog post
"""
type Post {
  id: ID!
  title: String!
  content: String!
  published: Boolean!
  author: User!
  comments(first: Int = 10, after: String): CommentConnection!
  tags: [Tag!]!
  viewCount: Int!
  createdAt: DateTime!
  updatedAt: DateTime!
}

"""
Post comment
"""
type Comment {
  id: ID!
  content: String!
  author: User!
  post: Post!
  createdAt: DateTime!
}

"""
Post tag
"""
type Tag {
  id: ID!
  name: String!
  posts(first: Int, after: String): PostConnection!
}

"""
Cursor-based pagination for posts
"""
type PostConnection {
  edges: [PostEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type PostEdge {
  cursor: String!
  node: Post!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

"""
Post ordering options
"""
enum PostOrderBy {
  CREATED_AT_ASC
  CREATED_AT_DESC
  TITLE_ASC
  TITLE_DESC
  VIEW_COUNT_DESC
}

"""
Input for creating a post
"""
input CreatePostInput {
  title: String!
  content: String!
  tags: [String!]
  published: Boolean = false
}

"""
Input for updating a post
"""
input UpdatePostInput {
  title: String
  content: String
  tags: [String!]
  published: Boolean
}

"""
Queries
"""
type Query {
  """Get current user"""
  me: User

  """Get user by ID"""
  user(id: ID!): User

  """Search users"""
  users(
    query: String
    first: Int = 10
    after: String
  ): UserConnection!

  """Get post by ID"""
  post(id: ID!): Post

  """Get all posts with filtering"""
  posts(
    published: Boolean
    authorId: ID
    tag: String
    first: Int = 10
    after: String
    orderBy: PostOrderBy = CREATED_AT_DESC
  ): PostConnection!
}

"""
Mutations
"""
type Mutation {
  """Create a new post"""
  createPost(input: CreatePostInput!): Post!

  """Update an existing post"""
  updatePost(id: ID!, input: UpdatePostInput!): Post!

  """Delete a post"""
  deletePost(id: ID!): Boolean!

  """Publish a post"""
  publishPost(id: ID!): Post!

  """Add comment to post"""
  addComment(postId: ID!, content: String!): Comment!

  """Delete comment"""
  deleteComment(id: ID!): Boolean!
}

"""
Subscriptions for real-time updates
"""
type Subscription {
  """Subscribe to new posts"""
  postCreated(authorId: ID): Post!

  """Subscribe to post updates"""
  postUpdated(id: ID!): Post!

  """Subscribe to new comments on a post"""
  commentAdded(postId: ID!): Comment!
}
```

### 3. Resolver Implementation with DataLoader

```typescript
// src/resolvers/index.ts
import { GraphQLError } from 'graphql';
import { PubSub } from 'graphql-subscriptions';
import DataLoader from 'dataloader';

const pubsub = new PubSub();

// DataLoader for batching user queries
const createUserLoader = (prisma) =>
  new DataLoader(async (userIds: number[]) => {
    const users = await prisma.user.findMany({
      where: { id: { in: userIds } },
    });

    const userMap = new Map(users.map(user => [user.id, user]));
    return userIds.map(id => userMap.get(id) || null);
  });

// DataLoader for batching post queries
const createPostLoader = (prisma) =>
  new DataLoader(async (postIds: number[]) => {
    const posts = await prisma.post.findMany({
      where: { id: { in: postIds } },
    });

    const postMap = new Map(posts.map(post => [post.id, post]));
    return postIds.map(id => postMap.get(id) || null);
  });

export const resolvers = {
  Query: {
    me: async (_, __, { user }) => {
      if (!user) {
        throw new GraphQLError('Not authenticated', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }
      return user;
    },

    user: async (_, { id }, { prisma, userLoader }) => {
      return userLoader.load(parseInt(id));
    },

    users: async (_, { query, first, after }, { prisma }) => {
      const cursor = after ? { id: parseInt(after) } : undefined;

      const users = await prisma.user.findMany({
        where: query
          ? {
              OR: [
                { username: { contains: query } },
                { email: { contains: query } },
              ],
            }
          : undefined,
        take: first + 1,
        cursor,
        orderBy: { createdAt: 'desc' },
      });

      const hasNextPage = users.length > first;
      const edges = users.slice(0, first).map(user => ({
        cursor: user.id.toString(),
        node: user,
      }));

      return {
        edges,
        pageInfo: {
          hasNextPage,
          hasPreviousPage: !!after,
          startCursor: edges[0]?.cursor,
          endCursor: edges[edges.length - 1]?.cursor,
        },
        totalCount: await prisma.user.count(),
      };
    },

    post: async (_, { id }, { prisma, postLoader }) => {
      return postLoader.load(parseInt(id));
    },

    posts: async (
      _,
      { published, authorId, tag, first, after, orderBy },
      { prisma }
    ) => {
      const cursor = after ? { id: parseInt(after) } : undefined;

      const orderByMap = {
        CREATED_AT_ASC: { createdAt: 'asc' },
        CREATED_AT_DESC: { createdAt: 'desc' },
        TITLE_ASC: { title: 'asc' },
        TITLE_DESC: { title: 'desc' },
        VIEW_COUNT_DESC: { viewCount: 'desc' },
      };

      const posts = await prisma.post.findMany({
        where: {
          ...(published !== undefined && { published }),
          ...(authorId && { authorId: parseInt(authorId) }),
          ...(tag && {
            tags: {
              some: { name: tag },
            },
          }),
        },
        take: first + 1,
        cursor,
        orderBy: orderByMap[orderBy] || orderByMap.CREATED_AT_DESC,
      });

      const hasNextPage = posts.length > first;
      const edges = posts.slice(0, first).map(post => ({
        cursor: post.id.toString(),
        node: post,
      }));

      return {
        edges,
        pageInfo: {
          hasNextPage,
          hasPreviousPage: !!after,
          startCursor: edges[0]?.cursor,
          endCursor: edges[edges.length - 1]?.cursor,
        },
        totalCount: await prisma.post.count(),
      };
    },
  },

  Mutation: {
    createPost: async (_, { input }, { prisma, user }) => {
      if (!user) {
        throw new GraphQLError('Not authenticated', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }

      const post = await prisma.post.create({
        data: {
          ...input,
          authorId: user.id,
          tags: {
            connectOrCreate: input.tags?.map(name => ({
              where: { name },
              create: { name },
            })),
          },
        },
        include: { author: true, tags: true },
      });

      // Publish to subscribers
      pubsub.publish('POST_CREATED', { postCreated: post });

      return post;
    },

    updatePost: async (_, { id, input }, { prisma, user }) => {
      if (!user) {
        throw new GraphQLError('Not authenticated', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }

      // Check ownership
      const post = await prisma.post.findUnique({
        where: { id: parseInt(id) },
      });

      if (!post || post.authorId !== user.id) {
        throw new GraphQLError('Not authorized', {
          extensions: { code: 'FORBIDDEN' },
        });
      }

      const updated = await prisma.post.update({
        where: { id: parseInt(id) },
        data: {
          ...input,
          ...(input.tags && {
            tags: {
              set: [],
              connectOrCreate: input.tags.map(name => ({
                where: { name },
                create: { name },
              })),
            },
          }),
        },
        include: { author: true, tags: true },
      });

      pubsub.publish('POST_UPDATED', { postUpdated: updated });

      return updated;
    },

    publishPost: async (_, { id }, { prisma, user }) => {
      if (!user) {
        throw new GraphQLError('Not authenticated', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }

      const post = await prisma.post.update({
        where: { id: parseInt(id) },
        data: { published: true },
        include: { author: true, tags: true },
      });

      pubsub.publish('POST_CREATED', { postCreated: post });

      return post;
    },

    addComment: async (_, { postId, content }, { prisma, user }) => {
      if (!user) {
        throw new GraphQLError('Not authenticated', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }

      const comment = await prisma.comment.create({
        data: {
          content,
          postId: parseInt(postId),
          authorId: user.id,
        },
        include: { author: true, post: true },
      });

      pubsub.publish('COMMENT_ADDED', { commentAdded: comment });

      return comment;
    },
  },

  Subscription: {
    postCreated: {
      subscribe: (_, { authorId }) => {
        if (authorId) {
          return pubsub.asyncIterator([`POST_CREATED_${authorId}`]);
        }
        return pubsub.asyncIterator(['POST_CREATED']);
      },
    },

    postUpdated: {
      subscribe: (_, { id }) => {
        return pubsub.asyncIterator([`POST_UPDATED_${id}`]);
      },
    },

    commentAdded: {
      subscribe: (_, { postId }) => {
        return pubsub.asyncIterator([`COMMENT_ADDED_${postId}`]);
      },
    },
  },

  // Field resolvers
  User: {
    posts: async (user, { first, after, orderBy }, { prisma }) => {
      // Reuse posts query logic
      return resolvers.Query.posts(
        null,
        { authorId: user.id, first, after, orderBy },
        { prisma }
      );
    },

    profile: async (user, _, { prisma }) => {
      return prisma.userProfile.findUnique({
        where: { userId: user.id },
      });
    },
  },

  Post: {
    author: async (post, _, { userLoader }) => {
      return userLoader.load(post.authorId);
    },

    comments: async (post, { first, after }, { prisma }) => {
      const cursor = after ? { id: parseInt(after) } : undefined;

      const comments = await prisma.comment.findMany({
        where: { postId: post.id },
        take: first + 1,
        cursor,
        orderBy: { createdAt: 'desc' },
      });

      const hasNextPage = comments.length > first;
      const edges = comments.slice(0, first).map(comment => ({
        cursor: comment.id.toString(),
        node: comment,
      }));

      return {
        edges,
        pageInfo: {
          hasNextPage,
          hasPreviousPage: !!after,
          startCursor: edges[0]?.cursor,
          endCursor: edges[edges.length - 1]?.cursor,
        },
        totalCount: await prisma.comment.count({ where: { postId: post.id } }),
      };
    },

    tags: async (post, _, { prisma }) => {
      return prisma.tag.findMany({
        where: {
          posts: {
            some: { id: post.id },
          },
        },
      });
    },
  },

  Comment: {
    author: async (comment, _, { userLoader }) => {
      return userLoader.load(comment.authorId);
    },

    post: async (comment, _, { postLoader }) => {
      return postLoader.load(comment.postId);
    },
  },
};
```

### 4. Context and Authentication

```typescript
// src/context.ts
import { PrismaClient } from '@prisma/client';
import jwt from 'jsonwebtoken';
import DataLoader from 'dataloader';

const prisma = new PrismaClient();

export interface Context {
  prisma: PrismaClient;
  user: any | null;
  userLoader: DataLoader<number, any>;
  postLoader: DataLoader<number, any>;
}

export async function context({ req }): Promise<Context> {
  // Extract token from headers
  const token = req.headers.authorization?.replace('Bearer ', '');

  let user = null;
  if (token) {
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET!);
      user = await prisma.user.findUnique({
        where: { id: decoded.userId },
      });
    } catch (error) {
      console.error('Invalid token:', error);
    }
  }

  return {
    prisma,
    user,
    userLoader: createUserLoader(prisma),
    postLoader: createPostLoader(prisma),
  };
}
```

### 5. Query Complexity and Rate Limiting

```typescript
// src/plugins/complexity.ts
import { getComplexity, simpleEstimator, fieldExtensionsEstimator } from 'graphql-query-complexity';
import { GraphQLError } from 'graphql';

export const complexityPlugin = {
  async requestDidStart() {
    return {
      async didResolveOperation({ request, document, schema }) {
        const complexity = getComplexity({
          schema,
          query: document,
          variables: request.variables,
          estimators: [
            fieldExtensionsEstimator(),
            simpleEstimator({ defaultComplexity: 1 }),
          ],
        });

        const maxComplexity = 1000;
        if (complexity > maxComplexity) {
          throw new GraphQLError(
            `Query is too complex: ${complexity}. Maximum allowed complexity: ${maxComplexity}`,
            {
              extensions: {
                code: 'QUERY_TOO_COMPLEX',
                complexity,
                maxComplexity,
              },
            }
          );
        }

        console.log('Query complexity:', complexity);
      },
    };
  },
};

// src/plugins/rateLimiting.ts
import { RateLimiterMemory } from 'rate-limiter-flexible';
import { GraphQLError } from 'graphql';

const rateLimiter = new RateLimiterMemory({
  points: 100, // Number of requests
  duration: 60, // Per 60 seconds
});

export const rateLimitPlugin = {
  async requestDidStart({ request }) {
    return {
      async didResolveOperation({ contextValue }) {
        const key = contextValue.user?.id || contextValue.req.ip;

        try {
          await rateLimiter.consume(key);
        } catch (error) {
          throw new GraphQLError('Rate limit exceeded', {
            extensions: {
              code: 'RATE_LIMIT_EXCEEDED',
              retryAfter: error.msBeforeNext / 1000,
            },
          });
        }
      },
    };
  },
};
```

### 6. Testing

```typescript
// tests/graphql/post.test.ts
import { ApolloServer } from '@apollo/server';
import { typeDefs } from '../../src/schema';
import { resolvers } from '../../src/resolvers';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

describe('Post Queries', () => {
  let server: ApolloServer;

  beforeAll(async () => {
    server = new ApolloServer({
      typeDefs,
      resolvers,
    });
  });

  after all(async () => {
    await prisma.$disconnect();
  });

  it('fetches posts with pagination', async () => {
    const result = await server.executeOperation({
      query: `
        query GetPosts($first: Int, $after: String) {
          posts(first: $first, after: $after) {
            edges {
              cursor
              node {
                id
                title
                author {
                  username
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      `,
      variables: { first: 10 },
    });

    expect(result.body.kind).toBe('single');
    if (result.body.kind === 'single') {
      expect(result.body.singleResult.errors).toBeUndefined();
      expect(result.body.singleResult.data?.posts).toBeDefined();
    }
  });

  it('creates a post with authentication', async () => {
    const user = await prisma.user.create({
      data: {
        email: 'test@example.com',
        username: 'testuser',
      },
    });

    const result = await server.executeOperation(
      {
        query: `
          mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
              id
              title
              content
              author {
                username
              }
            }
          }
        `,
        variables: {
          input: {
            title: 'Test Post',
            content: 'Test content',
            published: true,
          },
        },
      },
      {
        contextValue: { prisma, user },
      }
    );

    expect(result.body.kind).toBe('single');
    if (result.body.kind === 'single') {
      expect(result.body.singleResult.errors).toBeUndefined();
      expect(result.body.singleResult.data?.createPost.title).toBe('Test Post');
    }
  });
});
```

### 7. Federation Setup

```typescript
// src/federation.ts
import { buildSubgraphSchema } from '@apollo/subgraph';
import { gql } from 'graphql-tag';

const typeDefs = gql`
  extend schema
    @link(url: "https://specs.apollo.dev/federation/v2.3", import: ["@key", "@shareable"])

  type User @key(fields: "id") {
    id: ID!
    email: String! @shareable
    posts: [Post!]!
  }

  type Post @key(fields: "id") {
    id: ID!
    title: String!
    author: User!
  }
`;

const resolvers = {
  User: {
    __resolveReference: async (reference, { prisma }) => {
      return prisma.user.findUnique({
        where: { id: parseInt(reference.id) },
      });
    },
    posts: async (user, _, { prisma }) => {
      return prisma.post.findMany({
        where: { authorId: user.id },
      });
    },
  },

  Post: {
    __resolveReference: async (reference, { prisma }) => {
      return prisma.post.findUnique({
        where: { id: parseInt(reference.id) },
      });
    },
  },
};

export const schema = buildSubgraphSchema({ typeDefs, resolvers });
```

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `graphql-architect` - GraphQL schema design and optimization
- `architecture-council` - API architecture and patterns
- `typescript-pro` - TypeScript implementation

**Supporting Specialists**:

- `postgresql-specialist` - Database optimization
- `redis-specialist` - Caching strategies
- `websocket-specialist` - Real-time subscriptions

**Quality & Security**:

- `qa-strategist` - Testing strategies
- `security-auditor` - API security review
- `observability-incident-lead` - Query optimization

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

**JWT-based Authentication**:

```typescript
// src/auth.ts
import jwt from 'jsonwebtoken';
import { GraphQLError } from 'graphql';

export function requireAuth(user: any) {
  if (!user) {
    throw new GraphQLError('Authentication required', {
      extensions: { code: 'UNAUTHENTICATED' },
    });
  }
}

export function requireRole(user: any, role: string) {
  requireAuth(user);
  if (!user.roles.includes(role)) {
    throw new GraphQLError('Insufficient permissions', {
      extensions: { code: 'FORBIDDEN' },
    });
  }
}
```

**Field-level Authorization**:

```typescript
// src/directives/auth.ts
import { getDirective, MapperKind, mapSchema } from '@graphql-tools/utils';
import { GraphQLSchema } from 'graphql';

export function authDirective(directiveName: string = 'auth') {
  return {
    authDirectiveTypeDefs: `directive @${directiveName}(requires: Role = USER) on FIELD_DEFINITION`,
    authDirectiveTransformer: (schema: GraphQLSchema) =>
      mapSchema(schema, {
        [MapperKind.OBJECT_FIELD]: (fieldConfig) => {
          const authDirective = getDirective(schema, fieldConfig, directiveName)?.[0];
          if (authDirective) {
            const { requires } = authDirective;
            const { resolve = defaultFieldResolver } = fieldConfig;

            fieldConfig.resolve = async function (source, args, context, info) {
              const user = context.user;
              if (!user) {
                throw new GraphQLError('Not authenticated');
              }
              if (requires && !user.roles.includes(requires)) {
                throw new GraphQLError('Not authorized');
              }
              return resolve(source, args, context, info);
            };
          }
          return fieldConfig;
        },
      }),
  };
}
```

### Input Validation & Sanitization

**Validate all inputs**:

```typescript
// src/validation/schema.ts
import { z } from 'zod';

export const CreatePostSchema = z.object({
  title: z.string().min(3).max(200),
  content: z.string().min(10).max(10000),
  tags: z.array(z.string().min(1).max(50)).max(10).optional(),
  published: z.boolean().default(false),
});

// In resolver
createPost: async (_, { input }, { prisma, user }) => {
  requireAuth(user);

  // Validate input
  const validated = CreatePostSchema.parse(input);

  // Sanitize HTML content
  const sanitizedContent = sanitizeHtml(validated.content, {
    allowedTags: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
  });

  return prisma.post.create({
    data: { ...validated, content: sanitizedContent, authorId: user.id },
  });
};
```

### Query Security

**Depth Limiting**:

```typescript
// src/plugins/depthLimit.ts
import depthLimit from 'graphql-depth-limit';

const server = new ApolloServer({
  schema,
  validationRules: [depthLimit(7)], // Max depth of 7
});
```

**Persisted Queries** (production):

```typescript
// Only allow pre-approved queries in production
import { createPersistedQueryLink } from '@apollo/client/link/persisted-queries';

const server = new ApolloServer({
  schema,
  persistedQueries: {
    cache: new RedisCache({ host: 'localhost' }),
  },
  plugins: [
    {
      async requestDidStart() {
        return {
          async didResolveOperation({ request }) {
            if (process.env.NODE_ENV === 'production' && !request.extensions?.persistedQuery) {
              throw new GraphQLError('Only persisted queries allowed in production');
            }
          },
        };
      },
    },
  ],
});
```

### Rate Limiting & DoS Protection

**Per-field Cost Analysis**:

```graphql
type Query {
  # Expensive query: costs 50 points
  users(first: Int): [User!]! @cost(complexity: 50, multipliers: ["first"])

  # Cheap query: costs 1 point
  me: User @cost(complexity: 1)
}
```

**IP-based Rate Limiting**:

```typescript
import { RateLimiterRedis } from 'rate-limiter-flexible';
import Redis from 'ioredis';

const redis = new Redis();
const rateLimiter = new RateLimiterRedis({
  storeClient: redis,
  points: 1000, // Points
  duration: 3600, // Per hour
  blockDuration: 3600, // Block for 1 hour if exceeded
});

app.use(async (req, res, next) => {
  try {
    await rateLimiter.consume(req.ip);
    next();
  } catch (error) {
    res.status(429).send('Too Many Requests');
  }
});
```

### CORS Configuration

```typescript
app.use('/graphql', cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
  credentials: true,
  maxAge: 86400, // 24 hours
}));
```

### Security Checklist

- [ ] JWT tokens stored securely (httpOnly cookies or secure storage)
- [ ] All mutations require authentication
- [ ] Field-level authorization implemented for sensitive data
- [ ] Input validation on all mutations
- [ ] HTML/SQL injection prevention (sanitization)
- [ ] Query depth limiting enabled (max 7 levels)
- [ ] Query complexity limiting enabled (max 1000 points)
- [ ] Rate limiting per user/IP
- [ ] CORS properly configured
- [ ] HTTPS enforced in production
- [ ] Introspection disabled in production
- [ ] Error messages don't leak sensitive data
- [ ] Persisted queries enabled in production (optional)
- [ ] Regular security audits performed

______________________________________________________________________

## Testing & Validation

### Unit Testing Resolvers

```typescript
// tests/resolvers/post.test.ts
import { resolvers } from '../../src/resolvers';
import { PrismaClient } from '@prisma/client';
import { mockDeep, mockReset } from 'jest-mock-extended';

const prismaMock = mockDeep<PrismaClient>();

beforeEach(() => {
  mockReset(prismaMock);
});

describe('Post Resolvers', () => {
  describe('Query.posts', () => {
    it('returns paginated posts', async () => {
      const mockPosts = [
        { id: 1, title: 'Post 1', authorId: 1, createdAt: new Date() },
        { id: 2, title: 'Post 2', authorId: 1, createdAt: new Date() },
      ];

      prismaMock.post.findMany.mockResolvedValue(mockPosts);
      prismaMock.post.count.mockResolvedValue(2);

      const result = await resolvers.Query.posts(
        null,
        { first: 10, orderBy: 'CREATED_AT_DESC' },
        { prisma: prismaMock }
      );

      expect(result.edges).toHaveLength(2);
      expect(result.totalCount).toBe(2);
      expect(prismaMock.post.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          take: 11,
          orderBy: { createdAt: 'desc' },
        })
      );
    });

    it('filters posts by author', async () => {
      const mockPosts = [
        { id: 1, title: 'Post 1', authorId: 1, createdAt: new Date() },
      ];

      prismaMock.post.findMany.mockResolvedValue(mockPosts);
      prismaMock.post.count.mockResolvedValue(1);

      const result = await resolvers.Query.posts(
        null,
        { first: 10, authorId: '1' },
        { prisma: prismaMock }
      );

      expect(prismaMock.post.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            authorId: 1,
          }),
        })
      );
    });
  });

  describe('Mutation.createPost', () => {
    it('creates post when authenticated', async () => {
      const user = { id: 1, email: 'test@example.com' };
      const mockPost = {
        id: 1,
        title: 'Test Post',
        content: 'Test content',
        authorId: 1,
        author: user,
        tags: [],
      };

      prismaMock.post.create.mockResolvedValue(mockPost);

      const result = await resolvers.Mutation.createPost(
        null,
        {
          input: {
            title: 'Test Post',
            content: 'Test content',
            published: false,
          },
        },
        { prisma: prismaMock, user }
      );

      expect(result.title).toBe('Test Post');
      expect(prismaMock.post.create).toHaveBeenCalled();
    });

    it('throws error when not authenticated', async () => {
      await expect(
        resolvers.Mutation.createPost(
          null,
          { input: { title: 'Test', content: 'Test' } },
          { prisma: prismaMock, user: null }
        )
      ).rejects.toThrow('Not authenticated');
    });
  });
});
```

### Integration Testing

```typescript
// tests/integration/graphql.test.ts
import { ApolloServer } from '@apollo/server';
import { schema } from '../../src/schema';
import { context } from '../../src/context';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const server = new ApolloServer({ schema });

beforeAll(async () => {
  // Seed test database
  await prisma.user.create({
    data: { email: 'test@example.com', username: 'testuser' },
  });
});

after all(async () => {
  await prisma.$disconnect();
});

describe('GraphQL Integration Tests', () => {
  it('executes full query workflow', async () => {
    // 1. Query posts
    const postsResult = await server.executeOperation({
      query: `
        query GetPosts {
          posts(first: 10) {
            edges {
              node {
                id
                title
              }
            }
          }
        }
      `,
    });

    expect(postsResult.body.kind).toBe('single');

    // 2. Create post (authenticated)
    const user = await prisma.user.findFirst();
    const createResult = await server.executeOperation(
      {
        query: `
          mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
              id
              title
            }
          }
        `,
        variables: {
          input: {
            title: 'Integration Test Post',
            content: 'Content',
            published: true,
          },
        },
      },
      { contextValue: await context({ req: { headers: {}, user } }) }
    );

    expect(createResult.body.kind).toBe('single');
  });
});
```

### Schema Validation Tests

```typescript
// tests/schema/validation.test.ts
import { buildSchema, validateSchema } from 'graphql';
import { typeDefs } from '../../src/schema';

describe('Schema Validation', () => {
  it('schema is valid GraphQL', () => {
    const schema = buildSchema(typeDefs);
    const errors = validateSchema(schema);
    expect(errors).toHaveLength(0);
  });

  it('all types have descriptions', () => {
    const schema = buildSchema(typeDefs);
    const types = Object.values(schema.getTypeMap()).filter(
      type => !type.name.startsWith('__')
    );

    types.forEach(type => {
      expect(type.description).toBeTruthy();
    });
  });
});
```

### Load Testing with Artillery

```yaml
# artillery.yml
config:
  target: 'http://localhost:4000'
  phases:
    - duration: 60
      arrivalRate: 10
      name: Warm up
    - duration: 120
      arrivalRate: 50
      name: Sustained load
scenarios:
  - name: Query posts
    engine: graphql
    flow:
      - post:
          url: /graphql
          json:
            query: |
              query GetPosts {
                posts(first: 10) {
                  edges {
                    node {
                      id
                      title
                      author {
                        username
                      }
                    }
                  }
                }
              }
```

Run with: `artillery run artillery.yml`

### Subscription Testing

```typescript
// tests/subscriptions/post.test.ts
import { WebSocket } from 'ws';
import { createClient } from 'graphql-ws';

describe('Subscriptions', () => {
  it('receives post created events', (done) => {
    const client = createClient({
      url: 'ws://localhost:4000/graphql',
      webSocketImpl: WebSocket,
    });

    const unsubscribe = client.subscribe(
      {
        query: `
          subscription OnPostCreated {
            postCreated {
              id
              title
            }
          }
        `,
      },
      {
        next: (data) => {
          expect(data.data.postCreated).toBeDefined();
          unsubscribe();
          done();
        },
        error: done,
        complete: () => {},
      }
    );

    // Trigger post creation in separate request
    setTimeout(() => {
      createTestPost();
    }, 100);
  });
});
```

### Testing Checklist

- [ ] All resolvers have unit tests (queries, mutations, subscriptions)
- [ ] Integration tests cover full workflows
- [ ] Schema validation passes
- [ ] Authentication/authorization tested
- [ ] Input validation tested with invalid data
- [ ] DataLoader batching verified (N+1 prevention)
- [ ] Error handling tested for all edge cases
- [ ] Subscription delivery tested
- [ ] Load testing performed (>100 req/s)
- [ ] Query complexity limits tested
- [ ] Rate limiting tested
- [ ] Code coverage ≥80%

______________________________________________________________________

## Troubleshooting

### Common Issues

#### Issue: N+1 Query Problem

**Symptoms:**

- Slow query performance
- Multiple database queries for same data
- High database connection count

**Causes:**

- Not using DataLoader for related data
- Field resolvers making individual queries

**Solutions:**

1. **Implement DataLoader**:

```typescript
// WRONG: N+1 problem
Post: {
  author: async (post, _, { prisma }) => {
    return prisma.user.findUnique({ where: { id: post.authorId } });
  }
}

// RIGHT: Using DataLoader
Post: {
  author: async (post, _, { userLoader }) => {
    return userLoader.load(post.authorId);
  }
}
```

2. **Monitor with Apollo Studio**:

- Track resolver execution times
- Identify slow field resolvers
- Use query plans to debug

**Prevention:**

- Always use DataLoader for 1-to-1 and N-to-1 relationships
- Use `include` or `select` in Prisma for nested data
- Monitor query performance in development

______________________________________________________________________

#### Issue: Subscription Not Receiving Events

**Symptoms:**

- Client connected but no events received
- Events published but subscribers don't get them
- WebSocket connection established but silent

**Causes:**

- PubSub topic name mismatch
- Subscription filter not matching
- Context not passed to subscription resolvers

**Solutions:**

1. **Verify topic names match**:

```typescript
// Publisher
pubsub.publish('POST_CREATED', { postCreated: post });

// Subscriber - must match exactly
subscribe: () => pubsub.asyncIterator(['POST_CREATED'])
```

2. **Check subscription filters**:

```typescript
// If using withFilter, ensure it returns true
import { withFilter } from 'graphql-subscriptions';

postCreated: {
  subscribe: withFilter(
    () => pubsub.asyncIterator(['POST_CREATED']),
    (payload, variables) => {
      // Must return true to send event
      return !variables.authorId || payload.postCreated.authorId === variables.authorId;
    }
  ),
}
```

3. **Debug with logging**:

```typescript
pubsub.publish('POST_CREATED', { postCreated: post });
console.log('Published POST_CREATED event:', post.id);
```

______________________________________________________________________

#### Issue: Query Complexity Error

**Symptoms:**

- "Query is too complex" errors
- Legitimate queries rejected
- Inconsistent complexity calculations

**Causes:**

- Complexity limits too low
- Nested connections multiply complexity
- Complex queries without pagination limits

**Solutions:**

1. **Adjust complexity estimators**:

```typescript
const complexity = getComplexity({
  schema,
  query: document,
  variables: request.variables,
  estimators: [
    // Custom estimators for connections
    (args) => {
      if (args.type.name.endsWith('Connection')) {
        return args.args.first || 10;
      }
      return 1;
    },
    simpleEstimator({ defaultComplexity: 1 }),
  ],
});
```

2. **Increase limits for authenticated users**:

```typescript
const maxComplexity = context.user ? 5000 : 1000;
```

3. **Require pagination limits**:

```graphql
type Query {
  # Require first/last argument
  posts(first: Int!): PostConnection!
}
```

______________________________________________________________________

#### Issue: Authentication Failures

**Symptoms:**

- Valid tokens rejected
- "Not authenticated" errors for logged-in users
- Token verification errors

**Causes:**

- JWT secret mismatch
- Expired tokens
- Token not passed correctly
- Context creation fails silently

**Solutions:**

1. **Add debug logging**:

```typescript
export async function context({ req }): Promise<Context> {
  const token = req.headers.authorization?.replace('Bearer ', '');
  console.log('Token received:', token ? 'present' : 'missing');

  if (token) {
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET!);
      console.log('Token decoded:', decoded);
      user = await prisma.user.findUnique({ where: { id: decoded.userId } });
      console.log('User found:', user?.id);
    } catch (error) {
      console.error('Token verification failed:', error.message);
    }
  }
}
```

2. **Check token format**:

```bash
# Verify JWT structure
echo "YOUR_TOKEN" | cut -d'.' -f2 | base64 -d
```

3. **Ensure secret consistency**:

```typescript
// Sign and verify must use same secret
const token = jwt.sign({ userId: 1 }, process.env.JWT_SECRET);
jwt.verify(token, process.env.JWT_SECRET); // Must match
```

______________________________________________________________________

#### Issue: Poor Performance with Large Results

**Symptoms:**

- Slow queries with many results
- High memory usage
- Timeouts on large datasets

**Causes:**

- No pagination implemented
- Fetching too much data at once
- Missing database indexes

**Solutions:**

1. **Enforce pagination**:

```graphql
type Query {
  # Always require pagination
  posts(first: Int!, after: String): PostConnection!
}
```

2. **Add database indexes**:

```prisma
model Post {
  id        Int      @id @default(autoincrement())
  title     String
  authorId  Int
  createdAt DateTime @default(now())

  @@index([authorId])
  @@index([createdAt])
}
```

3. **Use cursor-based pagination**:

```typescript
// More efficient than offset pagination
const posts = await prisma.post.findMany({
  take: first + 1,
  cursor: after ? { id: parseInt(after) } : undefined,
  orderBy: { createdAt: 'desc' },
});
```

______________________________________________________________________

### Debugging Strategies

1. **Enable GraphQL Playground** (development only):

```typescript
const server = new ApolloServer({
  schema,
  plugins: [
    process.env.NODE_ENV === 'development' && ApolloServerPluginLandingPageGraphQLPlayground(),
  ].filter(Boolean),
});
```

2. **Use Apollo Studio for tracing**:

```typescript
const server = new ApolloServer({
  schema,
  plugins: [
    ApolloServerPluginUsageReporting({
      sendVariableValues: { all: true },
    }),
  ],
});
```

3. **Log all operations**:

```typescript
plugins: [
  {
    async requestDidStart({ request }) {
      console.log('Operation:', request.operationName);
      console.log('Query:', request.query);
      console.log('Variables:', request.variables);
    },
  },
],
```

______________________________________________________________________

### Getting Help

**Check Logs:**

- Server logs: `console.log` in resolvers and context
- Database logs: Enable Prisma query logging
- Network logs: Browser DevTools Network tab

**Related Tools:**

- Use `graphql-api-scaffold.md` for initial setup guidance
- Use `debugging-guide.md` for advanced debugging techniques
- Use `observability-incident-lead` agent for optimization help

**Agents to Consult:**

- `graphql-architect` - Schema design issues
- `architecture-council` - Architecture decisions
- `observability-incident-lead` - Performance optimization
- `security-auditor` - Security concerns

**Known Limitations:**

- PubSub in-memory implementation not suitable for multi-instance deployments (use Redis PubSub)
- Subscriptions require WebSocket support (not available on all hosting platforms)
- Query complexity calculation is approximate, not exact
- File uploads require separate configuration (not covered here)

______________________________________________________________________

## Best Practices

1. **Schema Design**: Use interfaces and unions for polymorphism
1. **N+1 Prevention**: Always use DataLoader for related data
1. **Pagination**: Implement cursor-based pagination for large datasets
1. **Error Handling**: Use proper GraphQL error codes and extensions
1. **Security**: Implement field-level authorization
1. **Complexity**: Limit query complexity and depth
1. **Caching**: Use DataLoader caching and response caching
1. **Monitoring**: Track query performance and complexity
1. **Documentation**: Use GraphQL schema descriptions
1. **Testing**: Test resolvers, schema, and subscriptions thoroughly
