# ProfAI API - Swagger Documentation Guide for UI Developers

## 🚀 **Quick Start**

### **Access Swagger UI**

Once the backend server is running, access the interactive API documentation at:

```
http://localhost:5003/docs
```

**Alternative (ReDoc):**
```
http://localhost:5003/redoc
```

---

## 📚 **API Documentation Overview**

All API endpoints are now fully documented with:
- ✅ **Request/Response schemas** - See exact payload structure
- ✅ **Example payloads** - Copy-paste ready JSON examples
- ✅ **Field descriptions** - Understand what each field does
- ✅ **Validation rules** - Know field requirements (required/optional, min/max, types)
- ✅ **Response codes** - All possible HTTP status codes
- ✅ **Tags & grouping** - Endpoints organized by category

---

## 🏷️ **API Endpoint Categories (Tags)**

### **1. Session Management** 
Manage user sessions and conversation history.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/check` | GET | Check if user has active session |
| `/api/session/create` | POST | Create new session for user |
| `/api/session/end` | POST | End active session |
| `/api/session/history` | GET | Get conversation history |

---

### **2. Chat**
Intelligent chat with AI assistant.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Text chat with AI (RAG + memory) |
| `/api/chat-with-audio` | POST | Chat with text + audio response |

---

### **3. Courses**
Course catalog and management.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/courses` | GET | Get all courses with metadata |

---

### **4. Admin**
Administrative dashboard and analytics.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/dashboard` | GET | Comprehensive statistics |

---

### **5. Health**
Service health and status.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |

---

## 📋 **Detailed Endpoint Documentation**

### **Session Management**

#### **1. Check Session - `GET /api/session/check`**

**Purpose:** Check if a user has an active session before starting conversation.

**Query Parameters:**
```typescript
{
  user_id: number  // Required, User ID to check
}
```

**Example Request:**
```bash
curl "http://localhost:5003/api/session/check?user_id=123"
```

**Example Response (Has Session):**
```json
{
  "has_session": true,
  "session_id": "abc-123-uuid",
  "message_count": 15,
  "last_activity": "2024-01-07T10:30:00",
  "started_at": "2024-01-07T09:00:00"
}
```

**Example Response (No Session):**
```json
{
  "has_session": false,
  "message": "No active session found for this user"
}
```

**Frontend Usage:**
```javascript
async function checkUserSession(userId) {
  const response = await fetch(`/api/session/check?user_id=${userId}`);
  const data = await response.json();
  return data.has_session ? data.session_id : null;
}
```

---

#### **2. Create Session - `POST /api/session/create`**

**Purpose:** Explicitly create a session (optional - chat endpoints auto-create).

**Request Body:**
```typescript
{
  user_id: number,           // Required
  ip_address?: string,       // Optional - for analytics
  user_agent?: string,       // Optional - browser info
  device_type?: string       // Optional - "mobile" | "desktop" | "tablet"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:5003/api/session/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "device_type": "mobile"
  }'
