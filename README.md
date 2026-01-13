# PerceptionAI
Real-time voice intelligence: fast speech-to-text with simple emotion analysis. We now extract audio features with openSMILE and train/infer models using scikit-learn.

## 🚀 Quickstart (TL;DR)
- Backend + Frontend in one command:
  - `./scripts/dev.sh` (runs FastAPI on 8001 and Vite on 5175)
- Visit http://localhost:5175
- Click “🎙️ Record”, speak, then use the controls:
  - ⏸️ Pause Conversation: finalize the current segment, timer/emotion will keep accumulating after you click Record again
  - 🔪 Clip Script: finalize current segment and create a distinct clip entry

That’s it. See below for details if you need them.

PerceptionAI is a real-time speech-to-text platform built for the modern voice-driven web.
It streams audio directly from the user’s browser microphone and transmits it through a high-performance FastAPI WebSocket backend for on-device feature extraction and emotion analysis.

Originally created for Cal Hacks, this project demonstrates how to seamlessly combine AI voice intelligence, cloud-scale ASR (Automatic Speech Recognition), and real-time web tech into a cohesive, production-ready experience.

## 🧱 Project Structure
```text
PerceptionAI/
├─ README.md                         # this file
├─ scripts/
│  └─ dev.sh                         # unified local dev launcher (frontend + backend)
├─ server/                           # FastAPI backend (Python 3.13)
│  ├─ .env                           # API keys and env vars (ignored)
│  ├─ requirements.txt               # backend dependencies
│  └─ app/
│     ├─ main.py                     # /ws/stream WebSocket
│     ├─ config.py                   # env via pydantic-settings
│     └─ ...
└─ web/                              # React/Vite frontend
   ├─ index.html
   ├─ package.json
   └─ src/
      ├─ App.tsx                     # main UI
      ├─ lib/                        # ws/audio helpers
      └─ components/                 # UI components
```

## 💡 Tech Stack

| Layer | Language / Framework | Description |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite | Modular UI, fast DX, WebSocket support |
| Audio Handling | Web Audio API (AudioWorklet) | Capture mic, encode PCM16, stream WS |
| Audio Features | openSMILE | Low-level descriptors extraction from audio |
| ML Models | scikit-learn | Training and inference for emotion models |
| Backend | Python 3.13, FastAPI | High-performance REST + WebSocket |
| Async Runtime | uvicorn, asyncio | Concurrent, event-driven networking |
| HTTP Client | httpx | Async uploads for REST |
| Realtime | websockets | WebSocket transport between frontend and backend |
| Config | pydantic-settings | Type-safe env management |
| Package Mgmt | pip, npm | Dependencies for both layers |
| Launcher | Bash (`scripts/dev.sh`) | One command to run both apps |

## ⚙️ Module Breakdown
🧩 Server — server/app/
File	Purpose
main.py	Defines /ws/stream, handles WebSocket lifecycle, receives audio chunks, emits emotion predictions
config.py	Loads .env safely using pydantic-settings, defines API URLs, keys, and DB params
audio/feature_extractor.py	Extracts openSMILE features (LLDs/statistics) from WAV/PCM audio
model/emotion_model.py	Loads and runs a scikit-learn emotion model
model/train_emotion_model.py	Training script to fit scikit-learn models on extracted features
Key Components

🌐 Frontend — web/src/
File	Role
App.tsx	Main UI: record button, transcript display, and status indicators
audio.ts	Core capture module using AudioContext and ScriptProcessorNode (or AudioWorklet). Converts Float32 → Int16 PCM, sends binary WS frames
main.tsx	React entrypoint, mounts App to DOM
index.html	Vite entry point; loads compiled JS bundle
WebSocket Flow

Frontend opens a WS: ws://localhost:8001/ws/stream

binaryType = "arraybuffer"

Sends PCM16 byte chunks continuously.

When user stops recording, sends { "type": "end" }.

Server responds with { "type": "transcript.final", "data": {...} }.

🧩 Setup Instructions
🧰 1. Clone Repository
git clone https://github.com/<yourname>/PerceptionAI.git
cd PerceptionAI

🐍 2. Backend Setup
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Environment File


⚠️ Never commit .env — it’s ignored by .gitignore.

💻 3. Frontend Setup
cd ../web
npm install

▶️ 4. Launch Everything (Recommended)

Run the provided dev script:

./scripts/dev.sh


This will:

Activate your venv

Start uvicorn app.main:app --reload --port 8001

Launch vite on port 5175

Output live logs for both

Access your app at: http://localhost:5175

⚙️ 5. Manual Launch (if needed)
# Terminal 1
cd server && source .venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Terminal 2
cd web && npm run dev -- --port 5175

