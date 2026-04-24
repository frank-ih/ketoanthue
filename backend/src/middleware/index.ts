import type { Context, Next } from 'hono';

// Simple in-memory rate limiter (use Redis in production)
const ipRequests = new Map<string, number[]>();

interface RateLimitOptions {
  maxRequests?: number;
  windowMs?: number;
}

export function rateLimiter(options: RateLimitOptions = {}) {
  const maxRequests = options.maxRequests ?? 30;
  const windowMs = options.windowMs ?? 60000;

  return async (c: Context, next: Next) => {
    const ip = c.req.header('x-forwarded-for')?.split(',')[0]?.trim()
      || c.req.header('x-real-ip')
      || 'unknown';
    const now = Date.now();

    const requests = ipRequests.get(ip) || [];
    const recent = requests.filter(t => now - t < windowMs);

    if (recent.length >= maxRequests) {
      return c.json({ error: 'Rate limit exceeded. Please try again later.' }, { status: 429 });
    }

    recent.push(now);
    ipRequests.set(ip, recent);
    await next();
  };
}

export async function traceRequest(c: Context, next: Next) {
  const requestId = crypto.randomUUID();
  c.set('requestId', requestId);

  const start = Date.now();

  await next();

  const duration = Date.now() - start;
  const status = c.res.status;

  console.log(JSON.stringify({
    requestId,
    method: c.req.method,
    path: c.req.path,
    status,
    duration: `${duration}ms`,
    timestamp: new Date().toISOString(),
  }));
}

export function errorHandler(err: Error, c: Context) {
  console.error('Error:', {
    message: err.message,
    path: c.req.path,
    requestId: c.get('requestId'),
  });

  return c.json(
    {
      error: 'Internal server error',
      requestId: c.get('requestId'),
    },
    { status: 500 }
  );
}