# PerceptionAI
It's not what you said, it's how you said it. Perception AI will tell you both of those things in just a quick, 20-second, speech-to-text analysis.

🧠 PerceptionAI — Real-Time Voice Intelligence
🎙️ Powered by FastAPI · React · WebSockets · Fish Audio ASR
🚀 Overview

PerceptionAI is a real-time speech-to-text platform built for the modern voice-driven web.
It streams audio directly from the user’s browser microphone, transmits it through a high-performance FastAPI WebSocket backend, and interfaces with the Fish Audio API for transcription and natural language analysis.

Originally created for Cal Hacks, this project demonstrates how to seamlessly combine AI voice intelligence, cloud-scale ASR (Automatic Speech Recognition), and real-time web tech into a cohesive, production-ready experience.

🧱 Project Structure
PerceptionAI/
│
├── README.md                     ← this file
├── scripts/
│   └── dev.sh                    ← unified local dev launcher (frontend + backend)
│
├── server/                       ← FastAPI backend (Python 3.13)
│   ├── .env                      ← API keys and environment vars (ignored by git)
│   ├── requirements.txt          ← backend dependencies
│   ├── app/
│   │   ├── main.py               ← entrypoint defining /ws/stream WebSocket
│   │   ├── config.py             ← loads env variables via pydantic-settings
│   │   ├── fish_audio/
│   │   │   ├── client.py         ← abstraction for Fish Audio ASR + WS clients
│   │   │   └── __init__.py
│   │   └── __init__.py
│   └── .venv/                    ← Python virtual environment (ignored)
│
├── web/                          ← React/Vite frontend
│   ├── index.html                ← HTML root served by Vite
│   ├── package.json              ← npm dependencies
│   ├── src/
│   │   ├── App.tsx               ← main React component / UI
│   │   ├── audio.ts              ← microphone capture + PCM streaming
│   │   ├── main.tsx              ← ReactDOM mount entrypoint
│   │   └── components/           ← optional UI components
│   └── tsconfig.json             ← TypeScript config
│
└── ...

💡 Tech Stack
Layer	Language / Framework	Description
Frontend	React + TypeScript + Vite	Fast developer experience, modular component system, WebSocket support
Audio Handling	Web Audio API (AudioWorklet / ScriptProcessor)	Captures live mic input, encodes PCM16, streams to backend
Backend	Python 3.13 + FastAPI	High-performance ASGI framework for REST & WebSocket routes
Async Runtime	uvicorn + asyncio	Concurrent, event-driven network layer
External AI Service	Fish Audio API	Provides ASR (speech-to-text) and TTS (text-to-speech) via REST and WS
HTTP Client	httpx	Async HTTP uploads for audio files
Realtime Transport	websockets	For optional realtime mode (Fish’s WS endpoint)
Configuration	pydantic-settings	Type-safe environment management
Package Mgmt	pip / npm	Dependency management for both layers
Launcher Script	Bash (scripts/dev.sh)	Runs server & frontend concurrently for dev
⚙️ Module Breakdown
🧩 Server — server/app/
File	Purpose
main.py	Defines /ws/stream, handles WebSocket lifecycle, receives audio chunks, calls Fish ASR, emits transcripts
config.py	Loads .env safely using pydantic-settings, defines API URLs, keys, and DB params
fish_audio/client.py	Unified API client supporting both ASR REST (default) and Realtime WS (optional). Includes mock mode for local testing.
Key Classes

FishAudioASRClient

Buffers PCM16 data → writes WAV → uploads to https://api.fish.audio/v1/asr.

Handles async REST requests via httpx.

Emits final transcript events through an asyncio.Queue.

FishAudioRealtimeWSClient

(Experimental) Connects to Fish’s WS for streaming transcription.

Uses websockets.connect with Bearer headers and SSL context.

get_fish_client()

Chooses between REST, Realtime, or Mock modes depending on FISH_MODE in .env.

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

Create a file called .env in server/:

FISH_API_KEY=sk_live_your_api_key_here
FISH_MODE=asr_rest
FISH_ASR_URL=https://api.fish.audio/v1/asr
FISH_REALTIME_WS=wss://api.fish.audio/v1/realtime


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

Backend buffers chunks → on { "type": "end" }, saves to .wav.

Fish ASR API transcribes → returns JSON with text + segments.

Backend sends transcript.final to browser.

UI displays transcript and timing data.

🎤 Recording a Message (Locally)
A) Through the app

Run ./scripts/dev.sh

Open http://localhost:5175

Click Record

Speak normally for a few seconds

Click Stop

The transcript appears below

B) Through the terminal (manual test)

Use ffmpeg to record and transcribe manually:

# record 5 seconds of mono PCM16 audio
ffmpeg -f avfoundation -i ":0" -t 5 -ac 1 -ar 16000 test.wav

# run backend transcription manually
python - <<'PY'
import asyncio
from app.fish_audio.client import FishAudioASRClient
async def main():
    client = FishAudioASRClient()
    await client.connect()
    with open("test.wav", "rb") as f:
        await client.send_audio(f.read())
    await client.mark_end_of_input()
    async for ev in client.events():
        print(ev)
        break
asyncio.run(main())
PY

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
          │  - FishAudioASRClient()    │
          └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │   Fish Audio Cloud API     │
         │   - /v1/asr (REST)         │
         │   - /v1/realtime (WS)      │
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

✅ Realtime ASR via Fish WebSocket

🧩 Speaker diarization

🎧 TTS playback

🧠 Sentiment & emotion analysis

☁️ Deploy on Render / Fly.io

📊 Live word visualization dashboard

🤝 Credits

Fish Audio — API provider for ASR/TTS

FastAPI — backend framework

Vite + React — modern web UI stack

Cal Hacks Team — for inspiration & community

📜 License

MIT License © 2025 Dhilon Prasad & Contributors

🏁 Quick Start TL;DR
git clone https://github.com/<you>/PerceptionAI.git
cd PerceptionAI
./scripts/dev.sh
# Visit http://localhost:5175
# Click 🎙️ Record → speak → ⏹ Stop → read your transcript!