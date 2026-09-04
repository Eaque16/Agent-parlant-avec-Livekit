# Agent vocal conversationnel ASACI — POC

Preuve de concept d'une assistante de service client francophone, « Awa ». Elle propose une console d'appel web (texte et voix), un worker vocal temps réel via LiveKit, un parcours téléphonique compatible TwiML, la persistance des échanges, un état métier structuré publié en direct et l'orientation vers un conseiller humain ou le support IT.

> **Périmètre de sécurité :** ce POC utilise exclusivement des scénarios et données fictifs ou anonymisés. Il ne se connecte à aucune plateforme ASACI, ne réalise aucun paiement et n'exécute aucune action irréversible.

## Architecture

```text
Navigateur (React) ──HTTP/WS──▶ API FastAPI ──▶ SQLite (conversations, messages, états métier, audit)
      │                              ▲
      │ WebRTC (LiveKit Cloud)       │ canal interne authentifié
      ▼                              │
Worker LiveKit Agents ── Gemini Live (défaut) ou OpenAI Realtime
Téléphone ──TwiML──▶ /telephony/* ──▶ API FastAPI
```

```text
app/                    API FastAPI
  main.py               application, cycle de vie, interface React compilée
  config.py             réglages lus depuis l'environnement
  database.py           persistance SQLite et rétention
  catalog.py            catalogue des procédures autorisées
  integrations.py       frontière des futures intégrations (simulées)
  realtime.py           jetons LiveKit éphémères
  api/                  routeurs : system, conversations, business_state, internal, admin, telephony, ws
  schemas/              contrats Pydantic (requêtes, état métier)
  services/             IA, tour de conversation, état métier, filtrage PII, files simulées
  static/               bundle React compilé (généré par `npm run build`)
agent/                  Worker vocal LiveKit Agents
  worker.py             point d'entrée, choix du fournisseur vocal
  config.py             réglages du worker
  state_publisher.py    publication des états vers la room et le backend
  prompts/              prompt système d'Awa
  tools/                outils métier appelables par le modèle
frontend/               Application React + Vite + TypeScript
tests/                  pytest (API, état métier, outils du worker)
docs/                   scénarios de démonstration et rapport technique
```

## Démarrage rapide

Prérequis : Python 3.11+, Node.js 22 (pour modifier le frontend).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Ouvrir <http://localhost:8000>. Le mode texte fonctionne sans aucun service externe grâce à un moteur déterministe. Essayer :

- « Je souhaite adhérer » pour un guidage métier ;
- « Mon portail affiche une erreur » pour une orientation IT ;
- « Mon dossier est bloqué, je veux faire une réclamation » pour un conseiller humain.

La documentation interactive est disponible sur <http://localhost:8000/docs>.

### Worker vocal (voix-à-voix)

Le worker rejoint la room LiveKit de chaque conversation et dialogue en français avec Gemini Live par défaut. Renseigner dans `.env` : `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GOOGLE_API_KEY`, `AGENT_INTERNAL_API_KEY` et `INTERNAL_API_KEY`.

```powershell
python -m agent.worker dev
```

`VOICE_PROVIDER=openai` bascule sur OpenAI Realtime (nécessite `OPENAI_API_KEY`).

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite écoute sur <http://localhost:5173> et transfère `/api`, `/health` et `/ws` vers FastAPI. `npm run build` compile l'interface dans `app/static/`, qui est versionné pour le déploiement monolithique.

### Conteneurs

```powershell
docker compose up --build
```

Démarre l'API et le worker vocal. Les variables sont lues depuis `.env`.

## Configuration

| Variable | Rôle |
| --- | --- |
| `DATABASE_PATH`, `RETENTION_DAYS` | Base SQLite et durée de conservation |
| `PUBLIC_BASE_URL` | URL publique utilisée par les webhooks téléphoniques |
| `ADMIN_API_KEY` | En-tête `X-Admin-Key` des routes `/api/admin/*` |
| `AGENT_INTERNAL_API_KEY` | En-tête `X-Agent-Key` : le worker renvoie transcriptions et réponses |
| `INTERNAL_API_KEY` | En-tête `X-Internal-Key` : le worker publie les états métier |
| `VOICE_PROVIDER`, `GOOGLE_*`, `OPENAI_REALTIME_*` | Fournisseur vocal du worker |
| `LIVEKIT_*` | Accès LiveKit Cloud et durée de vie des jetons |
| `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `OPENAI_TRANSCRIBE_MODEL`, `OPENAI_TTS_*` | Canal texte et audio du navigateur (optionnel) |
| `DEMO_MODE`, `INTEGRATIONS_ENABLED` | Garde-fous : intégrations simulées uniquement |

Les canaux internes refusent toute requête tant que leur clé n'est pas configurée. Ne commitez jamais `.env`.

## API

| Route | Usage |
| --- | --- |
| `GET /health` | État du service et fournisseur actif |
| `GET /api/procedures` | Catalogue des procédures autorisées |
| `GET /api/demo/capabilities` | Garde-fous et fonctions futures |
| `POST /api/conversations` | Créer une conversation |
| `GET /api/conversations/{id}` | Lire une conversation et ses messages |
| `POST /api/conversations/{id}/messages` | Envoyer un message texte |
| `POST /api/conversations/{id}/audio` | Envoyer un enregistrement (nécessite OpenAI) |
| `GET /api/conversations/{id}/state` et `/state/history` | État métier courant et historique |
| `WS /ws/conversations/{id}` | Diffusion temps réel des états métier |
| `GET /api/queues` | Files d'escalade simulées |
| `POST /api/realtime/token` | Jeton LiveKit éphémère limité à une room |
| `GET /api/admin/conversations`, `POST /api/admin/retention/purge` | Back-office |
| `POST /telephony/incoming`, `POST /telephony/turn/{id}` | Webhooks TwiML |

Le worker utilise deux routes internes hors documentation : `/api/internal/conversations/{id}/agent-events` et `/internal/conversations/{id}/state`.

## Qualité

```powershell
pytest                       # 31 tests, base temporaire isolée, .env ignoré
ruff check app agent tests   # lint
ruff format app agent tests  # formatage
cd frontend
npm run typecheck
npm test
npm run format:check
```

## Sécurité et exploitation

- Les numéros d'appelant ne sont conservés que sous forme des quatre derniers caractères.
- Les données sensibles (carte, IBAN, cryptogramme, mot de passe) sont refusées ou masquées avant persistance, avec trace d'audit.
- Les clés sont comparées en temps constant ; les secrets restent dans l'environnement.
- Le jeton LiveKit expire après 300 secondes par défaut et ne permet de rejoindre qu'une seule room.
- `DEMO_MODE=true` verrouille les intégrations sur des réponses fictives ; les paiements, remboursements, suppressions et validations sont interdits.
- L'image Docker s'exécute avec un utilisateur non privilégié et expose un contrôle de santé.
- Pour la production : PostgreSQL managé, coffre de secrets, validation des signatures téléphoniques, SSO du back-office, observabilité sans données personnelles.

## Documentation

- [docs/scenarios.md](docs/scenarios.md) : scénarios de démonstration.
- [docs/rapport-technique.txt](docs/rapport-technique.txt) : rapport technique et pédagogique.

## Limites assumées

Les procédures incluses sont des exemples à faire valider par les responsables métier ASACI. L'escalade crée un état, un ticket fictif et un événement d'audit ; le branchement réel vers un CRM, une file de conseillers ou un outil ITSM se fait derrière cet événement.
