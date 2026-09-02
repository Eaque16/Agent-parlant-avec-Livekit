# Agent vocal conversationnel ASACI — POC

POC cloud démontrable d’une assistante de service client francophone. Il fournit une interface web texte/voix, une API documentée, un connecteur téléphonique compatible TwiML, la transcription persistée des échanges et l’orientation vers un conseiller humain ou le support IT.

> **Périmètre de sécurité :** ce POC utilise exclusivement des scénarios et données fictifs/anonymisés. Il ne se connecte à aucune plateforme ASACI, ne réalise aucun paiement et n'exécute aucune action irréversible.

## Démonstration rapide

Prérequis : Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Ouvrir <http://localhost:8000>. Le mode texte fonctionne immédiatement, sans service externe. Essayer :

- « Je souhaite adhérer » pour un guidage métier ;
- « Mon portail affiche une erreur » pour une orientation IT ;
- « Mon dossier est bloqué, je veux faire une réclamation » pour un conseiller humain.

La documentation interactive est disponible sur <http://localhost:8000/docs>.

### Développement du frontend imposé

Le frontend se trouve dans `frontend/` et utilise React, Vite, TypeScript, React Router, TanStack Query, Tailwind CSS et les composants LiveKit.

```powershell
cd frontend
npm install
npm run dev
```

Vite écoute sur <http://localhost:5173> et transfère `/api` et `/health` vers FastAPI sur le port 8000. `npm run build` compile directement l'interface dans `app/static/` pour le déploiement monolithique.

LiveKit reste déconnecté tant que le backend ne dispose pas de `LIVEKIT_URL`, `LIVEKIT_API_KEY` et `LIVEKIT_API_SECRET`. Au démarrage d'un appel, React demande `POST /api/realtime/token` : FastAPI retourne un jeton éphémère, une identité anonymisée et une room dérivée de la conversation. Le secret LiveKit ne quitte jamais le backend et aucun jeton permanent n'est intégré au bundle.

Le jeton expire après 300 secondes par défaut (`LIVEKIT_TOKEN_TTL_SECONDS`) et ne permet de rejoindre que la room indiquée. Le navigateur y publie son microphone en WebRTC et restitue les pistes audio distantes avec `RoomAudioRenderer`.

### Agent vocal voix-à-voix

Le worker `agent.worker` rejoint les rooms LiveKit Cloud et utilise OpenAI Realtime directement pour l'audio entrant et sortant. Il parle en français, accepte les interruptions et applique le périmètre fictif du POC.

```powershell
pip install -r requirements-agent.txt
python -m agent.worker dev
```

En conteneur, `docker compose up --build` démarre l'API web et le worker vocal. Les variables requises sont `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` et `OPENAI_API_KEY`.

Les transcriptions finales de l'appelant, réponses de l'agent et erreurs de session sont renvoyées vers FastAPI et rattachées à la conversation. Ce canal interne exige `AGENT_INTERNAL_API_KEY`; la valeur doit être longue, aléatoire et identique pour l'API et le worker.

## Activer la voix IA

Copier `.env.example` vers `.env`, définir `OPENAI_API_KEY`, puis charger les variables ou lancer :

```powershell
docker compose up --build
```

Sans clé, le POC reste volontairement utilisable en texte avec un moteur déterministe. Avec une clé, les fichiers micro sont transcrits, la réponse est produite selon le prompt métier et restituée vocalement.

## Parcours téléphonique

Configurer le webhook d’appel entrant du fournisseur téléphonique vers `POST /telephony/incoming` et renseigner `PUBLIC_BASE_URL` avec l’URL HTTPS publique. Le flux TwiML utilise la reconnaissance vocale du fournisseur, conserve chaque tour dans la même conversation et déclenche les escalades.

Pour un POC exposé depuis un poste local, utiliser un tunnel HTTPS de votre choix vers le port 8000. En production, valider impérativement la signature des webhooks du fournisseur.

## Architecture

```text
Navigateur / Téléphone
        │
        ▼
API FastAPI ── orchestration métier ── OpenAI (STT, réponse, TTS)
        │                   │
        │                   └── règles d’escalade humain / IT
        ▼
SQLite (POC) : conversations, messages, audit
```

- `app/main.py` : contrats HTTP, interface téléphonique et sécurité d’administration.
- `app/services.py` : adaptateur IA et moteur local de démonstration.
- `app/prompt.py` : comportement conversationnel et procédures ASACI.
- `app/database.py` : conservation, audit et politique de rétention.
- `frontend/` : application React/Vite TypeScript et intégration LiveKit optionnelle.
- `app/static/` : artefacts compilés servis par FastAPI.

## Exploitation et sécurité

- Les numéros d’appelant ne sont conservés que sous forme des quatre derniers caractères dans ce POC.
- `RETENTION_DAYS` contrôle la rétention ; `POST /api/admin/retention/purge` exécute la purge.
- Les routes `/api/admin/*` exigent l’en-tête `X-Admin-Key`.
- Les secrets restent dans l’environnement et ne sont jamais stockés en base.
- Pour la production : PostgreSQL managé, chiffrement au repos, coffre de secrets, validation des signatures téléphoniques, authentification SSO du back-office, métriques et journalisation sans données personnelles.
- L’image Docker s’exécute avec un utilisateur non privilégié et expose un contrôle de santé.
- `DEMO_MODE=true` verrouille les intégrations sur des réponses fictives.
- `app/integrations.py` est l'unique frontière prévue pour les futures APIs sécurisées.
- Les fonctions futures sont en liste blanche, réversibles et soumises à approbation humaine si nécessaire.
- Paiements, remboursements financiers, suppressions, clôtures et validations de prestations sont interdits.

## Tests

```powershell
pytest -q
```

Les tests couvrent la persistance d’une conversation et les deux circuits d’escalade.

## Limites assumées du POC

Les procédures incluses sont des exemples à faire valider par les responsables métier ASACI. L’escalade crée un état et un événement d’audit ; le branchement réel vers un CRM, une file de conseillers ou un outil ITSM se fait derrière cet événement. Le navigateur emploie la synthèse locale en mode démo et la voix OpenAI lorsque la clé est configurée.