```

**Example Response:**
```json
{
  "session_id": "abc-123-uuid",
  "user_id": 123,
  "started_at": "2024-01-07T10:00:00",
  "message": "Session created successfully"
}
```

**Frontend Usage:**
```javascript
async function createSession(userId) {
  const response = await fetch('/api/session/create', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: userId,
      ip_address: await getUserIP(),
      user_agent: navigator.userAgent,
      device_type: getDeviceType()
    })
  });
  return await response.json();
}
```

---

#### **3. End Session - `POST /api/session/end`**

**Purpose:** End session when user logs out.

**Request Body:**
```typescript
{
  session_id: string  // Required - UUID of session to end
}
```

**Example Request:**
```bash
curl -X POST http://localhost:5003/api/session/end \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123-uuid"}'
```

**Example Response:**
```json
{
  "session_id": "abc-123-uuid",
  "message": "Session ended successfully"
}
```

**Frontend Usage:**
```javascript
async function endSession(sessionId) {
  await fetch('/api/session/end', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId})
  });
}
```

---

#### **4. Get History - `GET /api/session/history`**

**Purpose:** Retrieve past conversation messages.

**Query Parameters:**
```typescript
{
  session_id: string,  // Required - Session UUID
  limit?: number       // Optional - Max messages (default: 20)
}
```

**Example Request:**
```bash
curl "http://localhost:5003/api/session/history?session_id=abc-123&limit=50"
```

**Example Response:**
```json
{
  "session_id": "abc-123-uuid",
  "message_count": 4,
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "Hi, my name is Alice",
      "message_type": "text",
      "created_at": "2024-01-07T10:00:00"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Hello Alice! How can I help you?",
      "message_type": "text",
      "created_at": "2024-01-07T10:00:05"
    }
  ]
}
```

**Frontend Usage:**
```javascript
async function getConversationHistory(sessionId, limit = 20) {
  const response = await fetch(
    `/api/session/history?session_id=${sessionId}&limit=${limit}`
  );
  return await response.json();
}
```

---

### **Chat Endpoints**

#### **1. Text Chat - `POST /api/chat`**

**Purpose:** Send message to AI and get intelligent response with memory.

**Request Body:**
```typescript
{
  user_id: number,           // Required - User ID
  message: string,           // Required - User's question (min 1 char)
  language?: string,         // Optional - Default: "en-IN"
  ip_address?: string,       // Optional - For analytics
  user_agent?: string        // Optional - Browser info
}
```

**Example Request:**
```bash
curl -X POST http://localhost:5003/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "message": "What is robotics?",
    "language": "en-IN"
  }'
```

**Example Response:**
```json
{
  "answer": "Robotics is the interdisciplinary field that involves the design, construction, operation, and use of robots...",
  "session_id": "abc-123-uuid",
  "user_id": 123,
  "route": "course_query",
  "confidence": 0.85,
  "sources": [
    {
      "content": "Introduction to Robotics...",
      "metadata": {"course": "Robotics 101"}
    }
  ]
}
```

**Response Fields:**
- `answer`: AI-generated response text
- `session_id`: Session UUID (for tracking conversation)
- `user_id`: User ID
- `route`: Detected intent ("greeting", "general_question", "course_query")
- `confidence`: Route confidence score (0-1)
- `sources`: Retrieved documents from RAG (if course_query)

**Frontend Usage:**
```javascript
async function sendChatMessage(userId, message, language = 'en-IN') {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: userId,
      message: message,
      language: language
    })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const data = await response.json();
  
  // Store session_id for future messages
  localStorage.setItem('session_id', data.session_id);
  
  return data;
}
```

---

#### **2. Chat with Audio - `POST /api/chat-with-audio`**

**Purpose:** Get AI response as both text and audio.

**Request Body:**
```typescript
{
  user_id: number,           // Required
  message: string,           // Required
  language?: string,         // Optional - Default: "en-IN"
  ip_address?: string,       // Optional
  user_agent?: string        // Optional
}
```

**Example Request:**
```bash
curl -X POST http://localhost:5003/api/chat-with-audio \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "message": "Explain AI",
    "language": "en-IN"
  }'
