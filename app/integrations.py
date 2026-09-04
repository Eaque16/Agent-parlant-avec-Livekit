"""Frontière de sécurité des futures intégrations ASACI."""

from dataclasses import dataclass
from typing import Any

from .config import settings


class IntegrationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BusinessFunction:
    name: str
    reversible: bool
    requires_human_approval: bool
    description: str


AUTHORIZED_FUNCTIONS = {
    "read_case_status": BusinessFunction("read_case_status", True, False, "Lire le statut anonymisé d'un dossier"),
    "create_support_draft": BusinessFunction(
        "create_support_draft", True, True, "Préparer un brouillon de ticket support"
    ),
    "request_human_callback": BusinessFunction(
        "request_human_callback", True, True, "Demander un rappel après confirmation humaine"
    ),
}
FORBIDDEN_FUNCTIONS = {
    "take_payment",
    "refund_payment",
    "delete_case",
    "close_case",
    "change_beneficiary",
    "approve_claim",
}


def invoke(function_name: str, payload: dict[str, Any], *, approved_by: str | None = None) -> dict:
    """Point d'entrée unique ; toute invocation reste simulée dans le POC."""
    if function_name in FORBIDDEN_FUNCTIONS or function_name not in AUTHORIZED_FUNCTIONS:
        raise IntegrationBlocked(f"Fonction métier non autorisée : {function_name}")
    function = AUTHORIZED_FUNCTIONS[function_name]
    if not function.reversible:
        raise IntegrationBlocked("Les actions irréversibles sont interdites")
    if function.requires_human_approval and not approved_by:
        raise IntegrationBlocked("Une autorisation humaine explicite est requise")
    if settings.demo_mode:
        return {"status": "simulated", "function": function_name, "data": _fake_result(function_name)}
    if not settings.integrations_enabled or not settings.integration_base_url or not settings.integration_api_token:
        raise IntegrationBlocked("Les intégrations réelles sont désactivées")
    raise IntegrationBlocked("Connecteur réel non implémenté : validation de sécurité requise")


def _fake_result(function_name: str) -> dict:
    if function_name == "read_case_status":
        return {"case_ref": "DEMO-2026-0042", "status": "En cours d'examen", "identity": "Usager Démo"}
    if function_name == "create_support_draft":
        return {"draft_ref": "IT-DEMO-0017", "submitted": False}
    return {"request_ref": "RAPPEL-DEMO-0008", "submitted": False}
