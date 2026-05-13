# Jarvis – Local Requirements Checklist

## 1. Concetto corretto

Non è obbligatorio eseguire **Codex come server**.

Architettura consigliata:

```text
Telegram
   ↓
Jarvis Backend Python locale
   ↓
Tools locali su macOS
   ├── Codex CLI
   ├── Document index / RAG
   ├── Apple Calendar access
   ├── Weather API
   ├── Browser automation
   └── HomeKit / Home Assistant bridge
```

Quindi il componente sempre attivo è:

```text
Jarvis backend = server locale Python
```

Codex viene eseguito dal backend come:

```text
codex ...
```

oppure tramite un piccolo wrapper locale.

---

## 2. Requisiti macchina

### Minimo consigliato

- Mac sempre acceso o comunque acceso quando vuoi usare Jarvis
- macOS recente
- 16 GB RAM consigliati
- 20–50 GB liberi su disco
- Connessione Internet stabile
- Accesso amministratore sul Mac
- Terminale / shell disponibile

### Ideale

- Mac mini / MacBook collegato alla corrente
- Utente macOS dedicato o ambiente separato per Jarvis
- Repo Git dedicato
- Backup Time Machine attivo

---

## 3. Software base

Da installare:

```bash
xcode-select --install
```

```bash
brew install python git
```

Opzionale ma consigliato:

```bash
brew install node
```

Codex CLI:

```bash
brew install codex
```

oppure:

```bash
npm install -g @openai/codex
```

Poi autenticazione:

```bash
codex
```

---

## 4. Account e chiavi necessarie

### Obbligatorie per MVP

- Account OpenAI / ChatGPT con accesso a Codex
- Telegram Bot Token
- Il tuo Telegram user ID autorizzato
- Repo locale per il progetto Jarvis

### Per fasi successive

- Apple Developer Account, se vuoi usare WeatherKit ufficiale
- Apple ID configurato sul Mac
- Accesso ai calendari Apple locali
- Eventuali permessi macOS per Calendar, Automation, Accessibility
- Home Assistant, consigliato come bridge per HomeKit

---

## 5. Python backend

Stack minimo:

```text
Python 3.11+
FastAPI oppure python-telegram-bot
uvicorn
pydantic
python-dotenv
```

Per documenti/RAG:

```text
chromadb oppure sqlite-vec
sentence-transformers oppure OpenAI embeddings
pypdf
python-docx
markdown
```

Per automation locale:

```text
subprocess
osascript / AppleScript
pyobjc, se serve accesso Apple più nativo
playwright, se serve browser automation più robusta
```

---

## 6. Telegram access

Per MVP basta polling:

```text
Jarvis backend → Telegram getUpdates
```

Vantaggio:

- niente dominio pubblico
- niente reverse proxy
- più semplice su Mac locale

Webhook solo dopo:

```text
Telegram → HTTPS endpoint pubblico → Jarvis backend
```

Richiede:

- dominio o tunnel
- HTTPS
- gestione sicurezza più attenta

---

## 7. Sicurezza minima obbligatoria

Implementare subito:

- whitelist del tuo Telegram user ID
- file `.env` fuori da Git
- log senza token/API key
- conferma esplicita prima di azioni rischiose
- limite: Codex lavora solo dentro una cartella/repo autorizzata
- Git checkpoint prima di modifiche importanti

Esempio `.env`:

```env
TELEGRAM_BOT_TOKEN=...
AUTHORIZED_TELEGRAM_USER_ID=...
JARVIS_WORKSPACE=/Users/stefano/jarvis-workspace
CODEX_HOME=/Users/stefano/.codex
```

---

## 8. Permessi macOS da prevedere

Il backend potrebbe richiedere permessi per:

- Calendar
- Contacts, se in futuro necessario
- Automation / Apple Events
- Accessibility, se deve controllare app o browser
- Full Disk Access, solo se realmente necessario
- Files and Folders access

Da evitare all’inizio:

```text
Full Disk Access globale
```

Meglio partire con una cartella dedicata:

```text
~/JarvisWorkspace
```

---

## 9. Browser automation

MVP semplice:

```bash
open "https://example.com"
```

Poi:

