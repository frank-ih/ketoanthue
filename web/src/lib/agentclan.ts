// Backend API client for Ketoanthue chat
// All AI calls proxied through backend to keep secrets server-side

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatResponse {
  answer: string;
  citations?: Array<{
    source: string;
    reference: string;
  }>;
  confidence?: number;
}

export async function sendChatMessage(
  message: string,
  tenantId: string = 'ketoanthue',
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      tenantId,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
