# ProfAI React/Tailwind Integration Guide

## Table of Contents
1. [API Documentation](#api-documentation)
2. [WebSocket Integration](#websocket-integration)
3. [3D Character Audio Integration](#3d-character-audio-integration)
4. [React Components Structure](#react-components-structure)
5. [Implementation Examples](#implementation-examples)

---

## API Documentation

### Base Configuration
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8765';
```

### 1. Course Management APIs

#### Upload PDFs and Generate Course
```http
POST /api/upload-pdfs
Content-Type: multipart/form-data
```

**Payload:**
```javascript
const formData = new FormData();
formData.append('files', file1);
formData.append('files', file2);
formData.append('course_title', 'My Course Title');
```

**Response:**
```json
{
  "message": "Course generated successfully",
  "course": {
    "course_title": "Generated Course",
    "modules": [
      {
        "week": 1,
        "title": "Module Title",
        "sub_topics": [
          {
            "title": "Topic Title",
            "content": "Topic content..."
          }
        ]
      }
    ]
  }
}
```

#### Get Available Courses
```http
GET /api/courses
```

**Response:**
```json
[
  {
    "course_id": "1",
    "course_title": "Generated Course",
    "modules": 5
  }
]
```

#### Get Course Content
```http
GET /api/course/{course_id}
```

**Response:**
```json
{
  "course_id": "1",
  "course_title": "Course Title",
  "modules": [
    {
      "week": 1,
      "title": "Module Title",
      "sub_topics": [
        {
          "title": "Topic Title",
          "content": "Detailed content..."
        }
      ]
    }
  ]
}
```

### 2. Chat & Communication APIs

#### Text-Only Chat
```http
POST /api/chat
Content-Type: application/json
```

**Payload:**
```json
{
  "message": "What is artificial intelligence?",
  "language": "en-IN"
}
```

**Response:**
```json
{
  "answer": "AI response text...",
  "sources": ["Course Content", "General Knowledge"]
}
```

#### Chat with Audio (HTTP)
```http
POST /api/chat-with-audio
Content-Type: application/json
```

**Payload:**
```json
{
  "message": "Explain machine learning",
  "language": "en-IN"
}
```

**Response:**
```json
{
  "answer": "ML explanation...",
  "sources": ["Course Content"],
  "audio": "base64_encoded_audio_data",
  "has_audio": true
}
```

#### Audio Transcription
```http
POST /api/transcribe
Content-Type: multipart/form-data
```

**Payload:**
```javascript
const formData = new FormData();
formData.append('audio_file', audioBlob);
formData.append('language', 'en-IN');
```

**Response:**
```json
{
  "transcribed_text": "Hello, how are you?"
}
```

### 3. Class Teaching APIs

#### Start Class (HTTP)
```http
POST /api/start-class
Content-Type: application/json
```

**Payload:**
```json
{
  "course_id": "1",
  "module_index": 0,
  "sub_topic_index": 0,
  "language": "en-IN",
  "content_only": false
}
```

**Response:** Audio stream (audio/mpeg) or JSON with content preview

### 4. System APIs

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "services_available": true,
  "services": {
    "chat_service": true,
    "document_service": true,
    "audio_service": true,
    "teaching_service": true
  }
}
```

---

## WebSocket Integration

### Connection Setup

```javascript
// hooks/useWebSocket.js
import { useState, useEffect, useRef, useCallback } from 'react';

export const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastMessage, setLastMessage] = useState(null);
  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url);
      setConnectionStatus('connecting');

      ws.current.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttempts.current = 0;
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      ws.current.onclose = (event) => {
        console.log('🔌 WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');

        // Auto-reconnect logic
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          setConnectionStatus('reconnecting');
          setTimeout(() => connect(), 2000 * reconnectAttempts.current);
        }
      };

      ws.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnectionStatus('error');
      };

    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionStatus('error');
    }
  }, [url]);

  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    sendMessage,
    reconnect: connect,
    disconnect
  };
};
```

### WebSocket Message Types

#### 1. Chat with Audio Streaming
```javascript
// Send message
const sendChatMessage = (message, language = 'en-IN') => {
  const payload = {
    type: 'chat_with_audio',
    message: message,
    language: language,
    request_id: `chat_${Date.now()}`
  };
  sendMessage(payload);
};

// Handle responses
const handleWebSocketMessage = (data) => {
  switch (data.type) {
    case 'connection_ready':
      console.log('AI Assistant ready:', data.services);
      break;
    
    case 'processing_started':
      setStatus('AI is thinking...');
      break;
    
    case 'text_response':
      addMessage(data.text, 'ai', data.metadata?.sources);
      break;
    
    case 'audio_chunk':
      handleAudioChunk(data);
      break;
    
    case 'audio_generation_complete':
      handleAudioComplete(data);
      break;
    
    case 'error':
      console.error('WebSocket error:', data.error);
      setStatus(`Error: ${data.error}`);
      break;
  }
};
```

#### 2. Class Teaching
```javascript
const startClass = (courseId, moduleIndex, subTopicIndex, language = 'en-IN') => {
  const payload = {
    type: 'start_class',
    course_id: courseId,
    module_index: moduleIndex,
    sub_topic_index: subTopicIndex,
    language: language,
    request_id: `class_${Date.now()}`
  };
  sendMessage(payload);
};
```

#### 3. Voice Transcription
```javascript
const transcribeAudio = (audioBlob, language = 'en-IN') => {
  const reader = new FileReader();
  reader.onload = () => {
    const base64Audio = reader.result.split(',')[1];
    const payload = {
      type: 'transcribe_audio',
      audio_data: base64Audio,
      language: language,
      request_id: `voice_${Date.now()}`
    };
    sendMessage(payload);
  };
  reader.readAsDataURL(audioBlob);
};
```

---

## 3D Character Audio Integration

### Challenge: Converting MP3 Chunks to WAV for 3D Character

The WebSocket streams audio in MP3 format as base64 chunks, but your 3D character module requires WAV format. Here's the solution:

### Audio Processing Hook

```javascript
// hooks/useAudioProcessor.js
import { useState, useRef, useCallback } from 'react';

export const useAudioProcessor = () => {
  const [audioQueue, setAudioQueue] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const audioContext = useRef(null);
  const currentAudio = useRef(null);

  // Initialize Web Audio API
  const initAudioContext = useCallback(() => {
    if (!audioContext.current) {
      audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext.current;
  }, []);

  // Convert MP3 base64 chunk to WAV
  const convertMp3ToWav = useCallback(async (base64Mp3) => {
    try {
      const context = initAudioContext();
      
      // Decode base64 to array buffer
      const binaryString = atob(base64Mp3);
      const arrayBuffer = new ArrayBuffer(binaryString.length);
      const uint8Array = new Uint8Array(arrayBuffer);
      
      for (let i = 0; i < binaryString.length; i++) {
        uint8Array[i] = binaryString.charCodeAt(i);
      }

      // Decode MP3 audio data
      const audioBuffer = await context.decodeAudioData(arrayBuffer);
      
      // Convert to WAV format
      const wavBuffer = audioBufferToWav(audioBuffer);
      
      return {
        wavBuffer,
        audioBuffer,
        duration: audioBuffer.duration,
        sampleRate: audioBuffer.sampleRate
      };
      
    } catch (error) {
      console.error('Error converting MP3 to WAV:', error);
      return null;
    }
  }, [initAudioContext]);

  // Audio buffer to WAV conversion
  const audioBufferToWav = (audioBuffer) => {
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const bytesPerSample = bitDepth / 8;
    const blockAlign = numberOfChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = audioBuffer.length * blockAlign;
    const bufferSize = 44 + dataSize;

    const arrayBuffer = new ArrayBuffer(bufferSize);
    const view = new DataView(arrayBuffer);

    // WAV header
    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, bufferSize - 8, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numberOfChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataSize, true);

    // Convert audio data
    let offset = 44;
    for (let channel = 0; channel < numberOfChannels; channel++) {
      const channelData = audioBuffer.getChannelData(channel);
      for (let i = 0; i < channelData.length; i++) {
        const sample = Math.max(-1, Math.min(1, channelData[i]));
        view.setInt16(offset, sample * 0x7FFF, true);
        offset += 2;
      }
    }

    return arrayBuffer;
  };

  // Process audio chunk for 3D character
  const processAudioChunk = useCallback(async (chunkData) => {
    try {
      const { audio_data, chunk_id, size } = chunkData;
      
      // Convert MP3 to WAV
      const wavData = await convertMp3ToWav(audio_data);
      
      if (wavData) {
        // Add to queue with metadata
        const processedChunk = {
          id: chunk_id,
          wavBuffer: wavData.wavBuffer,
          audioBuffer: wavData.audioBuffer,
          duration: wavData.duration,
          sampleRate: wavData.sampleRate,
          originalSize: size,
          timestamp: Date.now()
        };

        setAudioQueue(prev => [...prev, processedChunk]);
        return processedChunk;
      }
      
      return null;
    } catch (error) {
      console.error('Error processing audio chunk:', error);
      return null;
    }
  }, [convertMp3ToWav]);

  // Play next chunk for 3D character
  const playNextChunk = useCallback(async (characterAudioModule) => {
    if (audioQueue.length === 0 || isProcessing) return;

    setIsProcessing(true);
    const chunk = audioQueue[0];
    setAudioQueue(prev => prev.slice(1));

    try {
      // Create blob URL for 3D character module
      const wavBlob = new Blob([chunk.wavBuffer], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(wavBlob);

      // Play through 3D character module
      await characterAudioModule.playAudio(audioUrl, {
        duration: chunk.duration,
        sampleRate: chunk.sampleRate,
        onComplete: () => {
          URL.revokeObjectURL(audioUrl);
          setIsProcessing(false);
          // Automatically play next chunk
          if (audioQueue.length > 0) {
            setTimeout(() => playNextChunk(characterAudioModule), 50);
          }
        },
        onError: (error) => {
          console.error('3D character audio error:', error);
          URL.revokeObjectURL(audioUrl);
          setIsProcessing(false);
        }
      });

    } catch (error) {
      console.error('Error playing audio chunk:', error);
      setIsProcessing(false);
    }
  }, [audioQueue, isProcessing]);

  // Clear audio queue
  const clearQueue = useCallback(() => {
    setAudioQueue([]);
    setIsProcessing(false);
    if (currentAudio.current) {
      currentAudio.current.pause();
      currentAudio.current = null;
    }
  }, []);

  return {
    audioQueue,
    isProcessing,
    processAudioChunk,
    playNextChunk,
    clearQueue,
    queueLength: audioQueue.length
  };
};
```

### 3D Character Integration Component

```javascript
// components/Character3D.jsx
import React, { useRef, useEffect, useState } from 'react';
import { useAudioProcessor } from '../hooks/useAudioProcessor';

const Character3D = ({ 
  characterModule, // Your 3D character module
  onAudioChunk,    // WebSocket audio chunk handler
  isListening = false 
}) => {
  const characterRef = useRef(null);
  const [isCharacterReady, setIsCharacterReady] = useState(false);
  const { 
    processAudioChunk, 
    playNextChunk, 
    clearQueue, 
    queueLength,
    isProcessing 
  } = useAudioProcessor();

  // Initialize 3D character
  useEffect(() => {
    if (characterRef.current && characterModule) {
      characterModule.init(characterRef.current)
        .then(() => {
          setIsCharacterReady(true);
          console.log('3D Character initialized');
        })
        .catch(error => {
          console.error('Failed to initialize 3D character:', error);
        });
    }
  }, [characterModule]);

  // Handle incoming audio chunks
  useEffect(() => {
    if (onAudioChunk && isCharacterReady) {
      const handleChunk = async (chunkData) => {
        const processedChunk = await processAudioChunk(chunkData);
        if (processedChunk && !isProcessing) {
          playNextChunk(characterModule);
        }
      };

      // Set up the audio chunk handler
      onAudioChunk(handleChunk);
    }
  }, [onAudioChunk, isCharacterReady, processAudioChunk, playNextChunk, isProcessing]);

  // Auto-play queued chunks
  useEffect(() => {
    if (queueLength > 0 && !isProcessing && isCharacterReady) {
      playNextChunk(characterModule);
    }
  }, [queueLength, isProcessing, isCharacterReady, playNextChunk, characterModule]);

  const handleStopAudio = () => {
    clearQueue();
    if (characterModule && characterModule.stopAudio) {
      characterModule.stopAudio();
    }
  };

  return (
    <div className="relative w-full h-full">
      {/* 3D Character Container */}
      <div 
        ref={characterRef} 
        className="w-full h-full"
        style={{ minHeight: '400px' }}
      />
      
      {/* Character Status Overlay */}
      <div className="absolute top-4 right-4 bg-black bg-opacity-50 text-white px-3 py-1 rounded">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            isCharacterReady ? 'bg-green-500' : 'bg-red-500'
          }`} />
          <span className="text-sm">
            {isCharacterReady ? 'Ready' : 'Loading...'}
          </span>
        </div>
        
        {queueLength > 0 && (
          <div className="text-xs mt-1">
            Queue: {queueLength} chunks
          </div>
        )}
        
        {isProcessing && (
          <div className="text-xs mt-1 text-yellow-300">
            Speaking...
          </div>
        )}
      </div>

      {/* Audio Controls */}
      <div className="absolute bottom-4 left-4 flex space-x-2">
        <button
          onClick={handleStopAudio}
          disabled={!isProcessing && queueLength === 0}
          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
        >
          Stop Audio
        </button>
        
        <div className="px-3 py-1 bg-gray-800 text-white rounded text-sm">
          {isListening ? '🎤 Listening' : '🔇 Idle'}
        </div>
      </div>
    </div>
  );
};

export default Character3D;
```

---

## API Usage Examples in React Components

### 1. Course Management API Usage

#### CourseManager Component
```javascript
// components/CourseManager.jsx
import React, { useState, useEffect } from 'react';

const CourseManager = ({ onCourseSelect, onStartClass, isConnected }) => {
  const [courses, setCourses] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // API Usage: Get Available Courses
  const loadCourses = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/courses`);
      const coursesData = await response.json();
      setCourses(coursesData);
      
      if (coursesData.length > 0) {
        await loadCourseDetails(coursesData[0].course_id);
      }
    } catch (error) {
      console.error('Error loading courses:', error);
    } finally {
      setLoading(false);
    }
  };

  // API Usage: Get Course Content
  const loadCourseDetails = async (courseId) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/course/${courseId}`);
      const courseDetails = await response.json();
      setSelectedCourse(courseDetails);
      onCourseSelect(courseDetails);
    } catch (error) {
      console.error('Error loading course details:', error);
    }
  };

  // API Usage: Upload PDFs and Generate Course
  const handleFileUpload = async (files, courseTitle) => {
    try {
      setLoading(true);
      setUploadProgress(0);

      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      if (courseTitle) formData.append('course_title', courseTitle);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/upload-pdfs`, {
        method: 'POST',
        body: formData,
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        }
      });

      if (!response.ok) throw new Error('Upload failed');

      const result = await response.json();
      console.log('Course generated:', result.course);
      
      // Reload courses after successful upload
      await loadCourses();
      
    } catch (error) {
      console.error('Error uploading files:', error);
    } finally {
      setLoading(false);
      setUploadProgress(0);
    }
  };

  useEffect(() => {
    loadCourses();
  }, []);

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-4">Course Manager</h2>
      
      {/* File Upload Section */}
      <div className="mb-6">
        <FileUploader 
          onUpload={handleFileUpload}
          loading={loading}
          progress={uploadProgress}
        />
      </div>

      {/* Course List */}
      {loading ? (
        <div>Loading courses...</div>
      ) : (
        <CourseList 
          courses={courses}
          selectedCourse={selectedCourse}
          onCourseSelect={loadCourseDetails}
          onStartClass={onStartClass}
          isConnected={isConnected}
        />
      )}
    </div>
  );
};
```

### 2. Chat API Usage

#### ChatInterface Component
```javascript
// components/ChatInterface.jsx
import React, { useState, useRef } from 'react';
import VoiceRecorder from './VoiceRecorder';

const ChatInterface = ({ 
  messages, 
  isLoading, 
  isConnected, 
  onSendMessage,
  onTranscribeAudio 
}) => {
  const [inputText, setInputText] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('en-IN');
  const [useHttpChat, setUseHttpChat] = useState(false); // Toggle between WebSocket and HTTP

  // API Usage: Text-Only Chat (HTTP)
  const sendHttpChatMessage = async (message) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          language: selectedLanguage
        })
      });

      if (!response.ok) throw new Error('Chat request failed');

      const data = await response.json();
      return {
        text: data.answer || data.response,
        sources: data.sources || []
      };
    } catch (error) {
      console.error('HTTP Chat error:', error);
      throw error;
    }
  };

  // API Usage: Chat with Audio (HTTP)
  const sendHttpChatWithAudio = async (message) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat-with-audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          language: selectedLanguage
        })
      });

      if (!response.ok) throw new Error('Chat with audio request failed');

      const data = await response.json();
      return {
        text: data.answer || data.response,
        sources: data.sources || [],
        audio: data.audio,
        hasAudio: data.has_audio
      };
    } catch (error) {
      console.error('HTTP Chat with Audio error:', error);
      throw error;
    }
  };

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const message = inputText.trim();
    setInputText('');

    if (useHttpChat) {
      // Use HTTP API
      try {
        const response = await sendHttpChatWithAudio(message);
        // Handle response (add to messages, play audio if available)
        if (response.hasAudio && response.audio) {
          playAudioFromBase64(response.audio);
        }
      } catch (error) {
        console.error('Failed to send HTTP message:', error);
      }
    } else {
      // Use WebSocket (preferred for real-time streaming)
      onSendMessage(message, selectedLanguage);
    }
  };

  const playAudioFromBase64 = (audioBase64) => {
    try {
      const audioBytes = atob(audioBase64);
      const audioArray = new Uint8Array(audioBytes.length);
      for (let i = 0; i < audioBytes.length; i++) {
        audioArray[i] = audioBytes.charCodeAt(i);
      }
      const audioBlob = new Blob([audioArray], { type: 'audio/mpeg' });
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.play();
      audio.onended = () => URL.revokeObjectURL(audioUrl);
    } catch (error) {
      console.error('Error playing audio:', error);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map(message => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>

      {/* Input Section */}
      <div className="p-4 border-t">
        {/* Language Selector */}
        <select 
          value={selectedLanguage}
          onChange={(e) => setSelectedLanguage(e.target.value)}
          className="mb-2 p-2 border rounded"
        >
          <option value="en-IN">English</option>
          <option value="hi-IN">Hindi</option>
          <option value="ta-IN">Tamil</option>
          {/* Add other languages */}
        </select>

        {/* API Method Toggle */}
        <div className="mb-2">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={useHttpChat}
              onChange={(e) => setUseHttpChat(e.target.checked)}
              className="mr-2"
            />
            Use HTTP API (instead of WebSocket)
          </label>
        </div>

        {/* Text Input */}
        <div className="flex gap-2">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 p-2 border rounded resize-none"
            rows="2"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading || (!isConnected && !useHttpChat)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>

        {/* Voice Recorder */}
        <VoiceRecorder
          onTranscribe={onTranscribeAudio}
          language={selectedLanguage}
          disabled={isLoading}
        />
      </div>
    </div>
  );
};
```

### 3. Voice Transcription API Usage

#### VoiceRecorder Component
```javascript
// components/VoiceRecorder.jsx
import React, { useState, useRef } from 'react';

const VoiceRecorder = ({ onTranscribe, language, disabled, useWebSocket = true }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // API Usage: Audio Transcription (HTTP)
  const transcribeAudioHttp = async (audioBlob) => {
    try {
      setIsProcessing(true);
      
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.webm');
      formData.append('language', language);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/transcribe`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('Transcription failed');

      const data = await response.json();
      return data.transcribed_text;
      
    } catch (error) {
      console.error('HTTP Transcription error:', error);
      throw error;
    } finally {
      setIsProcessing(false);
    }
  };

  // WebSocket Transcription (via parent component)
  const transcribeAudioWebSocket = (audioBlob) => {
    setIsProcessing(true);
    
    const reader = new FileReader();
    reader.onload = () => {
      const base64Audio = reader.result.split(',')[1];
      onTranscribe(base64Audio, language);
    };
    reader.readAsDataURL(audioBlob);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };
      
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        try {
          if (useWebSocket) {
            transcribeAudioWebSocket(audioBlob);
          } else {
            const transcribedText = await transcribeAudioHttp(audioBlob);
            onTranscribe(transcribedText);
          }
        } catch (error) {
          console.error('Transcription failed:', error);
          setIsProcessing(false);
        }
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorderRef.current.start();
      setIsRecording(true);
      
    } catch (error) {
      console.error('Error starting recording:', error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="flex items-center gap-2 mt-2">
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled || isProcessing}
        className={`px-4 py-2 rounded font-medium ${
          isRecording 
            ? 'bg-red-600 text-white hover:bg-red-700' 
            : 'bg-green-600 text-white hover:bg-green-700'
        } disabled:opacity-50`}
      >
        {isRecording ? '🛑 Stop Recording' : '🎤 Start Recording'}
      </button>
      
      {isProcessing && (
        <span className="text-sm text-gray-600">Processing audio...</span>
      )}
      
      <div className="text-xs text-gray-500">
        Method: {useWebSocket ? 'WebSocket' : 'HTTP API'}
      </div>
    </div>
  );
};
```

### 4. Class Teaching API Usage

#### ClassController Component
```javascript
// components/ClassController.jsx
import React, { useState } from 'react';