```text
AppleScript
Playwright
Chrome DevTools Protocol
```

Priorità:

1. Aprire URL
2. Cercare nel web e aprire risultati
3. Navigare pagine
4. Leggere contenuto pagina
5. Interagire con form solo dopo conferma

---

## 10. Apple Calendar

Opzioni:

### Semplice

Usare AppleScript / Calendar.app.

Pro:

- rapido
- locale
- buono per MVP

Contro:

- meno robusto
- dipende da permessi macOS

### Robusto

Usare EventKit tramite PyObjC o piccolo helper Swift.

Pro:

- più corretto
- più controllabile

Contro:

- più complesso

---

## 11. Apple Weather

Nota importante:

Apple Weather ufficiale significa WeatherKit.

Richiede:

- Apple Developer Program
- token JWT
- Team ID
- Service ID
- Key ID
- private key `.p8`

Per MVP puoi usare temporaneamente una API meteo più semplice oppure implementare WeatherKit dopo.

---

## 12. HomeKit

Accesso diretto HomeKit da Python non è il percorso più semplice.

Percorso consigliato:

```text
HomeKit devices
   ↓
Home Assistant
   ↓
Home Assistant REST/WebSocket API
   ↓
Jarvis backend
```

Vantaggi:

- API più semplice
- controllo centralizzato
- migliore sicurezza
- integrazione più ampia

MVP HomeKit:

- leggere stato luci/sensori
- accendere/spegnere una luce test
- sempre con whitelist comandi

---

## 13. Assistente vocale

Da lasciare dopo MVP Telegram.

Possibili step:

1. Push-to-talk locale
2. Whisper / speech-to-text
3. risposta testuale
4. text-to-speech
5. wake word locale

Non implementare subito wake word always-on.

---

## 14. MVP reale

Il primo MVP deve fare solo questo:

```text
Telegram → Jarvis Python Backend → Codex CLI / local tools → risposta Telegram
```

Funzioni MVP:

- rispondere solo al tuo user ID Telegram
- leggere documenti da una cartella autorizzata
- riassumere documenti
- cercare nei documenti
- aprire una pagina web su richiesta
- eseguire Codex nel workspace autorizzato
- loggare richieste e risposte
- chiedere conferma per azioni rischiose

---

## 15. Cosa NON fare subito

Non implementare subito:

- HomeKit completo
- assistente vocale always-on
- webhook pubblico
- controllo browser avanzato
- accesso globale al filesystem
- automazioni che modificano calendario o casa senza conferma
- gestione multiutente

---

## 16. Sequenza raccomandata

### Step 1 — Local skeleton

- repo Git
- ambiente Python
- `.env`
- logging
- comando `/health`

### Step 2 — Telegram bot

- polling
- whitelist user ID
- comandi base

### Step 3 — Codex bridge

- wrapper Python per invocare Codex CLI
- workspace limitato
- timeout
- log output

### Step 4 — Document tools

- cartella documenti
- indicizzazione
- ricerca
- riassunto

### Step 5 — Browser open

- comando Telegram:
  - `open https://...`
  - `search web ...`

### Step 6 — Apple Calendar read-only

- leggere eventi di oggi/domani
- nessuna modifica iniziale

### Step 7 — Weather

- WeatherKit o API alternativa
- comando:
  - `meteo oggi`
  - `meteo domani`

### Step 8 — Home Assistant / HomeKit bridge

- stato casa read-only
- poi primo comando controllato

### Step 9 — Voice

- push-to-talk
- speech-to-text
- text-to-speech

---

## 17. Definition of Done per MVP

Il MVP è completo quando puoi scrivere da Telegram:

```text
Jarvis, cerca nei miei documenti la nota su HANA NSE
```

e Jarvis:

- verifica che sei tu
- cerca solo nei documenti autorizzati
- opzionalmente usa Codex
- risponde su Telegram

Secondo comando MVP:

```text
Jarvis, apri google.com sul Mac
```

e Jarvis:

- apre il browser sul Mac locale
- conferma su Telegram

Terzo comando MVP:

```text
Jarvis, che eventi ho domani?
```

e Jarvis:

- legge il calendario locale
- risponde senza modificare nulla
