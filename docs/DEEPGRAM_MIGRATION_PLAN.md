# 🎙️ DEEPGRAM & ELEVENLABS MIGRATION PLAN

## 📊 **Current vs New Architecture**

### **BEFORE (Current - Sarvam AI)**
```
User Audio → Sarvam STT → LLM → Sarvam TTS → Audio Response
```

### **AFTER (New - Deepgram + ElevenLabs)**
```
User Audio → Deepgram STT (Real-time + VAD) → LLM → ElevenLabs TTS (Streaming) → Audio Response
```

---

## 🎯 **Why Migrate?**

### **Deepgram Advantages:**
- ✅ **Ultra-low latency** (~250ms)
- ✅ **Built-in VAD** (Voice Activity Detection)
- ✅ **Real-time streaming** WebSocket
- ✅ **Turn-taking & barge-in** support
- ✅ **Better accuracy** for conversational AI
- ✅ **Flux v2 model** with natural endpointing

### **ElevenLabs Advantages:**
- ✅ **High-quality voices** (most natural sounding)
- ✅ **Streaming TTS** (sub-500ms first chunk)
- ✅ **WebSocket streaming** for real-time
- ✅ **Multiple voice options**
- ✅ **Production-grade reliability**

---

## 📋 **Migration Checklist**

### **Phase 1: Add New Services** ✅
- [ ] Copy `deepgram_stt_service.py` to services/
- [ ] Copy `elevenlabs_service.py` to services/
- [ ] Update `config.py` with new API keys
- [ ] Update `requirements.txt`

### **Phase 2: Update Audio Service** ✅
- [ ] Modify `audio_service.py` to use Deepgram/ElevenLabs
- [ ] Keep Sarvam as fallback (optional)
- [ ] Add service selection logic

### **Phase 3: WebSocket Integration** ✅
- [ ] Update WebSocket handlers for Deepgram events
- [ ] Implement VAD event handling
- [ ] Add barge-in support

### **Phase 4: Testing** 🧪
- [ ] Test Deepgram STT accuracy
- [ ] Test ElevenLabs TTS quality
- [ ] Test real-time performance
- [ ] Test barge-in functionality
- [ ] Test fallback mechanisms

### **Phase 5: Deployment** 🚀
- [ ] Update .env with API keys
- [ ] Update K8s secrets
- [ ] Deploy to production
- [ ] Monitor performance

---

## 🔧 **Technical Changes Required**

### **1. New Service Files**
```
services/
├── deepgram_stt_service.py     ← NEW (Real-time STT)
├── elevenlabs_service.py       ← NEW (Streaming TTS)
├── audio_service.py            ← MODIFIED (Use new services)
└── sarvam_service.py           ← KEEP (Fallback)
```

### **2. Config Updates**
```python
# Add to config.py
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = "eleven_flash_v2_5"

# Audio provider selection
AUDIO_STT_PROVIDER = os.getenv("AUDIO_STT_PROVIDER", "deepgram")  # deepgram|sarvam
AUDIO_TTS_PROVIDER = os.getenv("AUDIO_TTS_PROVIDER", "elevenlabs")  # elevenlabs|sarvam
```

### **3. Environment Variables**
```env
# Add to .env
DEEPGRAM_API_KEY=your_deepgram_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
AUDIO_STT_PROVIDER=deepgram
AUDIO_TTS_PROVIDER=elevenlabs
```

### **4. Dependencies**
```
# Add to requirements.txt
deepgram-sdk>=3.0.0
elevenlabs>=1.0.0
websockets>=11.0.0
```

---

## 🔄 **Service Integration Pattern**

### **Current AudioService Pattern:**
```python
class AudioService:
    def __init__(self):
        self.sarvam_service = SarvamService()  # Only Sarvam
```

### **New AudioService Pattern:**
```python
class AudioService:
    def __init__(self):
        self.stt_provider = config.AUDIO_STT_PROVIDER
        self.tts_provider = config.AUDIO_TTS_PROVIDER
        
        # Initialize STT
        if self.stt_provider == "deepgram":
            self.stt_service = DeepgramSTTService()
        else:
            self.stt_service = SarvamService()
        
        # Initialize TTS
        if self.tts_provider == "elevenlabs":
            self.tts_service = ElevenLabsService()
        else:
            self.tts_service = SarvamService()
```

---

## 📡 **WebSocket Event Flow**

### **Deepgram Events:**
```javascript
// Client → Server (Audio chunks)
{
  "type": "stt_stream_start",
  "sample_rate": 16000,
  "language": "en-US"
}

{
  "type": "stt_audio_chunk",
  "audio": "base64_encoded_pcm16"
}

// Server → Client (Transcription)
{
  "type": "speech_started"  // VAD detected speech
}

{
  "type": "partial_transcript",
  "text": "Hello, I am..."
}

{
  "type": "final_transcript",
  "text": "Hello, I am speaking",
  "language": "en-US"
}

{
  "type": "utterance_end"  // User stopped speaking
}
```

### **ElevenLabs Events:**
```javascript
// Server → Client (Audio streaming)
{
  "type": "audio_chunk",
  "audio": "base64_encoded_mp3"
}

{
  "type": "audio_end"  // TTS completed
}

{
  "type": "tts_interrupted"  // Barge-in occurred
}
```

---

## 🎛️ **Feature Comparison**

| Feature | Sarvam AI | Deepgram + ElevenLabs |
|---------|-----------|----------------------|
| **STT Latency** | ~1-2s | ~250ms ✅ |
| **TTS Latency** | ~800ms | ~300ms ✅ |
| **Voice Quality** | Good | Excellent ✅ |
| **VAD** | No | Yes ✅ |
| **Barge-in** | No | Yes ✅ |
| **Streaming** | Limited | Full ✅ |
| **Languages** | Indian | Global ✅ |
| **Cost** | Lower | Higher |

