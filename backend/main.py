from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.agent import run_agent
from mangum import Mangum


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://d32obth2v9hhu6.cloudfront.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
def chat(payload: dict):

    user_input = payload["message"]

    response = run_agent(user_input)

    return {
        "response": response
    }


_mangum_handler = Mangum(app)


def handler(event, context):

    print("=== API GATEWAY EVENT ===")
    print(event)

    return _mangum_handler(event, context)