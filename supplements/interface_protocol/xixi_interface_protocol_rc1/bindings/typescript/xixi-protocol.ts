export const XIXI_PROTOCOL = "xixi/1.0" as const;

export type Actor = "ui" | "container" | "soul" | "body" | "tool" | "model" | "system";
export type Risk = "ordinary" | "scoped" | "outbound_private" | "irreversible";
export type UiMode = "quiet" | "chat" | "work" | "permission";
export type SoulReplyMode = "companion" | "answer" | "advice" | "execution" | "correction" | "quiet";

export interface Envelope<TType extends string, TPayload> {
  protocol: typeof XIXI_PROTOCOL;
  id: string;
  type: TType;
  timestamp: string;
  session_id: string;
  trace_id: string;
  reply_to: string | null;
  source: Actor;
  target: Actor;
  sequence: number;
  ack_required: boolean;
  replay_safe: boolean;
  payload: TPayload;
}

export interface UserInputPayload {
  turn_id: string;
  content: string;
  input_mode: "text" | "voice_transcript" | "system_action";
  attachments: Array<{
    attachment_id: string;
    kind: "image" | "audio" | "document" | "file" | "folder_ref";
    display_name: string;
    local_uri: string;
    mime_type: string | null;
    sha256: string | null;
  }>;
  client_context: {
    active_panel: string | null;
    foreground_app: string | null;
    quiet_mode: boolean;
  };
}

export interface PermissionRequestPayload {
  turn_id: string;
  permission_id: string;
  operation: string;
  target: string | null;
  scope: Record<string, unknown>;
  risk: "outbound_private" | "irreversible";
  reason: string;
  options: Array<"allow_once" | "allow_scope" | "deny">;
  expires_at: string | null;
}

export interface BodyIntentPayload {
  turn_id: string | null;
  state: "sleeping" | "alone" | "working" | "thinking" | "waiting" | "accompanying" | "communicating" | "executing";
  intent: {
    posture: string | null;
    motion: string | null;
    expression: string | null;
    camera: string | null;
    ui: string | null;
    intensity: number;
  };
  transition: {
    duration_ms: number;
    interruptible: boolean;
  };
}

export function assertBaseEnvelope(value: unknown): asserts value is Envelope<string, unknown> {
  if (!value || typeof value !== "object") throw new Error("Message must be an object");
  const m = value as Record<string, unknown>;
  if (m.protocol !== XIXI_PROTOCOL) throw new Error("Unsupported protocol");
  for (const key of ["id", "type", "timestamp", "session_id", "trace_id", "source", "target"]) {
    if (typeof m[key] !== "string") throw new Error(`Missing or invalid ${key}`);
  }
  if (!Number.isInteger(m.sequence)) throw new Error("Invalid sequence");
  if (!m.payload || typeof m.payload !== "object") throw new Error("Invalid payload");
}
