# 🎙️ REAL-TIME VOICE FEATURES - IMPLEMENTATION GUIDE

## 🎯 **Goal: Make `start_class` Similar to Real-Time Voice Agent**

---

## 📊 **Current Status**

### **✅ What You Already Have (Working Perfectly):**

1. **Streaming TTS with ElevenLabs** ✅
   - First chunk latency tracking
   - Sub-300ms goal
   - Chunk-based delivery

2. **Audio Service with Multi-Provider Support** ✅
   - Deepgram STT service implemented
   - ElevenLabs TTS service implemented
   - Sarvam fallback

3. **WebSocket Infrastructure** ✅
   - Connection handling
   - Message routing
   - Error handling

4. **Teaching Content Generation** ✅
   - Course navigation
   - Module/subtopic selection
   - Content formatting

### **⚠️ What's Missing (vs Reference):**

1. **Real-Time STT Streaming** ❌
2. **Voice Activity Detection (VAD)** ❌
3. **Barge-in / Interruption** ❌
4. **Continuous Conversation Loop** ❌
5. **Partial Transcript Display** ❌

---

## 🚀 **Implementation Plan**

### **Phase 1: Add Real-Time STT Handlers** 🔴 **HIGH PRIORITY**

#### **Step 1.1: Add STT Message Handlers**

**File:** `websocket_server.py`

**Location:** In `ProfAIAgent.process_messages()` method (around line 234)

```python
# Add these to the message routing section:
elif message_type == "stt_stream_start":
    await self.handle_stt_stream_start(data)
elif message_type == "stt_audio_chunk":
    await self.handle_stt_audio_chunk(data)
elif message_type == "stt_stream_end":
    await self.handle_stt_stream_end(data)
```

#### **Step 1.2: Implement STT Stream Start Handler**

**File:** `websocket_server.py`

**Location:** After `handle_get_metrics()` method (around line 1118)

