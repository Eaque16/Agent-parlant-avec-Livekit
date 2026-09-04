import { FormEvent, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { Message } from './types/api'
import { useRealtimeRoom } from './LiveKitVoice'
import { useBusinessState } from './hooks/useBusinessState'
import { BusinessStatePanel } from './components/BusinessStatePanel'
import { Icon } from './components/Icon'

type SpeechRecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  start(): void
  stop(): void
  onresult: ((e: any) => void) | null
  onend: (() => void) | null
  onerror: ((e: any) => void) | null
}

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
  const recognition = useRef<SpeechRecognitionLike | null>(null),
    realtime = useRealtimeRoom(),
    business = useBusinessState(id)
  const { data: storedConversation } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => api.conversation(id),
    enabled: !!id,
    refetchInterval: active ? 5000 : false,
  })
  useEffect(() => {
    api.createConversation().then((c) => setId(c.id))
  }, [])
  useEffect(() => {
    if (active && storedConversation?.messages.length) setMessages(storedConversation.messages)
  }, [active, storedConversation])
  const send = useMutation({
    mutationFn: (value: string) => api.sendMessage(id, value),
    onMutate: (value) => setMessages((m) => [...m, { role: 'user', content: value }]),
    onSuccess: (data) => {
      setMessages((m) => [...m, { role: 'assistant', content: data.reply }])
      const speech = new SpeechSynthesisUtterance(data.reply)
      speech.lang = 'fr-FR'
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(speech)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim() && id) {
      send.mutate(text.trim())
      setLive(text.trim())
      setText('')
    }
  }
  const toggle = async () => {
    if (active) {
      recognition.current?.stop()
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
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!Ctor) {
      setLive('Room LiveKit ouverte. Je vous écoute…')
      setActive(true)
      return
    }
    const r: SpeechRecognitionLike = new Ctor()
    r.lang = 'fr-FR'
    r.continuous = true
    r.interimResults = true
    r.onresult = (event: any) => {
      let interim = '',
        final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript
        else interim += event.results[i][0].transcript
      }
      setLive(interim || final || 'Je vous écoute…')
    }
    r.onend = () => setActive(false)
    r.onerror = (e) => setLive(`Microphone : ${e.error}`)
    recognition.current = r
    r.start()
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
              placeholder="Écrire un message de démonstration…"
            />
            <button disabled={!id || send.isPending} aria-label="Envoyer">
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
