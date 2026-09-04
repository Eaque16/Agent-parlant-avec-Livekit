import { FormEvent, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { Message } from './types/api'
import { useRealtimeRoom } from './LiveKitVoice'
import { useBusinessState } from './hooks/useBusinessState'
import { BusinessStatePanel } from './components/BusinessStatePanel'
import { Icon } from './components/Icon'

export function CallCenterPage() {
  const [id, setId] = useState(''),
    [messages, setMessages] = useState<Message[]>([
      {
        role: 'assistant',
        content: 'Bonjour, je suis Awa, l’assistante virtuelle ASACI. Comment puis-je vous aider ?',
      },
    ]),
    [live, setLive] = useState('Prête à vous écouter.'),
    [active, setActive] = useState(false),
    [text, setText] = useState('')
  const realtime = useRealtimeRoom(),
    business = useBusinessState(id)
  const { data: storedConversation } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => api.conversation(id),
    enabled: !!id,
    refetchInterval: active ? 1000 : false,
  })
  useEffect(() => {
    api.createConversation().then((c) => setId(c.id))
  }, [])
  useEffect(() => {
    if (active && storedConversation?.messages.length) setMessages(storedConversation.messages)
  }, [active, storedConversation])
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const value = text.trim()
    if (!value || !id) return
    try {
      await realtime.sendText(value)
      setMessages((current) => [...current, { role: 'user', content: value }])
      setLive('Message transmis à Awa.')
      setText('')
    } catch (error) {
      setLive(error instanceof Error ? error.message : 'Message non transmis.')
    }
  }
  const toggle = async () => {
    if (active) {
      realtime.disconnect()
      setActive(false)
      setLive('Appel mis en pause.')
      return
    }
    try {
      await realtime.connect(id)
    } catch (e) {
      setLive(e instanceof Error ? e.message : 'LiveKit Cloud indisponible')
      return
    }
    setActive(true)
    setLive('Connexion sécurisée en cours…')
  }
  return (
    <main className="consolePage">
      <div className="demoNotice">
        <Icon name="shield" size={16} />
        <span>
          <b>Démonstration sécurisée</b> — Données fictives uniquement. Aucun paiement ni action réelle.
        </span>
      </div>
      <header className="pageHeader">
        <div>
          <span className="eyebrow">CONVERSATION EN COURS</span>
          <h1>Console d’appel</h1>
          <p>Échange vocal assisté et qualification métier en temps réel</p>
        </div>
        <div className={`callStatus ${active ? 'isActive' : ''}`}>
          <i />
          {active ? 'Appel actif' : 'Prêt à démarrer'}
        </div>
      </header>
      <div className="consoleGrid">
        <section className="conversationCard">
          <header className="conversationTop">
            <div className="callerAvatar">UD</div>
            <div>
              <b>Usager démonstration</b>
              <span>Session navigateur · ID {id ? id.slice(0, 8) : 'en création'}</span>
            </div>
            <div className="connectionState">
              <span className={business.socketOpen ? 'connected' : ''} />
              {business.socketOpen ? 'Temps réel' : 'Synchronisation'}
            </div>
          </header>
          <div className={`voiceStage ${active ? 'listening' : ''}`}>
            <div className="voiceOrb">
              <Icon name="mic" size={24} />
              <span />
              <span />
              <span />
            </div>
            <div>
              <small>{active ? 'ÉCOUTE ACTIVE' : 'ASSISTANTE DISPONIBLE'}</small>
              <p>{business.partialTranscript || live}</p>
            </div>
            <div className="equalizer" aria-hidden="true">
              {[1, 2, 3, 4, 5].map((n) => (
                <i key={n} />
              ))}
            </div>
          </div>
          <div className="transcriptHeader">
            <div>
              <Icon name="file" size={17} />
              <b>Transcription</b>
            </div>
            <span>{messages.length} messages</span>
          </div>
          <div className="messages" aria-live="polite">
            {messages.map((m, i) => (
              <article className={m.role} key={i}>
                <div className="messageAvatar">{m.role === 'user' ? 'CL' : 'AW'}</div>
                <div>
                  <span>{m.role === 'user' ? 'Appelant' : 'Awa · Assistante IA'}</span>
                  <p>{m.content}</p>
                </div>
              </article>
            ))}
            {business.partialTranscript && (
              <article className="user partial">
                <div className="messageAvatar">CL</div>
                <div>
                  <span>Appelant · transcription en cours</span>
                  <p>
                    <i>{business.partialTranscript}</i>
                  </p>
                </div>
              </article>
            )}
          </div>
          <form className="messageComposer" onSubmit={submit}>
            <input
              aria-label="Message"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={realtime.connected ? 'Écrire à Awa dans cette conversation…' : 'Démarrez l’appel pour écrire à Awa…'}
            />
            <button disabled={!id || !realtime.connected} aria-label="Envoyer">
              Envoyer <span>→</span>
            </button>
          </form>
          <footer className="callControls">
            <div>
              <span className={`microphoneState ${active ? 'on' : ''}`}>
                <Icon name="mic" size={17} />
              </span>
              <p>
                <b>{active ? 'Microphone activé' : 'Microphone désactivé'}</b>
                <small>{active ? 'Awa vous écoute' : 'Cliquez pour commencer'}</small>
              </p>
            </div>
            <button onClick={toggle} className={active ? 'stopButton' : 'startButton'}>
              <Icon name={active ? 'pause' : 'phone'} size={18} />
              {active ? 'Mettre en pause' : 'Démarrer l’appel'}
            </button>
          </footer>
        </section>
        <aside className="insightColumn">
          <div className="insightTitle">
            <div>
              <span className="eyebrow">ASSISTANCE MÉTIER</span>
              <h2>Suivi intelligent</h2>
            </div>
            <span className="aiBadge">IA</span>
          </div>
          <BusinessStatePanel state={business.state} />
        </aside>
      </div>
    </main>
  )
}