```python
async def handle_stt_stream_start(self, data: dict):
    """
    Start real-time STT streaming with Deepgram.
    Implements VAD and barge-in support like reference implementation.
    """
    try:
        language = data.get('language', 'auto')
        sample_rate = int(data.get('sample_rate', 16000))
        
        log(f"🎙️ Starting real-time STT for client {self.client_id}")
        
        # Check if audio service has Deepgram
        if not hasattr(self.audio_service, 'deepgram_service') or \
           not self.audio_service.deepgram_service:
            await self.websocket.send({
                "type": "stt_unavailable",
                "error": "Deepgram STT not configured. Please set DEEPGRAM_API_KEY."
            })
            return
        
        # Import DeepgramSTTService
        from services.deepgram_stt_service import DeepgramSTTService
        
        # Create new STT instance for this session
        self.stt_service = DeepgramSTTService(
            sample_rate=sample_rate,
            language_hint=None if language == 'auto' else language
        )
        
        if not self.stt_service.enabled:
            await self.websocket.send({
                "type": "stt_unavailable",
                "error": "Deepgram API key missing"
            })
            return
        
        # Start STT connection
        ok = await self.stt_service.start()
        if not ok:
            await self.websocket.send({
                "type": "stt_failed",
                "error": "Failed to connect to Deepgram STT"
            })
            return
        
        # Initialize session state for STT
        self.websocket.session_data['stt'] = self.stt_service
        self.websocket.session_data['is_speaking'] = False
        self.websocket.session_data['current_tts_task'] = None
        
        # Start event pump for processing STT events
        stt_task = asyncio.create_task(self._stt_event_pump())
        self.websocket.session_data['stt_task'] = stt_task
        
        await self.websocket.send({
            "type": "stt_ready",
            "message": "Real-time speech recognition started",
            "sample_rate": sample_rate,
            "language": language,
            "features": ["VAD", "barge_in", "partial_transcripts"]
        })
        
        log(f"✅ Real-time STT started for client {self.client_id}")
        
    except Exception as e:
        log(f"❌ Error starting STT: {e}")
        await self.websocket.send({
            "type": "error",
            "error": f"STT start failed: {str(e)}"
        })

async def _stt_event_pump(self):
    """
    Process STT events from Deepgram.
    Handles VAD, partial transcripts, and final transcripts.
    """
    try:
        stt = self.websocket.session_data.get('stt')
        if not stt:
            return
        
        log(f"🎧 STT event pump started for client {self.client_id}")
        
        async for event in stt.recv():
            etype = event.get('type')
            text = event.get('text', '')
            
            # Handle speech started (VAD)
            if etype == 'speech_started':
                log(f"🗣️ User started speaking (client {self.client_id})")
                self.websocket.session_data['is_speaking'] = True
                
                # BARGE-IN: Cancel current TTS if playing
                tts_task = self.websocket.session_data.get('current_tts_task')
                if tts_task and not tts_task.done():
                    log(f"⏹️ Interrupting TTS (barge-in) for client {self.client_id}")
                    tts_task.cancel()
                    try:
                        await self.websocket.send({
                            "type": "tts_interrupted",
                            "message": "Audio interrupted by user speech"
                        })
                    except ConnectionClosed:
                        break
                
                # Notify client
                try:
                    await self.websocket.send({
                        "type": "speech_started",
                        "message": "Listening..."
                    })
                except ConnectionClosed:
                    break
            
            # Handle utterance end (VAD)
            elif etype == 'utterance_end':
                log(f"🔇 User stopped speaking (client {self.client_id})")
                self.websocket.session_data['is_speaking'] = False
                
                try:
                    await self.websocket.send({
                        "type": "utterance_end",
                        "message": "Processing speech..."
                    })
                except ConnectionClosed:
                    break
            
            # Handle partial transcript
            elif etype == 'partial' and text:
                log(f"📝 Partial: {text[:50]}... (client {self.client_id})")
                
                try:
                    await self.websocket.send({
                        "type": "partial_transcript",
                        "text": text,
                        "is_final": False
                    })
                except ConnectionClosed:
                    break
            
            # Handle final transcript
            elif etype == 'final' and text:
                log(f"✅ Final: {text} (client {self.client_id})")
                self.websocket.session_data['is_speaking'] = False
                
                try:
                    await self.websocket.send({
                        "type": "final_transcript",
                        "text": text,
                        "is_final": True,
                        "language": event.get('language', 'en')
                    })
                except ConnectionClosed:
                    break
                
                # Process the user's speech and generate response
                await self._process_user_speech(text)
            
            # Handle closed event
            elif etype == 'closed':
                log(f"🔌 STT connection closed (client {self.client_id})")
                break
        
        log(f"🏁 STT event pump finished for client {self.client_id}")
        
    except ConnectionClosed as e:
        log_disconnection(self.client_id, e, "in STT event pump")
    except Exception as e:
        log(f"❌ Error in STT event pump (client {self.client_id}): {e}")

async def _process_user_speech(self, text: str):
    """
    Process final transcript from user speech.
    Get LLM response and generate cancelable TTS.
    """
    try:
        # Check if user is still speaking (skip if interrupted)
        if self.websocket.session_data.get('is_speaking'):
            log(f"🛑 Skipping response: user is speaking (client {self.client_id})")
            return
        
        log(f"🤖 Processing user speech: {text[:50]}... (client {self.client_id})")
        
        # Get response from chat service
        response_data = await self.chat_service.ask_question(
            text, 
            self.current_language
        )
        response_text = response_data.get('answer', '')
        
        if not response_text:
            log(f"⚠️ Empty response from chat service (client {self.client_id})")
            return
        
        # Send text response
        try:
            await self.websocket.send({
                "type": "agent_response",
                "text": response_text,
                "metadata": response_data
            })
        except ConnectionClosed:
            return
        
        # Generate cancelable TTS
        await self._generate_cancelable_tts(response_text)
        
    except Exception as e:
        log(f"❌ Error processing user speech (client {self.client_id}): {e}")
        try:
            await self.websocket.send({
                "type": "error",
                "error": f"Failed to process speech: {str(e)}"
            })
        except ConnectionClosed:
            pass

async def _generate_cancelable_tts(self, text: str):
    """
    Generate TTS that can be cancelled if user starts speaking (barge-in).
    """
    async def send_tts_response():
        try:
            # Check if user started speaking before generation
            if self.websocket.session_data.get('is_speaking'):
                log(f"🛑 Skipping TTS: user is speaking (client {self.client_id})")
                return
            
            log(f"🎙️ Starting cancelable TTS (client {self.client_id})")
            
            # Stream TTS audio
            chunk_count = 0
            async for chunk in self.audio_service.stream_audio_from_text(
                text, 
                self.current_language,
                self.websocket
            ):
                # Check if user started speaking during generation
                if self.websocket.session_data.get('is_speaking'):
                    log(f"🛑 TTS cancelled: user started speaking (client {self.client_id})")
                    return
                
                if chunk and len(chunk) > 0:
                    chunk_count += 1
                    
                    # Send audio chunk
                    import base64
                    audio_base64 = base64.b64encode(chunk).decode('utf-8')
                    
                    try:
                        await self.websocket.send({
                            "type": "audio_chunk",
                            "chunk_id": chunk_count,
                            "audio_data": audio_base64,
                            "size": len(chunk),
                            "cancelable": True
                        })
                    except ConnectionClosed:
                        return
            
            # Send completion
            try:
                await self.websocket.send({
                    "type": "audio_generation_complete",
                    "total_chunks": chunk_count,
                    "cancelable": True
                })
            except ConnectionClosed:
                pass
            
            log(f"✅ Cancelable TTS complete: {chunk_count} chunks (client {self.client_id})")
            
        except asyncio.CancelledError:
            log(f"🛑 TTS task cancelled (barge-in) for client {self.client_id}")
            try:
                await self.websocket.send({
                    "type": "tts_cancelled",
                    "message": "Audio generation cancelled"
                })
            except ConnectionClosed:
                pass
        except Exception as e:
            log(f"❌ TTS error (client {self.client_id}): {e}")
    
    # Start cancelable TTS task
    tts_task = asyncio.create_task(send_tts_response())
    self.websocket.session_data['current_tts_task'] = tts_task
    
    try:
        await tts_task
    except asyncio.CancelledError:
        log(f"🛑 TTS task cancelled externally (client {self.client_id})")
    finally:
        self.websocket.session_data['current_tts_task'] = None

async def handle_stt_audio_chunk(self, data: dict):
    """
    Receive audio chunks from client and send to Deepgram STT.
    """
    try:
        stt = self.websocket.session_data.get('stt')
        if not stt:
            return
        
        audio_base64 = data.get('audio')
        if not audio_base64:
            return
        
        # Decode audio
        import base64
        pcm_bytes = base64.b64decode(audio_base64)
        
        # Send to STT service
        await stt.send_audio_chunk(pcm_bytes)
        
    except Exception as e:
        log(f"❌ Error handling STT audio chunk (client {self.client_id}): {e}")

async def handle_stt_stream_end(self, data: dict):
    """
    Stop real-time STT streaming.
    """
    try:
        log(f"🛑 Stopping STT stream for client {self.client_id}")
        
        # Close STT service
        stt = self.websocket.session_data.get('stt')
        if stt:
            await stt.close()
            self.websocket.session_data['stt'] = None
        
        # Cancel STT task
        stt_task = self.websocket.session_data.get('stt_task')
        if stt_task and not stt_task.done():
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass
            self.websocket.session_data['stt_task'] = None
        
        await self.websocket.send({
            "type": "stt_stopped",
            "message": "Speech recognition stopped"
        })
        
        log(f"✅ STT stream stopped for client {self.client_id}")
        
    except Exception as e:
        log(f"❌ Error stopping STT stream (client {self.client_id}): {e}")
```

