import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BusinessStatePanel } from './BusinessStatePanel'
import type { BusinessState } from '../types/businessState'

const state: BusinessState = {conversation_id:'00000000-0000-4000-8000-000000000001',state_version:2,updated_at:'2026-09-03T12:00:00Z',language:'fr',service:'adhesion',intent:{label:'adhesion',confidence:.9,reformulation:'Vous souhaitez effectuer une adhésion fictive.'},procedure:{id:'adhesion-qualification',version:'1.0',title:'Qualification adhésion'},step:{index:1,total:3,label:'Identifier'},next_question:'Est-ce une nouvelle adhésion ?',collected:[],missing:['type_demande'],resolution:{status:'none',text:null},escalation:{required:false,type:'none',reason:null,queued_at:null,ticket_id:null},risk_flags:[],final_summary:null,is_final:false}

describe('BusinessStatePanel',()=>{it('affiche la qualification structurée avec un libellé de confiance',()=>{render(<BusinessStatePanel state={state}/>);expect(screen.getByText('adhesion')).toBeInTheDocument();expect(screen.getByText('Confiance : 90 %')).toBeInTheDocument();expect(screen.getByText('Étape 1/3 — Identifier')).toBeInTheDocument()})})
