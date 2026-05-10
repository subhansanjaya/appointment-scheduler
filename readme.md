# A conversational AI agent

An appointment scheduler built with FastAPI, React, and OpenAI function calling to create and manage calendar events. Built as a prototype project for AI agent systems and scheduling automation.

![screenshot](https://github.com/subhansanjaya/appointment-scheduler/blob/main/capture.png)

---

## Features

- AI chatbot interface for booking appointments
- LLM-powered decision making (agent-based system)
- Schedule, check, and delete appointments via tools
- Backend function calling system (tool execution layer)
- FastAPI backend for API handling
- React frontend for chat UI
- Google Calendar integration

---

## How It Works

1. User sends a message from the React UI  
2. FastAPI receives the request  
3. The AI agent sends the prompt to an LLM  
4. The LLM responds in structured JSON:
   - Reply to user OR
   - Request a function call  
5. Backend executes the requested tool  
6. Response is returned back to the frontend  

---

## Tech Stack

### Backend
- FastAPI
- Python
- OpenAI API
- Google Calendar API (OAuth)

### Frontend
- React (TypeScript)
- Fetch API / Axios

### AI Layer
- OpenAI GPT models (function calling)
- Agent-based orchestration logic

---

## Project Structure

React Frontend
↓
FastAPI Backend
↓
AI Agent (LLM - OpenAI)
↓
Tool Layer (Function Calling)
↓
Calendar Service (Google Calendar API)

```

appointment-scheduler/
│
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── agent.py            # AI agent logic
│   ├── tools.py            # Function mapping layer
│   ├── calendar_service.py # Google Calendar integration
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── Chat.tsx
│   │   └── api.ts
│
├── venv/
└── README.md
```

---
## Environment Variables

- Create a .env file in the backend folder:

- OPENAI_API_KEY=your_openai_api_key

For Google Calendar (if enabled):

- GOOGLE_CLIENT_ID=your_client_id
- GOOGLE_CLIENT_SECRET=your_client_secret

## Run Backend
- cd backend
- source ../venv/bin/activate
- uvicorn main:app --reload
- Backend runs at: 127.0.0.1:8000

##  Run Frontend
- cd frontend
- npm install
- npm run dev

Frontend runs at:localhost:5173

## Google Calendar Setup

To enable calendar integration:

- Go to Google Cloud Console
- Enable Google Calendar API
- Create OAuth credentials
- Download credentials.json
- Place it inside /backend


##  Future Enhancements
- Multi-user authentication
- Persistent database (PostgreSQL)
- Real-time chat streaming
- Google Calendar full OAuth flow
- LangChain / LangGraph upgrade

## License
MIT License