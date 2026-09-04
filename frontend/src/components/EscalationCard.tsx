import type { BusinessState } from '../types/businessState'
import { Icon } from './Icon'

export function EscalationCard({ escalation }: { escalation: BusinessState['escalation'] }) {
  if (!escalation.required) return null
  return (
    <section className="stateCard escalationCard" aria-label="Escalade requise">
      <div className="cardTitle">
        <span className="iconBox amber">
          <Icon name="alert" />
        </span>
        <div>
          <h3>Escalade simulée requise</h3>
          <small>Aucune notification réelle</small>
        </div>
      </div>
      <dl>
        <div>
          <dt>Destination</dt>
          <dd>{escalation.type}</dd>
        </div>
        <div>
          <dt>Motif</dt>
          <dd>{escalation.reason}</dd>
        </div>
        <div>
          <dt>Ticket fictif</dt>
          <dd>{escalation.ticket_id ?? 'En cours de création'}</dd>
        </div>
      </dl>
    </section>
  )
}
