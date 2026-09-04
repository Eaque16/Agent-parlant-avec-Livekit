import type { BusinessState } from '../types/businessState'

export function EscalationCard({ escalation }: { escalation: BusinessState['escalation'] }) {
  if (!escalation.required) return null
  return <section className="stateCard escalationCard" aria-label="Escalade requise"><h3>Escalade simulée requise</h3><p><b>Destination :</b> {escalation.type}</p><p><b>Motif :</b> {escalation.reason}</p><p><b>Ticket fictif :</b> {escalation.ticket_id ?? 'En cours de création'}</p><small>Aucune notification réelle n’est envoyée.</small></section>
}