const ClassController = ({ 
  currentCourse, 
  onStartClass, 
  isConnected, 
  useWebSocket = true 
}) => {
  const [selectedModule, setSelectedModule] = useState(0);
  const [selectedSubTopic, setSelectedSubTopic] = useState(0);
  const [language, setLanguage] = useState('en-IN');
  const [isLoading, setIsLoading] = useState(false);
  const [contentPreview, setContentPreview] = useState(null);

  // API Usage: Start Class (HTTP) - Content Preview Only
  const getClassContentPreview = async () => {
    try {
      setIsLoading(true);
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/start-class`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: currentCourse.course_id,
          module_index: selectedModule,
          sub_topic_index: selectedSubTopic,
          language: language,
          content_only: true // Get preview only
        })
      });

      if (!response.ok) throw new Error('Failed to get content preview');

      const data = await response.json();
      setContentPreview(data);
      
    } catch (error) {
      console.error('Error getting content preview:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // API Usage: Start Class (HTTP) - Full Audio Generation
  const startClassHttp = async () => {
    try {
      setIsLoading(true);
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/start-class`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: currentCourse.course_id,
          module_index: selectedModule,
          sub_topic_index: selectedSubTopic,
          language: language,
          content_only: false
        })
      });

      if (!response.ok) throw new Error('Failed to start class');

      // Response is audio stream
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      
      // Play the audio
      const audio = new Audio(audioUrl);
      audio.play();
      audio.onended = () => URL.revokeObjectURL(audioUrl);
      
    } catch (error) {
      console.error('Error starting class:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartClass = () => {
    if (useWebSocket && isConnected) {
      // Use WebSocket for real-time streaming
      onStartClass(selectedModule, selectedSubTopic, language);
    } else {
      // Use HTTP API for single audio file
      startClassHttp();
    }
  };

  if (!currentCourse) {
    return <div>No course selected</div>;
  }

  return (
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">Class Controller</h3>
      
      {/* Module Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Module:</label>
        <select
          value={selectedModule}
          onChange={(e) => setSelectedModule(parseInt(e.target.value))}
          className="w-full p-2 border rounded"
        >
          {currentCourse.modules.map((module, index) => (
            <option key={index} value={index}>
              Week {module.week}: {module.title}
            </option>
          ))}
        </select>
      </div>

      {/* Sub-topic Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Sub-topic:</label>
        <select
          value={selectedSubTopic}
          onChange={(e) => setSelectedSubTopic(parseInt(e.target.value))}
          className="w-full p-2 border rounded"
        >
          {currentCourse.modules[selectedModule]?.sub_topics.map((topic, index) => (
            <option key={index} value={index}>
              {topic.title}
            </option>
          ))}
        </select>
      </div>

      {/* Language Selection */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Language:</label>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="w-full p-2 border rounded"
        >
          <option value="en-IN">English</option>
          <option value="hi-IN">Hindi</option>
          <option value="ta-IN">Tamil</option>
          {/* Add other languages */}
        </select>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={getClassContentPreview}
          disabled={isLoading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Preview Content
        </button>
        
        <button
          onClick={handleStartClass}
          disabled={isLoading || (!isConnected && useWebSocket)}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
        >
          {useWebSocket ? 'Start Class (WebSocket)' : 'Start Class (HTTP)'}
        </button>
      </div>

      {/* Content Preview */}
      {contentPreview && (
        <div className="mt-4 p-4 bg-gray-50 rounded">
          <h4 className="font-medium mb-2">Content Preview:</h4>
          <p className="text-sm text-gray-700 mb-2">
            <strong>Module:</strong> {contentPreview.module_title}
          </p>
          <p className="text-sm text-gray-700 mb-2">
            <strong>Topic:</strong> {contentPreview.sub_topic_title}
          </p>
          <p className="text-sm text-gray-700 mb-2">
            <strong>Length:</strong> {contentPreview.full_content_length} characters
          </p>
          <div className="text-sm text-gray-600 bg-white p-2 rounded border">
            {contentPreview.content_preview}
          </div>
        </div>
      )}

      {/* Method Indicator */}
      <div className="mt-4 text-xs text-gray-500">
        Using: {useWebSocket ? 'WebSocket (Real-time streaming)' : 'HTTP API (Single audio file)'}
        {useWebSocket && !isConnected && (
          <span className="text-red-500 ml-2">⚠️ WebSocket not connected</span>
        )}
      </div>
    </div>
  );
};
```

### 5. Health Check API Usage

#### SystemStatus Component
```javascript
// components/SystemStatus.jsx
import React, { useState, useEffect } from 'react';

const SystemStatus = () => {
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastCheck, setLastCheck] = useState(null);

  // API Usage: Health Check
  const checkSystemHealth = async () => {
    try {
      setLoading(true);
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/health`);
      const data = await response.json();
      
      setHealthStatus(data);
      setLastCheck(new Date());
      
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus({
        status: 'error',
        services_available: false,
        services: {}
      });
    } finally {
      setLoading(false);
    }
  };

  // Auto-check every 30 seconds
  useEffect(() => {
    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-green-600';
      case 'error': return 'text-red-600';
      default: return 'text-yellow-600';
    }
  };

  const getServiceStatus = (available) => {
    return available ? '✅ Available' : '❌ Unavailable';
  };

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">System Status</h3>
        <button
          onClick={checkSystemHealth}
          disabled={loading}
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Checking...' : 'Refresh'}
        </button>
      </div>

      {healthStatus ? (
        <div>
          <div className={`text-lg font-medium mb-2 ${getStatusColor(healthStatus.status)}`}>
            Status: {healthStatus.status.toUpperCase()}
          </div>
          
          <div className="mb-4">
            <strong>Services Available:</strong> {healthStatus.services_available ? 'Yes' : 'No'}
          </div>

          <div className="space-y-2">
            <h4 className="font-medium">Individual Services:</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>Chat Service: {getServiceStatus(healthStatus.services.chat_service)}</div>
              <div>Audio Service: {getServiceStatus(healthStatus.services.audio_service)}</div>
              <div>Document Service: {getServiceStatus(healthStatus.services.document_service)}</div>
              <div>Teaching Service: {getServiceStatus(healthStatus.services.teaching_service)}</div>
            </div>
          </div>

          {lastCheck && (
            <div className="mt-4 text-xs text-gray-500">
              Last checked: {lastCheck.toLocaleTimeString()}
            </div>
          )}
        </div>
      ) : (
        <div>Loading system status...</div>
      )}
    </div>
  );
};
```

### 6. Complete API Service Layer

#### API Service Utility
```javascript
// services/api.js
class ProfAIAPI {
  constructor(baseUrl = process.env.REACT_APP_API_URL) {
    this.baseUrl = baseUrl;
  }

  // Course Management APIs
  async uploadPDFs(files, courseTitle) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    if (courseTitle) formData.append('course_title', courseTitle);

    const response = await fetch(`${this.baseUrl}/api/upload-pdfs`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Upload failed');
    return response.json();
  }

  async getCourses() {
    const response = await fetch(`${this.baseUrl}/api/courses`);
    if (!response.ok) throw new Error('Failed to get courses');
    return response.json();
  }

  async getCourseContent(courseId) {
    const response = await fetch(`${this.baseUrl}/api/course/${courseId}`);
    if (!response.ok) throw new Error('Failed to get course content');
    return response.json();
  }

  // Chat APIs
  async sendChatMessage(message, language = 'en-IN') {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, language })
    });

    if (!response.ok) throw new Error('Chat request failed');
    return response.json();
  }

  async sendChatWithAudio(message, language = 'en-IN') {
    const response = await fetch(`${this.baseUrl}/api/chat-with-audio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, language })
    });

    if (!response.ok) throw new Error('Chat with audio request failed');
    return response.json();
  }

  async transcribeAudio(audioBlob, language = 'en-IN') {
    const formData = new FormData();
    formData.append('audio_file', audioBlob);
    formData.append('language', language);

    const response = await fetch(`${this.baseUrl}/api/transcribe`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Transcription failed');
    return response.json();
  }

  // Class Teaching APIs
  async startClass(courseId, moduleIndex, subTopicIndex, language = 'en-IN', contentOnly = false) {
    const response = await fetch(`${this.baseUrl}/api/start-class`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        course_id: courseId,
        module_index: moduleIndex,
        sub_topic_index: subTopicIndex,
        language,
        content_only: contentOnly
      })
    });

    if (!response.ok) throw new Error('Failed to start class');
    
    if (contentOnly) {
      return response.json();
    } else {
      return response.blob(); // Audio stream
    }
  }

  // System APIs
  async checkHealth() {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) throw new Error('Health check failed');
    return response.json();
  }
}

