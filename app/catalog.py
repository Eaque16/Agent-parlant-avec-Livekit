PROCEDURES = [
    {"id": "adhesion-qualification", "version": "1.0", "service": "Adhésion", "service_code": "adhesion", "name": "Qualification d'une adhésion", "steps": ["Identifier le type de demande", "Vérifier les informations nécessaires", "Orienter vers le guichet adhésion"]},
    {"id": "cotisations-verification", "version": "1.0", "service": "Cotisations", "service_code": "cotisations", "name": "Vérification d'une cotisation", "steps": ["Identifier la période", "Recueillir une référence non sensible", "Proposer le canal de régularisation"]},
    {"id": "prestations-suivi", "version": "1.0", "service": "Prestations", "service_code": "prestations", "name": "Suivi d'une prestation", "steps": ["Identifier la prestation", "Qualifier son statut", "Informer ou transmettre au gestionnaire"]},
    {"id": "reclamations-qualification", "version": "1.0", "service": "Réclamations", "service_code": "reclamations", "name": "Qualification d'une réclamation", "steps": ["Reformuler la difficulté", "Conserver le contexte utile", "Escalader vers un conseiller"]},
    {"id": "support-it-diagnostic", "version": "1.0", "service": "Support IT", "service_code": "support_it", "name": "Diagnostic et transfert IT", "steps": ["Qualifier l'incident", "Conserver le message d'erreur", "Créer une escalade IT"]},
]


PROCEDURES_BY_ID = {item["id"]: item for item in PROCEDURES}