---

### **Phase 2: Update `start_class` for Interactive Mode** 🟡 **MEDIUM PRIORITY**

#### **Step 2.1: Add Interactive Mode Parameter**

**File:** `websocket_server.py`

**Location:** In `handle_start_class()` method (around line 495)

```python
async def handle_start_class(self, data: dict):
    """Handle class start requests with optional interactive mode."""
    request_start_time = time.time()
    
    try:
        course_id = data.get("course_id")
        module_index = data.get("module_index", 0)
        sub_topic_index = data.get("sub_topic_index", 0)
        language = data.get("language", self.current_language)
        
        # NEW: Interactive mode flag
        interactive_mode = data.get("interactive_mode", False)
        
        log(f"Starting class: course={course_id}, module={module_index}, topic={sub_topic_index}, interactive={interactive_mode}")
        
        # ... existing code for loading course and generating content ...
        
        # After sending teaching content, check mode
        if interactive_mode:
            # Start STT for interactive Q&A
            await self.websocket.send({
                "type": "interactive_mode_starting",
                "message": "Starting interactive mode - you can ask questions anytime!"
            })
            
            # Auto-start STT
            await self.handle_stt_stream_start({
                "language": language,
                "sample_rate": 16000
            })
        
        # ... rest of existing code ...
```

---

### **Phase 3: Client-Side Implementation** 🟢 **LOW PRIORITY**

#### **Step 3.1: JavaScript Client for Real-Time Audio**

