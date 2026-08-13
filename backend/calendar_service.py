"""
Calendar Service Module

Provides Google Calendar integration:

- Local development: OAuth using token.json / credentials.json
- AWS Lambda: OAuth credentials from AWS Secrets Manager
- Create events
- Check availability
- Delete events
"""

import json
import os

import boto3
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]


# -----------------------------
# CONFIGURATION
# -----------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

TOKEN_FILE = os.path.join(
    BASE_DIR,
    "token.json"
)

CREDENTIALS_FILE = os.path.join(
    BASE_DIR,
    "credentials.json"
)

SECRET_NAME = os.environ.get(
    "GOOGLE_CALENDAR_SECRET"
)

# Detect AWS Lambda
IS_LAMBDA = bool(
    os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
)


# AWS Secrets Manager client
secrets_client = boto3.client(
    "secretsmanager"
) if IS_LAMBDA else None


# -----------------------------
# AWS SECRETS MANAGER
# -----------------------------

def get_google_token_from_secrets_manager():
    """
    Retrieve Google OAuth credentials from AWS Secrets Manager.
    """

    if not SECRET_NAME:
        raise RuntimeError(
            "GOOGLE_CALENDAR_SECRET environment variable "
            "is not configured."
        )

    try:
        response = secrets_client.get_secret_value(
            SecretId=SECRET_NAME
        )

        secret_string = response.get(
            "SecretString"
        )

        if not secret_string:
            raise RuntimeError(
                "Google Calendar secret does not contain "
                "SecretString."
            )

        return json.loads(secret_string)

    except Exception as e:
        print(
            "SECRETS MANAGER ERROR:",
            str(e)
        )
        raise


# -----------------------------
# LOCAL AUTHENTICATION
# -----------------------------

def get_local_service():
    """
    Authenticate using local token.json.

    Used only during local development.
    """

    creds = None

    # Load saved token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    # Refresh or perform OAuth login
    if not creds or not creds.valid:

        # Refresh existing token
        if (
            creds
            and creds.expired
            and creds.refresh_token
        ):
            creds.refresh(Request())

        else:
            # Initial local OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES
            )

            creds = flow.run_local_server(
                port=8081,
                open_browser=False
            )

        # Save token locally
        with open(
            TOKEN_FILE,
            "w"
        ) as token:
            token.write(
                creds.to_json()
            )

    return build(
        "calendar",
        "v3",
        credentials=creds
    )


# -----------------------------
# LAMBDA AUTHENTICATION
# -----------------------------

def get_lambda_service():
    """
    Authenticate using Google OAuth credentials
    stored in AWS Secrets Manager.
    """

    token_data = (
        get_google_token_from_secrets_manager()
    )

    try:
        creds = Credentials.from_authorized_user_info(
            token_data,
            SCOPES
        )

    except Exception as e:
        print(
            "GOOGLE CREDENTIAL ERROR:",
            str(e)
        )
        raise

    # Refresh expired credentials
    if not creds.valid:

        if (
            creds.expired
            and creds.refresh_token
        ):
            try:
                creds.refresh(
                    Request()
                )

            except Exception as e:
                print(
                    "GOOGLE TOKEN REFRESH ERROR:",
                    str(e)
                )
                raise

        else:
            raise RuntimeError(
                "Google Calendar credentials are "
                "invalid and cannot be refreshed."
            )

    return build(
        "calendar",
        "v3",
        credentials=creds
    )


# -----------------------------
# GET CALENDAR SERVICE
# -----------------------------

def get_service():
    """
    Return the appropriate Google Calendar service.

    Local:
        Uses token.json / credentials.json

    Lambda:
        Uses AWS Secrets Manager
    """

    if IS_LAMBDA:
        return get_lambda_service()

    return get_local_service()


# -----------------------------
# CREATE EVENT
# -----------------------------

def create_event(
    title,
    start,
    end,
    email
):
    service = get_service()

    event = {
        "summary": title,
        "start": {
            "dateTime": start,
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end,
            "timeZone": "Asia/Kolkata"
        },
        "attendees": [
            {
                "email": email
            }
        ]
    }

    try:

        created_event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event
            )
            .execute()
        )

        print(
            "\n=== GOOGLE CALENDAR RESPONSE ==="
        )

        print(
            "Event ID:",
            created_event.get("id")
        )

        print(
            "HTML Link:",
            created_event.get("htmlLink")
        )

        print(
            "Status:",
            created_event.get("status")
        )

        print(
            "================================\n"
        )

        if not created_event.get("id"):
            return {
                "error":
                    "Event creation failed"
            }

        return {
            "success": True,
            "event_id":
                created_event.get("id"),
            "link":
                created_event.get("htmlLink"),
            "status":
                created_event.get("status")
        }

    except Exception as e:

        print(
            "CALENDAR ERROR:",
            str(e)
        )

        return {
            "error": str(e)
        }


# -----------------------------
# CHECK AVAILABILITY
# -----------------------------

def check_availability(
    start,
    end
):
    service = get_service()

    def normalize(dt):

        if (
            "Z" not in dt
            and "+" not in dt
        ):
            return dt + "+05:30"

        return dt

    start = normalize(start)
    end = normalize(end)

    print(
        "\n=== AVAILABILITY DEBUG ==="
    )

    print(
        "START:",
        start
    )

    print(
        "END:",
        end
    )

    print(
        "==========================\n"
    )

    try:

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime"
            )
            .execute()
        )

        items = events_result.get(
            "items",
            []
        )

        print(
            "EVENT COUNT:",
            len(items)
        )

        for event in items:

            print(
                " -",
                event.get("summary"),
                "|",
                event.get("start")
            )

        return items

    except Exception as e:

        print(
            "AVAILABILITY ERROR:",
            str(e)
        )

        return {
            "error": str(e)
        }


# -----------------------------
# DELETE EVENT
# -----------------------------

def delete_event(
    event_id
):
    service = get_service()

    try:

        service.events().delete(
            calendarId="primary",
            eventId=event_id
        ).execute()

        return {
            "success": True
        }

    except Exception as e:

        print(
            "DELETE ERROR:",
            str(e)
        )

        return {
            "error": str(e)
        }