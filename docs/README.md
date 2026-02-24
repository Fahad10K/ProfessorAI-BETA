# ProfAI - Production Ready Educational AI Assistant

A multilingual AI-powered educational assistant that combines RAG, OpenAI, and Sarvam AI services for document processing, course generation, and interactive learning.

## 🌟 Features

### Core Capabilities
- **📄 PDF Upload & Processing** - Extract and process educational content from PDFs
- **🤖 AI Course Generation** - Automatically generate structured courses from documents
- **💬 RAG-powered Chat Interface** - Interactive Q&A with document context
- **🎤 Voice Interaction** - Support for 11 Indian languages via Sarvam AI
- **🔊 Text-to-Speech** - Audio responses in multiple languages
- **🌐 Multilingual Support** - English + 10 Indian languages

### Technical Features
- **FastAPI Backend** - High-performance async API
- **ChromaDB Vector Store** - Efficient document retrieval
- **OpenAI Integration** - GPT-4 powered responses
- **Sarvam AI Integration** - Indian language processing
- **Modular Architecture** - Clean, maintainable codebase

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Clone or navigate to the project
cd ProfAI_PROD

# Run setup script to copy sample data (optional)
python setup.py

# Copy environment template
copy .env.example .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=your_openai_key
# SARVAM_API_KEY=your_sarvam_key
# GROQ_API_KEY=your_groq_key (optional)
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start Server
```bash
python run_server.py
```

### 4. Access Application
- **Main Interface**: http://127.0.0.1:5001
- **Upload PDFs**: http://127.0.0.1:5001/web/upload.html
- **View Courses**: http://127.0.0.1:5001/web/courses.html

## 📁 Project Structure

```
ProfAI_PROD/
├── 📱 app.py                    # Main FastAPI application
├── ⚙️ config.py                # Configuration settings
├── 🚀 run_server.py            # Server runner
├── 🔧 setup.py                 # Environment setup script
├── 📋 requirements.txt         # Python dependencies
├── 🌐 web/                     # Web interface files
│   ├── index.html             # Main chat interface
│   ├── upload.html            # PDF upload page
│   ├── courses.html           # Course listing
│   └── course.html            # Course viewer
├── 🧠 core/                    # Core business logic
│   ├── course_generator.py    # Course generation engine
│   └── vectorizer.py          # Document vectorization
├── 🔧 services/                # External service integrations
│   ├── chat_service.py        # Chat orchestration
│   ├── document_service.py    # Document processing
│   ├── rag_service.py         # RAG implementation
│   ├── llm_service.py         # LLM interactions
│   ├── audio_service.py       # Audio processing
│   └── sarvam_service.py      # Sarvam AI integration
├── 🔄 processors/              # Data processing utilities
│   ├── pdf_extractor.py       # PDF text extraction
│   └── text_chunker.py        # Text chunking
├── 📊 models/                  # Data models and schemas
│   └── schemas.py             # Pydantic models
└── 💾 data/                    # Data storage
    ├── documents/             # Uploaded PDFs
    ├── vectorstore/           # ChromaDB database
    └── courses/               # Generated courses
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
SARVAM_API_KEY=your_sarvam_api_key_here

# Optional
GROQ_API_KEY=your_groq_api_key_here

# Server Configuration (optional overrides)
HOST=127.0.0.1
PORT=5001
DEBUG=True
```

### Supported Languages
- **English** (en)
- **Hindi** (hi)
- **Tamil** (ta)
- **Telugu** (te)
- **Kannada** (kn)
- **Malayalam** (ml)
- **Gujarati** (gu)
- **Marathi** (mr)
- **Bengali** (bn)
- **Punjabi** (pa)
- **Odia** (or)

## 📖 Usage Guide

### 1. Upload Documents
1. Navigate to the upload page
2. Select or drag-and-drop PDF files
3. Optionally provide a course title
4. Click "Generate Course"

### 2. Chat with Documents
1. Use the main chat interface
2. Ask questions about uploaded content
3. Select response language
4. Use voice input for supported languages

### 3. Browse Generated Courses
1. View all generated courses
2. Navigate through course modules
3. Access structured learning content

## 🔌 API Endpoints

### Core Endpoints
- `POST /api/chat` - Chat with AI assistant
- `POST /api/upload-pdfs` - Upload and process PDFs
- `GET /api/courses` - List all courses
- `GET /api/course/{course_id}` - Get specific course
- `POST /api/transcribe` - Audio transcription
- `POST /api/text-to-speech` - Generate audio

### Web Interface
- `GET /` - Main chat interface
- `GET /web/{filename}` - Static web files

## 🛠️ Development

### Running in Development Mode
```bash
# Enable debug mode in .env
DEBUG=True

# Start with auto-reload
python run_server.py
```

### Adding New Features
1. **Services**: Add new integrations in `services/`
2. **Processors**: Add data processing in `processors/`
3. **Models**: Define data structures in `models/`
4. **Web UI**: Update interface files in `web/`

## 🔍 Troubleshooting

### Common Issues

**1. API Key Errors**
- Ensure all required API keys are set in `.env`
- Check API key validity and quotas

**2. File Upload Issues**
- Verify PDF files are not corrupted
- Check file size limits
- Ensure `data/documents/` directory exists

**3. Vector Database Issues**
- Delete `data/vectorstore/` to reset
- Re-upload documents to rebuild index

**4. Port Already in Use**
- Change PORT in `.env` or config.py
- Kill existing processes on port 5001

### Logs and Debugging
- Check console output for detailed error messages
- Enable DEBUG mode for verbose logging
- Monitor browser developer console for frontend issues

## 📄 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Create an issue with detailed information