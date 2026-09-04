import { useCallback, useEffect, useRef, useState } from 'react'
import { RoomEvent } from 'livekit-client'
import { api } from '../api'
import { useRealtimeRoom } from '../LiveKitVoice'
import type { BusinessState } from '../types/businessState'

export const isNewerBusinessState = (candidate: BusinessState | undefined, currentVersion: number) =>
  Boolean(candidate && candidate.state_version > currentVersion)

export function useBusinessState(conversationId: string) {
  const { room } = useRealtimeRoom()
  const [state, setState] = useState<BusinessState>()
  const [partialTranscript, setPartialTranscript] = useState('')
  const [socketOpen, setSocketOpen] = useState(false)
  const version = useRef(0)
  const apply = useCallback((candidate?: BusinessState) => {
    if (!candidate || !isNewerBusinessState(candidate, version.current)) return
    version.current = candidate.state_version
    setState(candidate)
  }, [])
  const synchronize = useCallback(async () => {
    if (!conversationId) return
    try { apply(await api.businessState(conversationId)) } catch { /* le polling reprendra */ }
  }, [conversationId, apply])
  useEffect(() => { version.current = 0; setState(undefined); void synchronize() }, [conversationId, synchronize])
  useEffect(() => {
    const onData = (payload: Uint8Array, _participant: unknown, _kind: unknown, topic?: string) => {
      try {
        const parsed = JSON.parse(new TextDecoder().decode(payload))
        if (topic === 'business_state') apply(parsed as BusinessState)
        if (topic === 'transcript_partial') setPartialTranscript(parsed.text ?? '')
      } catch { /* charge utile étrangère ignorée */ }
    }
    const onReconnect = () => void synchronize()
    room.on(RoomEvent.DataReceived, onData)
    room.on(RoomEvent.Reconnected, onReconnect)
    return () => { room.off(RoomEvent.DataReceived, onData); room.off(RoomEvent.Reconnected, onReconnect) }
  }, [room, apply, synchronize])
  useEffect(() => {
    if (!conversationId) return
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${location.host}/ws/conversations/${conversationId}`)
    socket.onopen = () => setSocketOpen(true)
    socket.onclose = () => setSocketOpen(false)
    socket.onerror = () => setSocketOpen(false)
    socket.onmessage = event => { try { const message = JSON.parse(event.data); if (message.topic === 'business_state') apply(message.payload) } catch { /* invalide */ } }
    return () => socket.close()
  }, [conversationId, apply])
  useEffect(() => {
    if (!conversationId || socketOpen) return
    const timer = window.setInterval(() => void synchronize(), 5000)
    return () => window.clearInterval(timer)
  }, [conversationId, socketOpen, synchronize])
  return { state, partialTranscript, socketOpen, synchronize }
}
