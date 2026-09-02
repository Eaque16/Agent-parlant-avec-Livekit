import json
import re
from io import BytesIO

from .config import settings
from .prompt import SYSTEM_PROMPT


def _mock_answer(text: str) -> dict:
    value = text.lower()
    if any(x in value for x in ("payer maintenant", "carte bancaire", "prélèvement", "effectuer le paiement", "rembourser l'argent")):
        return {"reply": "Ce POC ne traite aucun paiement réel et ne doit recevoir aucune donnée bancaire. Je peux uniquement expliquer une procédure fictive ou simuler une orientation vers un conseiller.", "intent": "cotisation", "service": "Cotisations", "procedure": "Information sans transaction", "next_question": "Souhaitez-vous une explication fictive de la procédure ?", "resolution": "Transaction refusée par le mode démonstration", "escalation": "none", "reason": "Paiement réel interdit"}
    if any(x in value for x in ("connexion", "connecter", "mot de passe", "portail", "bug", "erreur technique")):
        return {"reply": "Je comprends que vous rencontrez un problème technique. Je simule la transmission de votre demande au support IT avec le résumé de notre échange.", "intent": "it_support", "service": "Support IT", "procedure": "Diagnostic et transfert IT", "next_question": "", "resolution": "Ticket IT fictif, non transmis", "escalation": "it", "reason": "Incident technique détecté"}
    if any(x in value for x in ("réclamation", "bloqué", "plainte", "fraude", "mécontent")):
        return {"reply": "Je comprends votre préoccupation. Ce cas nécessite un examen personnalisé. Je vais l'orienter vers un conseiller humain.", "intent": "reclamation", "service": "Réclamations", "procedure": "Qualification d'une réclamation", "next_question": "", "resolution": "Rappel par un conseiller simulé", "escalation": "human", "reason": "Examen humain requis"}
    mappings = [
        (("adhésion", "adhérer", "immatriculation"), "adhesion", "Adhésion", "Qualification d'une adhésion", "La demande concerne-t-elle une nouvelle immatriculation ou la mise à jour d'un dossier ?"),
        (("cotisation", "paiement", "payer"), "cotisation", "Cotisations", "Vérification d'une cotisation", "Quelle est la période concernée par la cotisation ?"),
        (("prestation", "remboursement", "remboursé"), "prestation", "Prestations", "Suivi d'une prestation", "Quelle est la nature de la prestation et son statut actuel ?"),
    ]
    for words, intent, service, procedure, reply in mappings:
        if any(word in value for word in words):
            return {"reply": reply, "intent": intent, "service": service, "procedure": procedure, "next_question": reply, "resolution": "", "escalation": "none", "reason": ""}
    reply = "Si je comprends bien, vous souhaitez être orienté dans une démarche ASACI. Pouvez-vous préciser s'il s'agit d'une adhésion, d'une cotisation, d'une prestation ou d'une réclamation ?"
    return {"reply": reply, "intent": "general", "service": "Accueil", "procedure": "Qualification initiale", "next_question": reply, "resolution": "", "escalation": "none", "reason": ""}


def _extract_json(value: str) -> dict:
    match = re.search(r"\{.*\}", value, re.DOTALL)
    if not match:
        raise ValueError("Réponse structurée absente")
    result = json.loads(match.group(0))
    if result.get("escalation") not in {"none", "human", "it"}:
        raise ValueError("Escalade invalide")
    return result


def answer(messages: list[dict], text: str) -> dict:
    if not settings.openai_api_key:
        return _mock_answer(text)
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-10:])
    response = client.responses.create(
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
        raise RuntimeError("La transcription audio nécessite OPENAI_API_KEY. Le chat texte reste disponible en mode démo.")
    from openai import OpenAI
    stream = BytesIO(data)
    stream.name = filename or "audio.webm"
    result = OpenAI(api_key=settings.openai_api_key).audio.transcriptions.create(
        model=settings.transcribe_model, file=stream, language="fr")
    return result.text


def synthesize(text: str) -> bytes:
    if not settings.openai_api_key:
        return b""
    from openai import OpenAI
    response = OpenAI(api_key=settings.openai_api_key).audio.speech.create(
        model=settings.tts_model, voice=settings.tts_voice, input=text,
        instructions="Parle en français, chaleureusement, clairement et à un rythme de service client.")
    return response.content