🧩 Recording Flow
🗣️ How it works

User clicks Record → frontend requests mic access.

Browser streams audio frames as binary PCM16 over WS.

Backend buffers chunks, extracts features, predicts emotion, and streams results back to the browser.

UI displays transcript and timing data.

🎤 Recording a Message (Locally)
A) Through the app

Run ./scripts/dev.sh

Open http://localhost:5175

Click Record

Speak normally for a few seconds

Click Stop

The transcript appears below

### 🎛️ Controls: Pause Conversation vs. Clip Script

#### ⏸️ Pause Conversation
- Temporarily halts streaming without clearing the timer.
- On click, the frontend sends `{ "type": "end" }` to the WebSocket, prompting the backend to finalize the current segment.
- Timer continues from where it left off when you resume recording (no reset to 0).
- Use when you want a clean transcript boundary without discarding previous content.

#### 🔪 Clip Script
- Finalizes the current segment and creates a new transcript entry immediately.
- Intended to “clip” the current script unit. Useful for marking takes/sections while staying in the same session.
- This also issues `{ "type": "end" }`, but your UI will show the clipped chunk distinctly.

Notes
- If you prefer one-shot uploads instead of streaming, send `{ "type": "upload", audio_b64 }` where `audio_b64` is your PCM16 audio as Base64; the server will replace the buffer and finalize right away.
- In REST mode, the server accumulates or replaces bytes internally and converts to `.wav` on finalize.

## 🎚️ Emotion Metrics: Valence & Arousal

We score emotion along two continuous dimensions plus a discrete label:

- Valence (-1.00 to 1.00): how positive vs. negative the tone is.
  - 0.00 ≈ very negative; 1.00 ≈ very positive.
  - Fused as: `valence = 0.65 * text_valence + 0.35 * audio_valence`, where `text_valence = (polarity + 1) / 2` and `audio_valence` comes from prosody.

- Arousal (0.00 to 1.00): how activated/energetic the delivery is.
  - 0.00 ≈ very calm; 1.00 ≈ very intense/energized.
  - Fused as: `arousal = 0.5 * text_arousal + 0.5 * audio_arousal`.

<img width="576" height="388" alt="image" src="https://github.com/user-attachments/assets/fb0b8ca4-b570-4ee7-80d4-45d12fcc0d83" />


- Label: selected from the 24-label taxonomy (Happy, Sad, Angry, …) plus the graph displayed below to fit the fused valence/arousal quadrant and text cues.

Display
- Values are shown to two decimals (e.g., `arousal: 0.72`, `valence: 0.41`).
- Labels may include intensity (e.g., “Very Angry”, “Slightly Calm”) based on polarity magnitude.

🔍 Architecture Diagram
         ┌────────────────────────────┐
         │  React + Vite Frontend     │
         │  (TypeScript, Web Audio)   │
         └────────────┬───────────────┘
                      │
         Binary PCM16 │  WebSocket JSON Events
                      ▼
          ┌────────────────────────────┐
          │  FastAPI Server (Python)   │
          │  - WebSocket endpoint      │
          │  - EmotionModel (sklearn)  │
          └────────────┬───────────────┘
                      │
                      ▼
        ┌────────────────────────────┐
        │   Audio Feature Pipeline   │
        │   - openSMILE features     │
        │   - sklearn model          │
        └────────────────────────────┘

🧰 Dependencies
Python (backend)
Package	Purpose
fastapi	API and WebSocket framework
uvicorn	ASGI server
httpx	Async HTTP client for REST calls
websockets	Async WS client (realtime mode)
pydantic-settings	Loads .env config
asyncio	Built-in concurrency
opensmile	Audio feature extraction (LLDs, functionals)
scikit-learn	Model training and inference for emotion classification/regression
Node (frontend)
Package	Purpose
react + react-dom	UI library
vite	Lightning-fast dev bundler
typescript	Type safety
@types/react / @types/node	Type definitions
🔐 Security & Privacy

.env is ignored via .gitignore

API keys are loaded at runtime, never bundled into frontend

CORS is enabled for local development but can be restricted by domain in production

💡 Future Enhancements

🧩 Speaker diarization

🎧 TTS playback

🧠 Sentiment & emotion analysis

☁️ Deploy on Render / Fly.io

📊 Live word visualization dashboard

🤝 Credits

FastAPI — backend framework

Vite + React — modern web UI stack

Cal Hacks Team — for inspiration & community

📜 License

MIT License © 2025 Dhilon Prasad & Contributors

🏁 Quick Start TL;DR
git clone https://github.com/<you>/PerceptionAI.git
cd PerceptionAI
./scripts/dev.sh