```

**Example Response:**
```json
{
  "answer": "AI stands for Artificial Intelligence...",
  "audio_data": "base64_encoded_audio_string_here...",
  "session_id": "abc-123-uuid",
  "user_id": 123,
  "metadata": {
    "route": "general_question",
    "confidence": 0.92
  }
}
```

**Response Fields:**
- `answer`: Text response
- `audio_data`: Base64-encoded MP3 audio
- `session_id`: Session UUID
- `user_id`: User ID
- `metadata`: Additional info (route, confidence, etc.)

**Frontend Usage:**
```javascript
async function sendChatWithAudio(userId, message) {
  const response = await fetch('/api/chat-with-audio', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: userId,
      message: message
    })
  });
  
  const data = await response.json();
  
  // Play audio
  const audio = new Audio(`data:audio/mp3;base64,${data.audio_data}`);
  audio.play();
  
  return data;
}
```

---

### **Course Endpoints**

#### **Get All Courses - `GET /api/courses`**

**Purpose:** Retrieve complete course catalog with all metadata.

**Example Request:**
```bash
curl http://localhost:5003/api/courses
```

**Example Response:**
```json
[
  {
    "id": 1,
    "title": "Introduction to Robotics",
    "description": "Learn robotics fundamentals",
    "level": "Beginner",
    "teacher_id": 5,
    "course_order": 1,
    "course_number": 101,
    "country": "India",
    "file_metadata": {},
    "created_by": "admin",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
]
```

**Important Fields:**
- `id`: Course ID (use this for database operations)
- `course_number`: Display-friendly course number
- `country`: Country where course is offered/localized
- `level`: "Beginner", "Intermediate", "Advanced"

**Frontend Usage:**
```javascript
async function getCourses() {
  const response = await fetch('/api/courses');
  return await response.json();
}

// Display in dropdown
function populateCourseDropdown() {
  getCourses().then(courses => {
    const select = document.getElementById('course-select');
    courses.forEach(course => {
      const option = document.createElement('option');
      option.value = course.id;
      option.text = `${course.title} (${course.country})`;
      select.add(option);
    });
  });
}
```

---

### **Admin Endpoints**

#### **Admin Dashboard - `GET /api/admin/dashboard`**

**Purpose:** Get comprehensive statistics for admin panel.

⚠️ **Authentication Required:** Protect this endpoint in production!

**Example Request:**
```bash
curl http://localhost:5003/api/admin/dashboard
```

**Example Response:**
```json
{
  "status": "success",
  "timestamp": "2024-01-07T10:00:00",
  "data": {
    "total_courses": 25,
    "total_users": 1500,
    "users_by_role": {
      "student": 1400,
      "teacher": 90,
      "admin": 10
    },
    "active_sessions_24h": 350,
    "total_messages": 12500,
    "total_enrollments": 3200,
    "paid_enrollments": 850,
    "total_purchases": 900,
    "total_revenue": 125000.00,
    "courses": [
      {
        "id": 1,
        "title": "Introduction to Robotics",
        "country": "India",
        "level": "Beginner",
        "enrollment_count": 450,
        "paid_enrollment_count": 120
      }
    ],
    "recent_users": [
      {
        "id": 1500,
        "username": "alice123",
        "email": "alice@example.com",
        "role": "student",
        "created_at": "2024-01-07T09:00:00"
      }
    ],
    "session_activity_7d": [
      {
        "date": "2024-01-07",
        "session_count": 120,
        "unique_users": 95
      }
    ]
  }
}
```

**Frontend Usage:**
```javascript
async function loadAdminDashboard() {
  const response = await fetch('/api/admin/dashboard', {
    headers: {
      'Authorization': `Bearer ${adminToken}`  // Add auth
    }
  });
  
  const {data} = await response.json();
  
  // Update dashboard UI
  document.getElementById('total-users').textContent = data.total_users;
  document.getElementById('total-revenue').textContent = `$${data.total_revenue}`;
  
  // Render charts
  renderUsersByRoleChart(data.users_by_role);
  renderSessionActivityChart(data.session_activity_7d);
  
  return data;
}
```

---

## 🔧 **Error Handling**

All endpoints return standard HTTP status codes:

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Missing required field (e.g., `user_id`) |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Internal server error |
| 503 | Service Unavailable | Service not initialized |

**Error Response Format:**
```json
{
  "detail": "Error message here"
}
```

**Frontend Error Handling:**
```javascript
async function apiRequest(url, options) {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    // Show user-friendly error message
    showNotification('error', error.message);
    throw error;
  }
}
```

---

## 🎯 **Common Frontend Patterns**

### **Pattern 1: User Login Flow**

```javascript
async function handleUserLogin(username, password) {
  // 1. Authenticate user (your auth endpoint)
  const user = await authenticateUser(username, password);
  
  // 2. Check for existing session
  const sessionCheck = await fetch(`/api/session/check?user_id=${user.id}`);
  const {has_session, session_id} = await sessionCheck.json();
  
  if (has_session) {
    // 3. Load conversation history
    const history = await fetch(
      `/api/session/history?session_id=${session_id}&limit=50`
    );
    const {messages} = await history.json();
    displayConversationHistory(messages);
  }
  
  // 4. Store user info
  localStorage.setItem('user_id', user.id);
  localStorage.setItem('session_id', session_id);
}
```

---

### **Pattern 2: Send Message Flow**

```javascript
async function sendMessage(message) {
  const userId = localStorage.getItem('user_id');
  
  // Send to backend
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: userId,
      message: message,
      language: 'en-IN'
    })
  });
  
  const data = await response.json();
  
  // Update UI
  addMessageToChat('user', message);
  addMessageToChat('assistant', data.answer);
  
  // Update session_id (in case it was newly created)
  localStorage.setItem('session_id', data.session_id);
  
  return data;
}
```

---

### **Pattern 3: Logout Flow**

```javascript
async function handleLogout() {
  const sessionId = localStorage.getItem('session_id');
  
  if (sessionId) {
    // End session
    await fetch('/api/session/end', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId})
    });
  }
  
  // Clear local storage
  localStorage.removeItem('user_id');
  localStorage.removeItem('session_id');
  
  // Redirect to login
  window.location.href = '/login';
}
```

---

## 📱 **Mobile App Integration**

### **React Native Example**

```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';

