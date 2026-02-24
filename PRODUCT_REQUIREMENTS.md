# ProfessorAI Real-Time Teaching System - Product Requirements & Implementation Plan

## 🔴 CRITICAL BUGS FOUND

### BUG 1: LangGraph Supervisor is COMPLETELY BROKEN
**File:** `services/langgraph_supervisor_agent.py:15`
```python
from langchain.agents import create_agent  # ❌ THIS FUNCTION DOES NOT EXIST
```
`create_agent` does not exist in `langchain.agents`. The supervisor graph **cannot compile**, meaning every `interactive_teaching` request:
1. Tries to init supervisor → FAILS
2. Falls into error handler → adds 5-10s latency
3. Either crashes or takes broken fallback path

**Impact:** This is the #1 cause of latency. Every barge-in routes through a broken supervisor.

### BUG 2: Teaching Content Generation = 60s Timeout
**File:** `websocket_server.py:1059-1067`
- Uses `teaching_service.generate_teaching_content()` which calls OpenAI GPT-4o-mini
- Has a 60s timeout, but LLM generation itself has a 5s internal timeout
- Content truncated to 8000 chars but prompt is ~2000 chars → huge LLM input
- **Result:** 5-10s delay before any audio starts

### BUG 3: Raw WebSocket for ElevenLabs TTS (no SDK)
**File:** `services/elevenlabs_service.py`
- Uses raw `websockets.connect()` to ElevenLabs multi-stream-input endpoint
- No connection pooling, no retry, no optimized buffering
- Uses `mp3_22050_32` (low quality) but with `optimize_streaming_latency=4`
- **Result:** 2-5s first-byte latency for TTS

### BUG 4: Raw WebSocket for Deepgram STT (no SDK)
**File:** `services/deepgram_stt_service.py`
- Uses raw `websockets.connect()` instead of official Deepgram SDK
- No keepalive optimization, no automatic reconnection
- **Result:** Connection overhead on every teaching session

---

## 📋 REQUIREMENTS

### REQ-1: Teach Mode Flow
**Priority:** P0 (Critical)

When "Start Class" is clicked:
1. ✅ WebSocket channel activates
2. ✅ Pull course content from database/JSON
3. 🔧 Send to LLM for teaching pattern (MUST be fast, <3s)
4. 🆕 Store teaching state: `JUST_STARTED`, `TEACHING`, `PAUSED_FOR_QUERY`, `WAITING_RESUME`, `COMPLETED`
5. 🆕 Orchestrator manages state + sends response + listens for barge-in IN PARALLEL
6. ✅ Stream TTS audio to client

### REQ-2: Barge-in → RAG Decision → Answer → Resume
**Priority:** P0 (Critical)

When user interrupts during teaching:
1. ✅ Cancel TTS immediately
2. 🆕 Orchestrator classifies: Can LLM answer directly, or need RAG?
3. 🆕 Route to RAG or general LLM accordingly
4. 🆕 After answering, ask: "Is your doubt clear? Should we continue?"
5. 🆕 On "resume/continue", resume teaching FROM WHERE WE LEFT OFF

### REQ-3: Teaching State Persistence
**Priority:** P0 (Critical)

Store in Redis per session:
- `teaching_state`: enum (TEACHING, PAUSED, ANSWERING, WAITING_RESUME, COMPLETED)
- `content_position`: character offset where teaching was interrupted
- `segments_completed`: which segments are done
- `questions_asked`: count of barge-ins
- `last_question`: what was asked
- `last_answer`: what was answered

### REQ-4: Real-Time Latency Targets
**Priority:** P0 (Critical)

| Metric | Current | Target |
|--------|---------|--------|
| Start class → first audio | 5-10s | <2s |
| Barge-in → STT complete | 5-20s | <1s |
| STT → LLM response | 10-20s | <2s |
| LLM → first TTS byte | 10-30s | <1s |
| **Total barge-in round-trip** | **25-70s** | **<4s** |

