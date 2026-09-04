export type BusinessService =
  'adhesion' | 'cotisations' | 'prestations' | 'reclamations' | 'support_it' | 'inconnu'
export type EscalationType = 'none' | 'conseiller' | 'support_it' | 'pool_tpv'
export type ResolutionStatus = 'none' | 'proposed' | 'accepted' | 'refused'
export type RiskFlag =
  | 'paiement_demande'
  | 'hors_perimetre'
  | 'incomprehension_repetee'
  | 'dossier_bloque'
  | 'incident_technique'
  | 'detresse'
  | 'donnee_sensible'

export interface BusinessState {
  conversation_id: string
  state_version: number
  updated_at: string
  language: 'fr'
  service: BusinessService
  intent: { label: string; confidence: number; reformulation: string }
  procedure: { id: string | null; version: string | null; title: string | null }
  step: { index: number; total: number; label: string | null }
  next_question: string | null
  collected: Array<{ field: string; value: string; source: 'caller' | 'agent' | 'system'; at: string }>
  missing: string[]
  resolution: { status: ResolutionStatus; text: string | null }
  escalation: {
    required: boolean
    type: EscalationType
    reason: string | null
    queued_at: string | null
    ticket_id: string | null
  }
  risk_flags: RiskFlag[]
  final_summary: string | null
  is_final: boolean
  rejected_fields?: string[]
  procedure_known?: boolean
}
