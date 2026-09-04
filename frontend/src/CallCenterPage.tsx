import { FormEvent, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { Message, Outcome } from './types'
import { useRealtimeRoom } from './LiveKitVoice'
import { useBusinessState } from './hooks/useBusinessState'
import { BusinessStatePanel } from './components/BusinessStatePanel'

type SpeechRecognitionLike = {lang:string;continuous:boolean;interimResults:boolean;start():void;stop():void;onresult:((e:any)=>void)|null;onend:(()=>void)|null;onerror:((e:any)=>void)|null}

export function CallCenterPage(){
 const [id,setId]=useState(''),[messages,setMessages]=useState<Message[]>([{role:'assistant',content:'Bonjour, je suis Awa. Décrivez-moi votre préoccupation fictive.'}]),[live,setLive]=useState('Appuyez sur « Démarrer l’appel » puis parlez.'),[active,setActive]=useState(false),[,setOutcome]=useState<Outcome>(),[text,setText]=useState('')
 const recognition=useRef<SpeechRecognitionLike|null>(null), realtime=useRealtimeRoom(), business=useBusinessState(id)
 useQuery({queryKey:['procedures'],queryFn:api.procedures})
 const {data:storedConversation}=useQuery({queryKey:['conversation',id],queryFn:()=>api.conversation(id),enabled:!!id,refetchInterval:active?5000:false})
 useEffect(()=>{api.createConversation().then(c=>setId(c.id))},[])
 useEffect(()=>{if(active&&storedConversation?.messages.length)setMessages(storedConversation.messages)},[active,storedConversation])
 const send=useMutation({mutationFn:(value:string)=>api.sendMessage(id,value),onMutate:value=>setMessages(m=>[...m,{role:'user',content:value}]),onSuccess:data=>{setMessages(m=>[...m,{role:'assistant',content:data.reply}]);setOutcome(data);const speech=new SpeechSynthesisUtterance(data.reply);speech.lang='fr-FR';window.speechSynthesis.cancel();window.speechSynthesis.speak(speech)}})
 const submit=(e:FormEvent)=>{e.preventDefault();if(text.trim()&&id){send.mutate(text.trim());setLive(text.trim());setText('')}}
 const toggle=async()=>{if(active){recognition.current?.stop();realtime.disconnect();setActive(false);return}try{await realtime.connect(id)}catch(e){setLive(e instanceof Error?e.message:'LiveKit Cloud indisponible');return}const Ctor=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;if(!Ctor){setLive('Room LiveKit ouverte. Transcription directe indisponible dans ce navigateur.');setActive(true);return}const r:SpeechRecognitionLike=new Ctor();r.lang='fr-FR';r.continuous=true;r.interimResults=true;r.onresult=(event:any)=>{let interim='',final='';for(let i=event.resultIndex;i<event.results.length;i++){if(event.results[i].isFinal)final+=event.results[i][0].transcript;else interim+=event.results[i][0].transcript}setLive(interim||final||'Je vous écoute…')};r.onend=()=>setActive(false);r.onerror=e=>setLive(`Microphone : ${e.error}`);recognition.current=r;r.start();setActive(true);setLive('Connexion à la room LiveKit…')}
 return <main className="workspace"><section className="call"><div className="warning">DÉMONSTRATION SÉCURISÉE · Aucun dossier réel · Aucun paiement · Aucune action irréversible</div><div className="callTitle"><div><small>APPEL FICTIF EN COURS</small><h1>Conversation client</h1><p>Usager Démo · Session navigateur</p></div><span>● Simulation</span></div><div className={`live ${active?'active':''}`}><div className="wave">|||||</div><div><small>TRANSCRIPTION EN DIRECT</small><p>{business.partialTranscript||live}</p></div></div><div className="messages">{messages.map((m,i)=><article className={m.role} key={i}><b>{m.role==='user'?'CL':'AW'}</b><p>{m.content}</p></article>)}{business.partialTranscript&&<article className="partial"><b>CL</b><p><i>{business.partialTranscript}</i></p></article>}</div><form onSubmit={submit}><input value={text} onChange={e=>setText(e.target.value)} placeholder="Écrire une préoccupation fictive…"/><button disabled={!id||send.isPending}>Envoyer</button></form><div className="controls"><button onClick={toggle} className={active?'stop':''}>{active?'■ Mettre en pause':'● Démarrer l’appel'}</button><span>{active?'Écoute active':'Microphone inactif'} · État : {business.socketOpen?'temps réel':'synchronisation 5 s'}</span></div></section><aside><BusinessStatePanel state={business.state}/></aside></main>
}