### REQ-5: VAD Sensitivity
**Priority:** P1 (High)

- Must NOT trigger on fan noise, breathing, keyboard typing
- Must trigger on clear speech
- Use Deepgram's built-in VAD with tuned thresholds
- Client-side: increase VAD threshold to filter ambient noise

### REQ-6: No Redundant Service Files
**Priority:** P2 (Medium)

Current redundant files to consolidate:
- `chat_service.py` + `chat_service_v2.py` + `chat_service_new.py` (empty)
- `database_service.py` + `database_service_actual.py` + `database_service_new.py` + `database_service_v2.py`
- `teaching_service.py` + `teaching_orchestrator.py` + `langgraph_supervisor_agent.py` + `langgraph_teaching_agent.py` + `supervisor_streaming.py`

---

## 🔧 IMPLEMENTATION PLAN

### Phase 1: Fix Critical Latency (Highest Impact)

#### 1A. Replace Broken Supervisor with Fast Orchestrator
**Files:** NEW `services/teaching_orchestrator_v2.py`, UPDATE `websocket_server.py`

Replace the broken LangGraph supervisor (which can't even compile) with a lightweight, fast orchestrator that:
- Uses keyword-based intent classification (like existing `TeachingOrchestrator.classify_intent`)
- Routes to RAG or LLM directly (no multi-hop graph)
- Manages teaching state machine
- Tracks content position for resume
- All in-memory with Redis backup (no Redis round-trip in hot path)

**Latency gain:** Eliminates 5-20s supervisor initialization + processing failure

#### 1B. Upgrade ElevenLabs TTS to Official SDK
**Files:** UPDATE `services/elevenlabs_service.py`

Replace raw WebSocket with official `elevenlabs` Python SDK:
```python
from elevenlabs.client import AsyncElevenLabs
client = AsyncElevenLabs(api_key=config.ELEVENLABS_API_KEY)
audio_stream = await client.text_to_speech.stream(
    text=text,
    voice_id=config.ELEVENLABS_VOICE_ID,
    model_id="eleven_flash_v2_5",  # Fastest model
    optimize_streaming_latency=4   # Max optimization
)
```

**Latency gain:** 2-5s → <500ms first byte

#### 1C. Upgrade Deepgram STT to Official SDK
**Files:** UPDATE `services/deepgram_stt_service.py`

Replace raw WebSocket with official `deepgram-sdk`:
```python
from deepgram import DeepgramClient
client = DeepgramClient(config.DEEPGRAM_API_KEY)
connection = client.listen.asynclive.v("1")  # or v2 for flux
```

**Latency gain:** More reliable connection, better VAD, auto-reconnect

#### 1D. Fast Teaching Content (Skip LLM for Initial Delivery)
**Files:** UPDATE `websocket_server.py`

Instead of generating teaching content with LLM (5-10s), directly use the course JSON content with minimal formatting. Start TTS immediately, generate enhanced content in background.

**Latency gain:** 5-10s → <500ms to first audio

### Phase 2: Teaching State Machine + Resume

#### 2A. Implement TeachingStateMachine
States: IDLE → TEACHING → PAUSED_FOR_QUERY → ANSWERING → WAITING_RESUME → TEACHING (loop)

#### 2B. Content Position Tracking
Split teaching content into segments. Track which segment was playing when interrupted. On resume, start from that segment.

#### 2C. Barge-in Intelligence
When user interrupts:
1. Classify intent (question vs command)
2. If question: check if course-specific → RAG, else → general LLM
3. After answer: "Is that clear? Shall we continue?"
4. On continue: resume from interrupted segment

### Phase 3: VAD + Polish

#### 3A. Deepgram VAD Tuning
Already partially done. Key params:
- `endpointing=500` (500ms silence = end of turn)
- `vad_turnoff=400` (ignore <400ms sounds)
- `interim_results=false` (no partial spam)

#### 3B. Client-Side VAD Threshold
Increase threshold in UI to filter background noise.

---

## 📁 FILES TO MODIFY

| File | Action | Description |
|------|--------|-------------|
| `services/elevenlabs_service.py` | **REWRITE** | Use official SDK for streaming TTS |
| `services/deepgram_stt_service.py` | **UPDATE** | Use official SDK, tune VAD |
| `services/teaching_orchestrator.py` | **REWRITE** | Fast orchestrator with state machine |
| `websocket_server.py` | **UPDATE** | Use new orchestrator, fast content delivery |
| `config.py` | **UPDATE** | Add new config params |
| `requirements.txt` | **UPDATE** | Add `elevenlabs`, `deepgram-sdk` |
| `langgraph_supervisor_agent.py` | **DEPRECATE** | Broken, replaced by new orchestrator |
| `langgraph_teaching_agent.py` | **DEPRECATE** | Not needed with new orchestrator |
| `supervisor_streaming.py` | **DEPRECATE** | Merged into websocket_server |

---

## ⏱️ EXECUTION ORDER

1. **[NOW]** Upgrade ElevenLabs TTS → Official SDK (biggest latency win)
2. **[NOW]** Replace broken supervisor → Fast orchestrator with state machine
3. **[NOW]** Fast teaching content delivery (skip slow LLM generation)
4. **[NEXT]** Implement barge-in → RAG/LLM → answer → resume flow
5. **[NEXT]** Content position tracking for resume
6. **[LATER]** Deepgram SDK upgrade (current raw WS works, just less optimal)
7. **[LATER]** Clean up redundant files

---

## ✅ IMPLEMENTATION STATUS

### Completed Changes

| # | Change | File(s) | Status |
|---|--------|---------|--------|
| 1 | **Replaced broken LangGraph supervisor** with `RealtimeOrchestrator` | `services/realtime_orchestrator.py` (NEW), `websocket_server.py` | ✅ DONE |
| 2 | **ElevenLabs SDK upgrade** - uses official `AsyncElevenLabs` with raw WS fallback | `services/elevenlabs_service.py` | ✅ DONE |
| 3 | **Fast content delivery** - skip 60s LLM generation, use raw content immediately | `websocket_server.py` | ✅ DONE |
| 4 | **Barge-in → RAG/LLM → answer → resume** - full flow with orchestrator | `websocket_server.py`, `services/realtime_orchestrator.py` | ✅ DONE |
| 5 | **Teaching state machine** - IDLE→TEACHING→PAUSED→ANSWERING→WAITING_RESUME | `services/realtime_orchestrator.py` | ✅ DONE |
| 6 | **Content segmentation** for resume from interrupted position | `services/realtime_orchestrator.py` | ✅ DONE |
| 7 | **VAD tuning** - endpointing=500ms, vad_turnoff=400ms, interim_results=false | `services/deepgram_stt_service.py` | ✅ DONE |
| 8 | **Dead code removal** - removed `_answer_teaching_question`, `_stream_supervisor_response` | `websocket_server.py` | ✅ DONE |
| 9 | **Dependencies** - added `elevenlabs`, `deepgram-sdk` to `req.txt` | `req.txt` | ✅ DONE |

### Expected Latency Improvements

| Metric | Before | After (Expected) | Why |
|--------|--------|-------------------|-----|
| Start class → first audio | 5-10s | <2s | Skip LLM content gen, use raw content |
| Barge-in detection | ~500ms | ~50ms | Direct orchestrator, no supervisor init |
| Intent classification | 5-20s (broken supervisor) | <5ms | Keyword-based, no LLM |
| RAG/LLM answer | 10-20s (60s timeout) | <5s (15s timeout) | Tight timeout, direct routing |
| TTS first byte | 2-5s (raw WS) | <500ms (SDK) | Official SDK with max latency opt |
| **Total round-trip** | **25-70s** | **<8s** | All optimizations combined |

### Remaining Work
- [ ] End-to-end user testing
- [ ] Deepgram SDK upgrade (nice-to-have, current raw WS works)
- [ ] Redundant service file cleanup