---

## 🛡️ **Fallback Strategy**

### **Option 1: Smart Fallback (Recommended)**
```python
async def transcribe_audio(self, audio_data):
    try:
        # Try Deepgram first
        return await self.deepgram_service.transcribe(audio_data)
    except Exception as e:
        logging.warning(f"Deepgram failed: {e}, falling back to Sarvam")
        # Fallback to Sarvam
        return await self.sarvam_service.transcribe(audio_data)
```

### **Option 2: Config-Based Selection**
```python
# Use provider specified in config
if config.AUDIO_STT_PROVIDER == "deepgram":
    use Deepgram
elif config.AUDIO_STT_PROVIDER == "sarvam":
    use Sarvam
```

### **Option 3: Keep Both Available**
```python
# Expose both services
self.deepgram_stt = DeepgramSTTService()
self.elevenlabs_tts = ElevenLabsService()
self.sarvam_service = SarvamService()  # Backup

# Use primary, fallback to secondary
```

---

## 🧪 **Testing Plan**

### **Test 1: STT Accuracy**
```python
# Test Deepgram transcription
audio_file = "test_audio.wav"
result = await deepgram_service.transcribe(audio_file)
assert result.text == "expected transcription"
assert result.confidence > 0.9
```

### **Test 2: TTS Quality**
```python
# Test ElevenLabs audio generation
text = "Hello, this is a test"
audio = await elevenlabs_service.generate_audio(text)
assert len(audio) > 0
assert audio.format == "mp3"
```

### **Test 3: Real-time Performance**
```python
# Measure latency
import time

start = time.time()
transcript = await deepgram_service.transcribe_stream(audio_chunks)
stt_latency = time.time() - start

start = time.time()
audio = await elevenlabs_service.tts_stream(text)
tts_latency = time.time() - start

assert stt_latency < 0.5  # < 500ms
assert tts_latency < 0.5  # < 500ms
```

### **Test 4: Barge-in**
```python
# Test interruption handling
async with conversation:
    await conversation.start_speaking()  # Agent speaks
    await conversation.user_interrupts()  # User interrupts
    assert conversation.agent_stopped == True
    assert conversation.queue_cleared == True
```

---

## 📊 **Performance Benchmarks**

### **Expected Improvements:**
```
Metric                Before (Sarvam)    After (Deepgram+ElevenLabs)
---------------------------------------------------------------------
STT First Result      1200ms             250ms ✅ (-950ms, 79% faster)
TTS First Chunk       800ms              300ms ✅ (-500ms, 62% faster)
Total RTT             2000ms             550ms ✅ (-1450ms, 72% faster)
Voice Quality         7/10               9/10 ✅ (+2 points)
Barge-in Support      No                 Yes ✅
VAD Accuracy          N/A                95%+ ✅
```

---

## 💰 **Cost Considerations**

### **Deepgram Pricing:**
- Pay-as-you-go: $0.0043/minute
- Growth plan: $0.0036/minute
- Free tier: $200 credit

### **ElevenLabs Pricing:**
- Free: 10,000 characters/month
- Starter: $5/month (30,000 characters)
- Creator: $22/month (100,000 characters)
- Pro: $99/month (500,000 characters)

### **Cost Comparison:**
```
Usage: 1000 voice interactions/month
Avg: 30 seconds STT + 20 seconds TTS per interaction

Deepgram: 1000 * 0.5min * $0.0043 = $2.15/month
ElevenLabs: ~50,000 chars = $5/month (Starter plan)
Total: ~$7/month

vs Sarvam: Variable pricing
```

---

## 🚦 **Migration Phases**

### **Phase 1: Setup (Day 1)**
1. Get API keys (Deepgram + ElevenLabs)
2. Add dependencies
3. Copy service files
4. Update config

### **Phase 2: Integration (Day 2-3)**
1. Modify AudioService
2. Update WebSocket handlers
3. Add event processing
4. Implement fallbacks

### **Phase 3: Testing (Day 4-5)**
1. Unit tests
2. Integration tests
3. Performance tests
4. User acceptance testing

### **Phase 4: Deployment (Day 6)**
1. Deploy to staging
2. Monitor performance
3. Deploy to production
4. Update documentation

---

## ⚠️ **Important Notes**

### **Breaking Changes:**
- WebSocket event structure changed
- Audio format requirements (PCM16 for Deepgram)
- New environment variables required

### **Backward Compatibility:**
- Keep Sarvam service as fallback
- Support both old and new event formats (during transition)
- Gradual rollout recommended

### **Security:**
- Store API keys in secrets
- Use environment variables
- Never commit keys to Git

---

## 🔗 **Resources**

- **Deepgram Docs:** https://developers.deepgram.com/
- **ElevenLabs Docs:** https://elevenlabs.io/docs/
- **Reference Implementation:** `AUM-ADMIN-B-Repo/Prof_AI/`

---

## ✅ **Success Criteria**

Migration is successful when:
- [ ] Deepgram STT works reliably
- [ ] ElevenLabs TTS quality is excellent
- [ ] Latency < 550ms total
- [ ] Barge-in works smoothly
- [ ] Fallback to Sarvam works
- [ ] All tests pass
- [ ] Production deployment stable

---

**Estimated Time:** 5-6 days  
**Complexity:** Medium  
**Risk:** Low (fallback available)  
**Impact:** High (much better UX!)
