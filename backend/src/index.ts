import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { traceRequest, errorHandler, rateLimiter } from './middleware/index.js';
import { healthRouter } from './routes/health.js';
import { chatRouter } from './routes/chat.js';

// Validate required env vars at startup
if (!process.env.AGENTCLAN_API_KEY) {
  console.error('FATAL: AGENTCLAN_API_KEY is required');
  process.exit(1);
}

const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000')
  .split(',')
  .map(s => s.trim());

const app = new Hono();

// Middleware
app.use('*', logger());
app.use('*', cors({
  origin: (origin) => {
    if (!origin || ALLOWED_ORIGINS.includes(origin)) return origin;
    return null;
  },
  credentials: true,
}));
app.use('*', rateLimiter({ maxRequests: 30, windowMs: 60000 }));
app.use('*', traceRequest);

// Routes
app.route('/health', healthRouter);
app.route('/api/chat', chatRouter);

// Error handler
app.onError(errorHandler);

const port = parseInt(process.env.PORT || '3001', 10);

console.log(`Ketoanthue API running on port ${port}`);

serve({
  fetch: app.fetch,
  port,
});

export default app;