export default new ProfAIAPI();
```

---

## React Components Structure

### Main App Structure
```
src/
├── components/
│   ├── Character3D.jsx
│   ├── ChatInterface.jsx
│   ├── CourseManager.jsx
│   ├── VoiceRecorder.jsx
│   └── ConnectionStatus.jsx
├── hooks/
│   ├── useWebSocket.js
│   ├── useAudioProcessor.js
│   ├── useVoiceRecorder.js
│   └── useProfAI.js
├── services/
│   ├── api.js
│   └── websocket.js
├── utils/
│   ├── audioUtils.js
│   └── constants.js
└── App.jsx
```

### Main ProfAI Hook

```javascript
// hooks/useProfAI.js
import { useState, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { useAudioProcessor } from './useAudioProcessor';

export const useProfAI = (wsUrl) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentCourse, setCurrentCourse] = useState(null);
  
  const { 
    isConnected, 
    connectionStatus, 
    lastMessage, 
    sendMessage 
  } = useWebSocket(wsUrl);
  
  const {
    processAudioChunk,
    playNextChunk,
    clearQueue,
    queueLength
  } = useAudioProcessor();

  // Handle WebSocket messages
  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'text_response':
        setMessages(prev => [...prev, {
          id: Date.now(),
          text: data.text,
          sender: 'ai',
          sources: data.metadata?.sources,
          timestamp: new Date()
        }]);
        setIsLoading(false);
        break;
        
      case 'audio_chunk':
        processAudioChunk(data);
        break;
        
      case 'processing_started':
        setIsLoading(true);
        break;
        
      case 'audio_generation_complete':
        setIsLoading(false);
        break;
        
      case 'error':
        console.error('ProfAI Error:', data.error);
        setIsLoading(false);
        break;
    }
  }, [processAudioChunk]);

  // Send chat message
  const sendChatMessage = useCallback((message, language = 'en-IN') => {
    if (!isConnected) return false;
    
    setMessages(prev => [...prev, {
      id: Date.now(),
      text: message,
      sender: 'user',
      timestamp: new Date()
    }]);
    
    setIsLoading(true);
    clearQueue(); // Clear any existing audio
    
    return sendMessage({
      type: 'chat_with_audio',
      message,
      language,
      request_id: `chat_${Date.now()}`
    });
  }, [isConnected, sendMessage, clearQueue]);

  // Start class
  const startClass = useCallback((moduleIndex, subTopicIndex, language = 'en-IN') => {
    if (!isConnected || !currentCourse) return false;
    
    setIsLoading(true);
    clearQueue();
    
    return sendMessage({
      type: 'start_class',
      course_id: currentCourse.course_id,
      module_index: moduleIndex,
      sub_topic_index: subTopicIndex,
      language,
      request_id: `class_${Date.now()}`
    });
  }, [isConnected, currentCourse, sendMessage, clearQueue]);

  return {
    // Connection
    isConnected,
    connectionStatus,
    
    // Messages
    messages,
    isLoading,
    sendChatMessage,
    
    // Course
    currentCourse,
    setCurrentCourse,
    startClass,
    
    // Audio
    audioQueueLength: queueLength,
    clearAudioQueue: clearQueue,
    onAudioChunk: processAudioChunk,
    playNextAudioChunk: playNextChunk,
    
    // WebSocket message handler
    handleMessage,
    lastMessage
  };
};
```

### Main App Component

```javascript
// App.jsx
import React, { useEffect } from 'react';
import Character3D from './components/Character3D';
import ChatInterface from './components/ChatInterface';
import CourseManager from './components/CourseManager';
import ConnectionStatus from './components/ConnectionStatus';
import { useProfAI } from './hooks/useProfAI';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8765';

