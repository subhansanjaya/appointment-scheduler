# AI Appointment Scheduler

A conversational appointment scheduler built with FastAPI, React, OpenAI and Google Calendar. The project demonstrates an AI agent architecture where natural-language scheduling requests are interpreted by an LLM and translated into calendar actions through a tool execution layer.

![screenshot](https://github.com/subhansanjaya/appointment-scheduler/blob/main/capture.png)

![screenshot](https://github.com/subhansanjaya/appointment-scheduler/blob/main/capture2.png)

![screenshot](https://github.com/subhansanjaya/appointment-scheduler/blob/feature/v2-multi-user/capture3.png)
---

## Features

- AI chatbot interface for appointment scheduling
- LLM-powered scheduling agent
- Scheduling intent classification layer
- Book appointments
- Check calendar availability
- Delete appointments
- Google Calendar integration
- Structured agent responses
- Backend tool execution layer


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
- OpenAI GPT models
- Intent classification
- Agent-based orchestration
- Structured JSON responses
- Tool execution

### Infrastructure

- AWS Lambda
- API Gateway
- AWS Secrets Manager
- Amazon S3
- Amazon CloudFront

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
    └── .env.development
    └── .env.production
│
├── venv/
└── README.md
```

---
## Environment Variables

- Create a .env file in the backend folder:

- OPENAI_API_KEY=your_openai_api_key

- INTENT_MODEL=gpt-4o-mini
- AGENT_MODEL=gpt-4o

For Google Calendar (if enabled):
- GOOGLE_CREDENTIALS=credentials.json

## Run Backend
- cd backend
- source ../venv/bin/activate
- uvicorn main:app --reload
- Backend runs at: 127.0.0.1:8000

##  Run Frontend
- create .env.development with VITE_API_URL=http://localhost:8000 / .env.production for production deployment (npm run build)
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

For AWS Lambda, the Google OAuth credentials are stored in AWS Secrets Manager instead of being included in the Lambda deployment package.

##  Future Enhancements
- Should add unit tests
- Multi-user authentication
- Persistent database (PostgreSQL)
- Real-time chat streaming
- Google Calendar full OAuth flow
- LangChain / LangGraph upgrade

## Version History

### v1.0.0 — Single User (MVP)

Current stable release.

Includes:

- Appointment scheduling
- Calendar availability checking
- Appointment deletion
- AI scheduling agent
- Scheduling intent layer
- Google Calendar integration

### v2.0.0 — Multi-User Architecture: 

This version introduces:
- Google OAuth authentication
- user-specific sessions and Google Calendar access
- PostgreSQL-based persistence for users and Google accounts
- persistent conversation state
- multi-turn scheduling workflows. 

The backend uses FastAPI and LangGraph to handle availability and booking workflows, with the application deployed using AWS Lambda, API Gateway, Amazon RDS, NAT Gateway, S3, and CloudFront.

> **Note:** The v2.0.0 code has been committed to the `feature/v2-multi-user` branch but has not been tagged yet. The release will be tagged as `v2.0.0` after the planned refactoring and final cleanup.

---

## Future Improvements

- Authentication and authorization
- AI evaluation framework
- Intent classification evaluation
- Improved error handling
- Unit and integration tests
- Persistent database
- Streaming responses
- Better observability
- Rate limiting
- Usage-based quotas
- Multi-user Google Calendar integration
- Asynchronous background processing

---

## License

MIT License