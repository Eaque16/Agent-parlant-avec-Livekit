import type { Capabilities, Conversation, Outcome, Procedure, RealtimeSession } from './types'

async function json<T>(response: Response): Promise<T> {
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? 'Service indisponible')
  return data as T
}
export const api = {
  health: () => fetch('/health').then(r => json<{status:string; mode:string; demo_mode:boolean}>(r)),
  procedures: () => fetch('/api/procedures').then(r => json<Procedure[]>(r)),
  capabilities: () => fetch('/api/demo/capabilities').then(r => json<Capabilities>(r)),
  createConversation: () => fetch('/api/conversations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({channel:'web'}) }).then(r => json<Conversation>(r)),
  conversation: (id:string) => fetch(`/api/conversations/${id}`).then(r => json<Conversation>(r)),
  realtimeToken: (conversationId:string) => fetch('/api/realtime/token', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({conversation_id:conversationId}) }).then(r => json<RealtimeSession>(r)),
  sendMessage: (id:string, text:string) => fetch(`/api/conversations/${id}/messages`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) }).then(r => json<Outcome>(r)),
  sendAudio: (id:string, blob:Blob) => { const body=new FormData(); body.append('audio',blob,'appel.webm'); return fetch(`/api/conversations/${id}/audio`,{method:'POST',body}).then(r=>json<Outcome & {audio_base64?:string}>(r)) },
}