**Create:** `web/realtime-voice-client.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>ProfAI - Real-Time Voice Class</title>
</head>
<body>
    <h1>ProfAI Real-Time Voice Class</h1>
    
    <div id="status">Connecting...</div>
    <div id="transcript"></div>
    <div id="response"></div>
    
    <button id="startBtn">Start Interactive Class</button>
    <button id="stopBtn" disabled>Stop</button>
    
    <script>
        let ws = null;
        let audioContext = null;
        let mediaStream = null;
        let processor = null;
        
        // Connect WebSocket
        function connect() {
            ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = () => {
                console.log('Connected');
                document.getElementById('status').textContent = 'Connected';
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
        }
        
        // Handle messages from server
        function handleMessage(data) {
            switch(data.type) {
                case 'stt_ready':
                    console.log('STT ready');
                    document.getElementById('status').textContent = 'Listening...';
                    break;
                
                case 'partial_transcript':
                    document.getElementById('transcript').textContent = 
                        'You: ' + data.text;
                    break;
                
                case 'final_transcript':
                    document.getElementById('transcript').textContent = 
                        'You (final): ' + data.text;
                    break;
                
                case 'agent_response':
                    document.getElementById('response').textContent = 
                        'Teacher: ' + data.text;
                    break;
                
                case 'audio_chunk':
                    playAudioChunk(data.audio_data);
                    break;
                
                case 'tts_interrupted':
                    console.log('Audio interrupted');
                    break;
            }
        }
        
        // Start interactive class
        async function startInteractiveClass() {
            // Request microphone
            mediaStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                } 
            });
            
            // Create audio context
            audioContext = new AudioContext({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(mediaStream);
            
            // Create processor
            processor = audioContext.createScriptProcessor(4096, 1, 1);
            processor.onaudioprocess = (e) => {
                const audioData = e.inputBuffer.getChannelData(0);
                
                // Convert to PCM16
                const pcm16 = new Int16Array(audioData.length);
                for (let i = 0; i < audioData.length; i++) {
                    pcm16[i] = Math.max(-32768, Math.min(32767, audioData[i] * 32768));
                }
                
                // Send to server
                const base64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
                ws.send(JSON.stringify({
                    type: 'stt_audio_chunk',
                    audio: base64
                }));
            };
            
            source.connect(processor);
            processor.connect(audioContext.destination);
            
            // Start STT on server
            ws.send(JSON.stringify({
                type: 'stt_stream_start',
                language: 'en-US',
                sample_rate: 16000
            }));
            
            // Start class with interactive mode
            ws.send(JSON.stringify({
                type: 'start_class',
                course_id: '1',
                module_index: 0,
                sub_topic_index: 0,
                language: 'en-IN',
                interactive_mode: true
            }));
            
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
        }
        
        // Stop
        function stop() {
            if (processor) {
                processor.disconnect();
                processor = null;
            }
            
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }
            
            if (ws) {
                ws.send(JSON.stringify({ type: 'stt_stream_end' }));
            }
            
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
        }
        
        // Play audio chunk
        function playAudioChunk(base64Audio) {
            const audioData = atob(base64Audio);
            const arrayBuffer = new ArrayBuffer(audioData.length);
            const view = new Uint8Array(arrayBuffer);
            for (let i = 0; i < audioData.length; i++) {
                view[i] = audioData.charCodeAt(i);
            }
            
            const audio = new Audio();
            const blob = new Blob([arrayBuffer], { type: 'audio/mpeg' });
            audio.src = URL.createObjectURL(blob);
            audio.play();
        }
        
        // Button handlers
        document.getElementById('startBtn').onclick = startInteractiveClass;
        document.getElementById('stopBtn').onclick = stop;
        
        // Connect on load
        connect();
    </script>
</body>
</html>
```

---

## ✅ **Testing Checklist**

### **Phase 1 Testing:**
- [ ] `stt_stream_start` message starts Deepgram connection
- [ ] `speech_started` event fires when user speaks
- [ ] `partial_transcript` shows live transcription
- [ ] `final_transcript` triggers response generation
- [ ] `utterance_end` resets speaking state

### **Phase 2 Testing:**
- [ ] Barge-in cancels TTS when user speaks
- [ ] TTS resumes after interruption
- [ ] Multiple interruptions handled correctly

### **Phase 3 Testing:**
- [ ] Client can send audio chunks
- [ ] Audio playback works
- [ ] Interactive mode starts automatically

---

## 🎯 **Result**

After implementation, your `start_class` will have:

✅ **All current features** (streaming TTS, teaching content, etc.)  
✅ **Real-time STT** (Deepgram WebSocket)  
✅ **VAD** (automatic speech detection)  
✅ **Barge-in** (interrupt teacher anytime)  
✅ **Continuous Q&A** (ask questions during class)  
✅ **Partial transcripts** (live transcription)

**Exactly like the reference real-time voice agent!** 🎉
