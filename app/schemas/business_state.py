from datetime import UTC, datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Service(str, Enum):
    ADHESION = "adhesion"
    COTISATIONS = "cotisations"
    PRESTATIONS = "prestations"
    RECLAMATIONS = "reclamations"
    SUPPORT_IT = "support_it"
    INCONNU = "inconnu"


class EscalationType(str, Enum):
    NONE = "none"
    CONSEILLER = "conseiller"
    SUPPORT_IT = "support_it"
    POOL_TPV = "pool_tpv"


class ResolutionStatus(str, Enum):
    NONE = "none"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REFUSED = "refused"


class RiskFlag(str, Enum):
    PAIEMENT_DEMANDE = "paiement_demande"
    HORS_PERIMETRE = "hors_perimetre"
    INCOMPREHENSION_REPETEE = "incomprehension_repetee"
    DOSSIER_BLOQUE = "dossier_bloque"
    INCIDENT_TECHNIQUE = "incident_technique"
    DETRESSE = "detresse"
    DONNEE_SENSIBLE = "donnee_sensible"


class Intent(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    confidence: float = Field(ge=0, le=1)
    reformulation: str = Field(min_length=1, max_length=1000)


class Procedure(StrictModel):
    id: str | None = Field(default=None, max_length=120)
    version: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=300)


class Step(StrictModel):
    index: int = Field(ge=0)
    total: int = Field(ge=0)
    label: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def valid_progress(self):
        if self.index > self.total:
            raise ValueError("step.index doit être inférieur ou égal à step.total")
        return self


class CollectedField(StrictModel):
    field: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    source: Literal["caller", "agent", "system"] = "caller"
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Resolution(StrictModel):
    status: ResolutionStatus = ResolutionStatus.NONE
    text: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def active_resolution_has_text(self):
        if self.status != ResolutionStatus.NONE and not (self.text and self.text.strip()):
            raise ValueError("une résolution active doit contenir un texte")
        return self


class Escalation(StrictModel):
    required: bool = False
    type: EscalationType = EscalationType.NONE
    reason: str | None = Field(default=None, max_length=2000)
    queued_at: datetime | None = None
    ticket_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def valid_escalation(self):
        if self.required and (self.type == EscalationType.NONE or not (self.reason and self.reason.strip())):
            raise ValueError("une escalade requise exige un type et un motif")
        if not self.required and self.type != EscalationType.NONE:
            raise ValueError("une escalade non requise doit avoir le type none")
        return self


class BusinessState(StrictModel):
    conversation_id: UUID
    state_version: int = Field(ge=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    language: Literal["fr"] = "fr"
    service: Service = Service.INCONNU
    intent: Intent
    procedure: Procedure = Field(default_factory=Procedure)
    step: Step = Field(default_factory=lambda: Step(index=0, total=0))
    next_question: str | None = Field(default=None, max_length=2000)
    collected: list[CollectedField] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    resolution: Resolution = Field(default_factory=Resolution)
    escalation: Escalation = Field(default_factory=Escalation)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    final_summary: str | None = Field(default=None, max_length=8000)
    is_final: bool = False

    @model_validator(mode="after")
    def final_state_has_summary(self):
        if self.is_final and not (self.final_summary and self.final_summary.strip()):
            raise ValueError("un état final exige un résumé")
        return self


class BusinessStateOut(BusinessState):
    rejected_fields: list[str] = Field(default_factory=list)
    procedure_known: bool = True