class ChatAPI {
  constructor(baseURL = 'http://localhost:5003') {
    this.baseURL = baseURL;
  }
  
  async sendMessage(message) {
    const userId = await AsyncStorage.getItem('user_id');
    
    const response = await fetch(`${this.baseURL}/api/chat`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        user_id: parseInt(userId),
        message: message,
        ip_address: await this.getDeviceIP(),
        user_agent: 'MyApp/1.0.0 (React Native)',
        device_type: Platform.OS  // 'ios' or 'android'
      })
    });
    
    return await response.json();
  }
}
```

---

## 🧪 **Testing in Swagger UI**

1. **Open Swagger UI:** `http://localhost:5003/docs`

2. **Test an endpoint:**
   - Click on any endpoint (e.g., `POST /api/chat`)
   - Click "Try it out" button
   - Fill in the request body with example data
   - Click "Execute"
   - View response below

3. **Copy request as cURL:**
   - After executing, scroll down to see generated cURL command
   - Copy and test in terminal

---

## ✅ **Validation Rules**

All request fields are validated. Common rules:

| Field | Validation |
|-------|------------|
| `user_id` | Required, must be positive integer |
| `message` | Required, minimum 1 character |
| `language` | Optional, default "en-IN" |
| `session_id` | Required for end/history, must be valid UUID |
| `limit` | Optional, must be positive integer |

**Validation Error Example:**
```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 🚀 **Production Checklist**

Before deploying to production:

- [ ] Add authentication middleware to all endpoints
- [ ] Protect `/api/admin/dashboard` with admin role check
- [ ] Add rate limiting (e.g., max 100 requests/min per user)
- [ ] Enable HTTPS/TLS
- [ ] Set up CORS properly (remove wildcard `*`)
- [ ] Add request logging and monitoring
- [ ] Set up error tracking (e.g., Sentry)
- [ ] Add API versioning (e.g., `/api/v1/...`)
- [ ] Document authentication flow in Swagger
- [ ] Add response time SLA monitoring

---

## 📞 **Support**

For API issues or questions:
- Check Swagger UI for latest docs: `http://localhost:5003/docs`
- View detailed schemas: `http://localhost:5003/redoc`
- Review source code: `app_celery.py` and `models/api_schemas.py`

---

**Happy Coding! 🎉**
