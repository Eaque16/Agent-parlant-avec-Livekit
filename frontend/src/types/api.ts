export type Message = { role: 'user' | 'assistant'; content: string; created_at?: string }

export type CallSession = {
  id: number
  room_name: string
  provider: string
  voice: string
  status: 'active' | 'ended'
  started_at: string
  ended_at?: string
  duration_seconds?: number
  end_reason?: string
}

export type Conversation = { id: string; messages: Message[]; calls: CallSession[]; status: string }

export type Outcome = {
  transcript: string
  reply: string
  intent: string
  service: string
  procedure: string
  next_question: string
  resolution: string
  escalation: 'none' | 'human' | 'it'
  reason: string
}

export type Capabilities = {
  data_policy: string
  real_asaci_connections: false
  real_payments: false
  irreversible_actions: false
  authorized_future_functions: {
    name: string
    description: string
    reversible: boolean
    requires_human_approval: boolean
  }[]
  forbidden_functions: string[]
}

export type RealtimeSession = {
  server_url: string
  token: string
  room_name: string
  identity: string
  expires_in: number
}
