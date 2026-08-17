import os

from fastapi import (
    Depends,
    FastAPI,
    Request,
)
from mangum import Mangum


from fastapi.middleware.cors import (
    CORSMiddleware,
)

from fastapi.responses import (
    RedirectResponse,
)

from sqlalchemy.orm import Session

from starlette.middleware.sessions import (
    SessionMiddleware,
)

from backend.agent import run_agent
from backend.auth import oauth
from backend.database import get_db
from backend.models import (
    User,
    GoogleAccount,
)


app = FastAPI()


# ============================================================
# SESSION
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    session_cookie="appointment_session",
    same_site="none",
    https_only=True,
)


# ============================================================
# CORS
# ============================================================

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


# ============================================================
# GOOGLE LOGIN
# ============================================================

@app.get("/auth/google")
async def google_login(
    request: Request,
):

    redirect_uri = request.url_for(
        "google_callback"
    )

    print(
        "\n=== GOOGLE LOGIN ==="
    )

    print(
        "Redirect URI:",
        redirect_uri,
    )

    print(
        "====================\n"
    )

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        access_type="offline",
    )


# ============================================================
# GOOGLE CALLBACK
# ============================================================

@app.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
):

    token = await oauth.google.authorize_access_token(
        request
    )

    user_info = token.get(
        "userinfo"
    )

    if not user_info:

        return {
            "error": (
                "Unable to retrieve "
                "Google user information"
            )
        }

    google_user_id = user_info[
        "sub"
    ]

    email = user_info.get(
        "email"
    )

    name = user_info.get(
        "name"
    )

    # ========================================================
    # FIND OR CREATE APPLICATION USER
    # ========================================================

    user = (
        db.query(User)
        .filter(
            User.google_user_id
            == google_user_id
        )
        .first()
    )

    if not user:

        user = User(
            google_user_id=google_user_id,
            email=email,
            name=name,
        )

        db.add(user)

        db.commit()

        db.refresh(user)

    # ========================================================
    # GOOGLE ACCOUNT / REFRESH TOKEN
    # ========================================================

    refresh_token = token.get(
        "refresh_token"
    )

    google_account = (
        db.query(GoogleAccount)
        .filter(
            GoogleAccount.user_id
            == user.id
        )
        .first()
    )

    if google_account:

        # ----------------------------------------------------
        # EXISTING GOOGLE ACCOUNT
        # ----------------------------------------------------
        #
        # Google normally does not return a new
        # refresh token on every login.
        #
        # Therefore, keep the existing refresh token.
        #

        if refresh_token:

            google_account.refresh_token = (
                refresh_token
            )

    else:

        # ----------------------------------------------------
        # FIRST GOOGLE AUTHORIZATION
        # ----------------------------------------------------
        #
        # We need a refresh token for the first
        # authorization so the backend can access
        # Google Calendar later.
        #

        if not refresh_token:

            return {
                "error": (
                    "Google did not return a refresh token. "
                    "Please authorize again."
                )
            }

        google_account = GoogleAccount(
            user_id=user.id,
            google_user_id=google_user_id,
            refresh_token=refresh_token,
        )

        db.add(
            google_account
        )

    db.commit()

    # ========================================================
    # CREATE APPLICATION SESSION
    # ========================================================

    request.session[
        "user_id"
    ] = user.id

    print(
        "\n=== GOOGLE LOGIN SUCCESS ==="
    )

    print(
        "User ID:",
        user.id,
    )

    print(
        "Email:",
        user.email,
    )

    print(
        "Has new refresh token:",
        bool(refresh_token),
    )

    print(
        "============================\n"
    )

    # ========================================================
    # REDIRECT TO REACT
    # ========================================================

    return RedirectResponse(
        url=(
            "http://localhost:5173/"
            "?authenticated=true"
        )
    )


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/auth/me")
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):

    user_id = request.session.get(
        "user_id"
    )

    if not user_id:

        return {
            "authenticated": False
        }

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:

        request.session.clear()

        return {
            "authenticated": False
        }

    return {
        "authenticated": True,

        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
    }


# ============================================================
# LOGOUT
# ============================================================

@app.post("/auth/logout")
def logout(
    request: Request,
):

    # Only clear the application session.
    #
    # IMPORTANT:
    # This does NOT delete the Google refresh token.
    #
    # Therefore the user can log in again without
    # having to grant Calendar permissions again.

    request.session.clear()

    return {
        "success": True
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
def chat(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):

    # ========================================================
    # AUTHENTICATION
    # ========================================================

    user_id = request.session.get(
        "user_id"
    )

    if not user_id:

        return {
            "error": (
                "Authentication required"
            )
        }

    # ========================================================
    # USER INPUT
    # ========================================================

    user_input = payload.get(
        "message"
    )

    if not user_input:

        return {
            "error": (
                "Message is required"
            )
        }

    print(
        "\n=== CHAT REQUEST ==="
    )

    print(
        "User ID:",
        user_id,
    )

    print(
        "Message:",
        user_input,
    )

    print(
        "====================\n"
    )

    # ========================================================
    # RUN AGENT
    # ========================================================

    response = run_agent(
        db,
        user_id,
        user_input,
    )

    # ========================================================
    # RETURN AI RESPONSE
    # ========================================================

    return {
        "response": response
    }
    
# ============================================================
# AWS LAMBDA HANDLER
# ============================================================


handler = Mangum(app)