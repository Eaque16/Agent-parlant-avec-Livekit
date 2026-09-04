# Scénarios de démonstration ASACI

Toutes les personnes, références et actions de ces scénarios sont fictives. Aucun paiement ni changement réel n'est exécuté.

## 1. Adhésion

1. Appelant : « Je souhaite m'inscrire. » État : service `adhesion`, intention reformulée, procédure `adhesion-qualification`, étape 1/3.
2. Awa : « Si je comprends bien, vous souhaitez effectuer une nouvelle adhésion. S'agit-il d'une première adhésion ? »
3. Appelant : « Oui. » État : `type_demande` recueilli, étape 2/3, informations nécessaires encore manquantes affichées.
4. Awa annonce une orientation fictive. État final : résolution proposée, aucune escalade, résumé non vide.

## 2. Cotisations

1. Appelant : « Je voudrais comprendre ma cotisation de mars. » État : service `cotisations`, procédure `cotisations-verification`.
2. Awa reformule puis demande uniquement la période. L'appelant répond « mars 2026 ».
3. État : période recueillie, prochaine étape affichée. Awa explique la procédure fictive sans encaisser de paiement.
4. Si l'appelant demande de payer, Awa appelle `refuse_action`, ajoute `paiement_demande` et simule une escalade conseiller.

## 3. Prestations

1. Appelant : « Où en est ma prestation fictive ? » État : service `prestations`, procédure `prestations-suivi`.
2. Awa reformule et demande la nature de la prestation, une seule question.
3. Awa ne promet aucun délai ni statut absent du catalogue. État final : informations recueillies et orientation proposée.

## 4. Réclamation bloquée

1. Appelant : « Mon dossier de réclamation est bloqué. » État : service `reclamations`, risque `dossier_bloque`.
2. Awa reformule et recueille uniquement le contexte non sensible.
3. État : escalade `conseiller`, motif explicite et ticket `SIM-…`. Awa annonce que le ticket et la transmission sont simulés.

## 5. Incident informatique

1. Appelant : « Le portail affiche une erreur. » État : service `support_it`, procédure `support-it-diagnostic`.
2. Awa reformule puis demande le message d'erreur sans demander de mot de passe.
3. État : escalade `support_it`, risque `incident_technique`, ticket fictif unique et résumé final.
4. Pour une édition d'attestation impossible, la destination attendue est `pool_tpv`.
