import { Hono } from 'hono';
import { z } from 'zod';

const chatSchema = z.object({
  message: z.string().min(1).max(2000),
  tenantId: z.string().optional().default('ketoanthue'),
});

const agentclanResponseSchema = z.object({
  answer: z.string().optional(),
  message: z.string().optional(),
  citations: z.array(z.record(z.unknown())).optional(),
  confidence: z.number().optional(),
});

// Basic prompt injection sanitization
function sanitizeInput(text: string): string {
  return text
    .replace(/ignore\s+(all\s+)?previous\s+instructions/gi, '[REMOVED]')
    .replace(/system\s*:/gi, '[REMOVED]')
    .replace(/you\s+are\s+now/gi, '[REMOVED]')
    .replace(/<\s*script\s*>/gi, '[REMOVED]');
}

export const chatRouter = new Hono();

chatRouter.post('/', async (c) => {
  const body = await c.req.json();
  const parsed = chatSchema.safeParse(body);

  if (!parsed.success) {
    return c.json({ error: 'Invalid request' }, { status: 400 });
  }

  const { message, tenantId } = parsed.data;
  const sanitizedMessage = sanitizeInput(message);

  const agentclanApi = process.env.AGENTCLAN_API_URL || 'http://localhost:8080';
  const agentclanKey = process.env.AGENTCLAN_API_KEY!;

  try {
    const response = await fetch(`${agentclanApi}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${agentclanKey}`,
      },
      body: JSON.stringify({
        message: sanitizedMessage,
        agent: 'ketoanthue',
        tenant_id: tenantId,
      }),
    });

    if (!response.ok) {
      throw new Error(`AgentClan API error: ${response.status}`);
    }

    const raw = await response.json();
    const validated = agentclanResponseSchema.safeParse(raw);

    if (!validated.success) {
      console.error('Invalid AgentClan response:', validated.error);
      return c.json({
        answer: 'Xin lỗi, tôi chưa thể trả lờii.',
        citations: [],
        confidence: 0,
      });
    }

    const data = validated.data;

    return c.json({
      answer: data.answer || data.message || 'Xin lỗi, tôi chưa thể trả lờii.',
      citations: data.citations || [],
      confidence: data.confidence || 0.8,
    });
  } catch (error) {
    console.error('Chat error:', error);
    return c.json({
      answer: 'Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau.',
      citations: [],
      confidence: 0,
    });
  }
});
