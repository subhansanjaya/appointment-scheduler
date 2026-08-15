import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from backend.agent import run_agent
from backend.auth import oauth
from backend.database import get_db
from backend.models import User, GoogleAccount

app = FastAPI()

# -----------------------------
# SESSION
# -----------------------------

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
)

# -----------------------------
# CORS
# -----------------------------

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


# -----------------------------
# GOOGLE LOGIN
# -----------------------------

@app.get("/auth/google")
async def google_login(request: Request):

    redirect_uri = request.url_for(
        "google_callback"
    )

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        access_type="offline",
        prompt="consent",
    )


# -----------------------------
# GOOGLE CALLBACK
# -----------------------------

@app.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    token = await oauth.google.authorize_access_token(request)

    user_info = token.get("userinfo")

    if not user_info:
        return {
            "error": "Unable to retrieve Google user information"
        }

    google_user_id = user_info["sub"]
    email = user_info.get("email")
    name = user_info.get("name")

    # -----------------------------
    # FIND OR CREATE APPLICATION USER
    # -----------------------------

    user = (
        db.query(User)
        .filter(
            User.google_user_id == google_user_id
        )
        .first()
    )

    if not user:
        user = User(
            google_user_id=google_user_id,
            email=email,
            name=name
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    # -----------------------------
    # GET GOOGLE REFRESH TOKEN
    # -----------------------------

    refresh_token = token.get("refresh_token")

    if not refresh_token:
        return {
            "error": (
                "Google did not return a refresh token. "
                "Please authorize again."
            )
        }

    # -----------------------------
    # FIND EXISTING GOOGLE ACCOUNT
    # -----------------------------

    google_account = (
        db.query(GoogleAccount)
        .filter(
            GoogleAccount.user_id == user.id
        )
        .first()
    )

    if google_account:

        google_account.refresh_token = refresh_token

    else:

        google_account = GoogleAccount(
            user_id=user.id,
            google_user_id=google_user_id,
            refresh_token=refresh_token
        )

        db.add(google_account)

    db.commit()

    # -----------------------------
    # CREATE SESSION
    # -----------------------------

    request.session["user_id"] = user.id

    return {
        "message": "Google login successful",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }
# -----------------------------
# CHAT
# -----------------------------

@app.post("/chat")
def chat(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):

    user_id = request.session.get("user_id")

    if not user_id:
        return {
            "error": "Authentication required"
        }

    user_input = payload["message"]

    response = run_agent(
        db,
        user_id,
        user_input,
    )

    return {
        "response": response
    }