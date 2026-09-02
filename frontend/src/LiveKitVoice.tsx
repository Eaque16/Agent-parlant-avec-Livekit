import { createContext, useContext, useMemo, useState } from 'react'
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react'
import '@livekit/components-styles'
import { api } from './api'
import type { RealtimeSession } from './types'

type RealtimeContextValue = { connect: (id: string) => Promise<void>; disconnect: () => void; session?: RealtimeSession; connected: boolean }
const RealtimeContext = createContext<RealtimeContextValue | null>(null)

export function useRealtimeRoom() {
  const value = useContext(RealtimeContext)
  if (!value) throw new Error('RealtimeProvider absent')
  return value
}

export function LiveKitVoice({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<RealtimeSession>()
  const [connected, setConnected] = useState(false)
  const value = useMemo(() => ({
    session, connected,
    connect: async (id: string) => setSession(await api.realtimeToken(id)),
    disconnect: () => { setSession(undefined); setConnected(false) },
  }), [session, connected])
  const content = session ? <LiveKitRoom token={session.token} serverUrl={session.server_url} connect audio video={false}
    onConnected={() => setConnected(true)} onDisconnected={() => setConnected(false)} data-lk-theme="default">
    <RoomAudioRenderer />{children}
  </LiveKitRoom> : children
  return <RealtimeContext.Provider value={value}>{content}</RealtimeContext.Provider>
}
