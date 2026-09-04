import type { Capabilities, Conversation, Outcome, RealtimeSession } from './types/api'
import type { BusinessState } from './types/businessState'

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function json<T>(response: Response): Promise<T> {
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? 'Service indisponible')
  return data as T
}

function post<T>(url: string, body: unknown): Promise<T> {
  return fetch(url, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }).then((r) =>
    json<T>(r),
  )
}

export const api = {
  capabilities: () => fetch('/api/demo/capabilities').then((r) => json<Capabilities>(r)),
  createConversation: () => post<Conversation>('/api/conversations', { channel: 'web' }),
  conversation: (id: string) => fetch(`/api/conversations/${id}`).then((r) => json<Conversation>(r)),
  businessState: (id: string) =>
    fetch(`/api/conversations/${id}/state`).then((r) =>
      r.status === 404 ? undefined : json<BusinessState>(r),
    ),
  realtimeToken: (conversationId: string) =>
    post<RealtimeSession>('/api/realtime/token', { conversation_id: conversationId }),
  sendMessage: (id: string, text: string) => post<Outcome>(`/api/conversations/${id}/messages`, { text }),
}