function App() {
  const {
    isConnected,
    connectionStatus,
    messages,
    isLoading,
    sendChatMessage,
    currentCourse,
    setCurrentCourse,
    startClass,
    audioQueueLength,
    clearAudioQueue,
    onAudioChunk,
    playNextAudioChunk,
    handleMessage,
    lastMessage
  } = useProfAI(WS_URL);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      handleMessage(lastMessage);
    }
  }, [lastMessage, handleMessage]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-800">ProfAI</h1>
            <ConnectionStatus 
              isConnected={isConnected}
              status={connectionStatus}
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex h-screen">
        {/* Left Sidebar - Course Manager */}
        <div className="w-80 bg-white shadow-lg">
          <CourseManager 
            currentCourse={currentCourse}
            onCourseSelect={setCurrentCourse}
            onStartClass={startClass}
            isConnected={isConnected}
          />
        </div>

        {/* Center - 3D Character */}
        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-2xl h-96">
            <Character3D
              characterModule={window.characterModule} // Your 3D character module
              onAudioChunk={onAudioChunk}
              isListening={isLoading}
            />
          </div>
        </div>

        {/* Right Sidebar - Chat Interface */}
        <div className="w-96 bg-white shadow-lg">
          <ChatInterface
            messages={messages}
            isLoading={isLoading}
            isConnected={isConnected}
            onSendMessage={sendChatMessage}
            audioQueueLength={audioQueueLength}
            onClearAudio={clearAudioQueue}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
```

---

## Implementation Examples

### Environment Variables (.env)
```env
REACT_APP_API_URL=http://localhost:5001
REACT_APP_WS_URL=ws://localhost:8765
REACT_APP_SUPPORTED_LANGUAGES=en-IN,hi-IN,ta-IN,te-IN,bn-IN,gu-IN,kn-IN,ml-IN,mr-IN,pa-IN,ur-IN
```

### Package.json Dependencies
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "tailwindcss": "^3.3.0",
    "@headlessui/react": "^1.7.0",
    "@heroicons/react": "^2.0.0"
  }
}
```

### Tailwind Config
```javascript
// tailwind.config.js
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'profai-blue': '#667eea',
        'profai-purple': '#764ba2',
      }
    },
  },
  plugins: [],
}
```

This comprehensive guide provides everything you need to integrate ProfAI with React/Tailwind, including proper WebSocket handling and 3D character audio conversion from MP3 chunks to WAV format for seamless real-time audio streaming.