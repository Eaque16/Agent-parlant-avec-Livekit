import { createContext, useContext, useMemo, useState } from 'react'
import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react'
import '@livekit/components-styles'
import { Room } from 'livekit-client'
import { api } from './api'
import type { RealtimeSession } from './types/api'

type RealtimeContextValue = {
  connect: (id: string) => Promise<void>
  disconnect: () => void
  sendText: (text: string) => Promise<void>
  session?: RealtimeSession
  connected: boolean
  room: Room
}
const RealtimeContext = createContext<RealtimeContextValue | null>(null)

export function useRealtimeRoom() {
  const value = useContext(RealtimeContext)
  if (!value) throw new Error('RealtimeProvider absent')
  return value
}

export function LiveKitVoice({ children }: { children: React.ReactNode }) {
  const [room] = useState(() => new Room())
  const [session, setSession] = useState<RealtimeSession>()
  const [connected, setConnected] = useState(false)
  const value = useMemo(
    () => ({
      session,
      connected,
      room,
      connect: async (id: string) => setSession(await api.realtimeToken(id)),
      disconnect: () => {
        void room.disconnect()
        setSession(undefined)
        setConnected(false)
      },
      sendText: async (text: string) => {
        if (!connected) throw new Error('Démarrez l’appel avant d’envoyer un message.')
        await room.localParticipant.publishData(
          new TextEncoder().encode(JSON.stringify({ text })),
          { reliable: true, topic: 'chat_message' },
        )
      },
    }),
    [session, connected, room],
  )
  const content = session ? (
    <LiveKitRoom
      room={room}
      token={session.token}
      serverUrl={session.server_url}
      connect
      audio
      video={false}
      onConnected={() => setConnected(true)}
      onDisconnected={() => setConnected(false)}
      data-lk-theme="default"
    >
      <RoomAudioRenderer />
      {children}
    </LiveKitRoom>
  ) : (
    children
  )
  return <RealtimeContext.Provider value={value}>{content}</RealtimeContext.Provider>
}
