"""Adaptateur IA : moteur déterministe de démonstration, ou OpenAI lorsqu'une clé est configurée."""

import json
import re
from io import BytesIO

from ..config import settings
from ..prompt import SYSTEM_PROMPT

ESCALATIONS = {"none", "human", "it"}

PAYMENT_WORDS = ("payer maintenant", "carte bancaire", "prélèvement", "effectuer le paiement", "rembourser l'argent")
IT_WORDS = ("connexion", "connecter", "mot de passe", "portail", "bug", "erreur technique")
COMPLAINT_WORDS = ("réclamation", "bloqué", "plainte", "fraude", "mécontent")

# (mots-clés, intention, service, procédure, question de qualification)
GUIDANCE = (
    (
        ("adhésion", "adhérer", "immatriculation"),
        "adhesion",
        "Adhésion",
        "Qualification d'une adhésion",
        "La demande concerne-t-elle une nouvelle immatriculation ou la mise à jour d'un dossier ?",
    ),
    (
        ("cotisation", "paiement", "payer"),
        "cotisation",
        "Cotisations",
        "Vérification d'une cotisation",
        "Quelle est la période concernée par la cotisation ?",
    ),
    (
        ("prestation", "remboursement", "remboursé"),
        "prestation",
        "Prestations",
        "Suivi d'une prestation",
        "Quelle est la nature de la prestation et son statut actuel ?",
    ),
)

GENERIC_REPLY = (
    "Si je comprends bien, vous souhaitez être orienté dans une démarche ASACI. "
    "Pouvez-vous préciser s'il s'agit d'une adhésion, d'une cotisation, d'une prestation ou d'une réclamation ?"
)


def _outcome(
    reply: str,
    *,
    intent: str,
    service: str,
    procedure: str,
    next_question: str = "",
    resolution: str = "",
    escalation: str = "none",
    reason: str = "",
) -> dict:
    return {
        "reply": reply,
        "intent": intent,
        "service": service,
        "procedure": procedure,
        "next_question": next_question,
        "resolution": resolution,
        "escalation": escalation,
        "reason": reason,
    }


def _mock_answer(text: str) -> dict:
    value = text.lower()
    if any(word in value for word in PAYMENT_WORDS):
        question = "Souhaitez-vous que je vous indique la marche à suivre ?"
        return _outcome(
            "Je ne traite aucun paiement réel et je ne peux pas recevoir de donnée bancaire. "
            f"Je peux vous expliquer la procédure ou vous orienter vers un conseiller. {question}",
            intent="cotisation",
            service="Cotisations",
            procedure="Information sans transaction",
            next_question=question,
            resolution="Transaction refusée par le mode démonstration",
            reason="Paiement réel interdit",
        )
    if any(word in value for word in IT_WORDS):
        return _outcome(
            "Je comprends que vous rencontrez un problème technique. Je prépare votre orientation vers le support "
            "informatique avec le résumé de notre échange. Cette demande n'est pas transmise dans cet environnement "
            "de démonstration.",
            intent="it_support",
            service="Support IT",
            procedure="Diagnostic et transfert IT",
            resolution="Ticket IT fictif, non transmis",
            escalation="it",
            reason="Incident technique détecté",
        )
    if any(word in value for word in COMPLAINT_WORDS):
        return _outcome(
            "Je comprends votre préoccupation. Ce cas nécessite un examen personnalisé. "
            "Je vais l'orienter vers un conseiller humain.",
            intent="reclamation",
            service="Réclamations",
            procedure="Qualification d'une réclamation",
            resolution="Rappel par un conseiller simulé",
            escalation="human",
            reason="Examen humain requis",
        )
    for words, intent, service, procedure, question in GUIDANCE:
        if any(word in value for word in words):
            return _outcome(question, intent=intent, service=service, procedure=procedure, next_question=question)
    return _outcome(
        GENERIC_REPLY,
        intent="general",
        service="Accueil",
        procedure="Qualification initiale",
        next_question=GENERIC_REPLY,
    )


def _extract_json(value: str) -> dict:
    match = re.search(r"\{.*\}", value, re.DOTALL)
    if not match:
        raise ValueError("Réponse structurée absente")
    result = json.loads(match.group(0))
    if result.get("escalation") not in ESCALATIONS:
        raise ValueError("Escalade invalide")
    return result


def _openai_client():
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key)


def answer(messages: list[dict], text: str) -> dict:
    if not settings.openai_api_key:
        return _mock_answer(text)
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-10:])
    response = _openai_client().responses.create(
        model=settings.chat_model,
        instructions=SYSTEM_PROMPT,
        input=f"Historique :\n{history}\n\nDernier message de l'appelant : {text}",
    )
    result = _extract_json(response.output_text)
    result.setdefault("service", "Accueil")
    result.setdefault("procedure", "Qualification initiale")
    result.setdefault("next_question", "")
    result.setdefault("resolution", "")
    return result


def transcribe(data: bytes, filename: str, content_type: str | None) -> str:
    if not settings.openai_api_key:
        raise RuntimeError(
            "La transcription audio nécessite OPENAI_API_KEY. Le chat texte reste disponible en mode démo."
        )
    stream = BytesIO(data)
    stream.name = filename or "audio.webm"
    return (
        _openai_client().audio.transcriptions.create(model=settings.transcribe_model, file=stream, language="fr").text
    )


def synthesize(text: str) -> bytes:
    if not settings.openai_api_key:
        return b""
    return (
        _openai_client()
        .audio.speech.create(
            model=settings.tts_model,
            voice=settings.tts_voice,
            input=text,
            instructions="Parle en français, chaleureusement, clairement et à un rythme de service client.",
        )
        .content
    )
