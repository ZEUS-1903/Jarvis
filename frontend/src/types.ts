// Mirrors backend/app/schemas/chat.py. If one changes, change the other.
export interface ToolTrace {
  name: string;
  arguments: string; // raw JSON string the model produced
  ok: boolean;
  error: string | null;
  duration_ms: number;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
  tool_calls: ToolTrace[];
  usage: { input_tokens: number; output_tokens: number; llm_calls: number };
  request_id: string | null;
}

export type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; tools: ToolTrace[]; requestId: string | null };
