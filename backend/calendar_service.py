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
import logging
import os


logger = logging.getLogger(__name__)

from backend.logging_utils import log_debug

import boto3
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from backend.database import SessionLocal
from backend.models import GoogleAccount

from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# -----------------------------
# CONFIGURATION
# -----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

SECRET_NAME = os.environ.get("GOOGLE_CALENDAR_SECRET")

# Detect AWS Lambda
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


# AWS Secrets Manager client
secrets_client = boto3.client("secretsmanager") if IS_LAMBDA else None


# -----------------------------
# AWS SECRETS MANAGER
# -----------------------------


def get_google_token_from_secrets_manager():
    """
    Retrieve Google OAuth credentials from AWS Secrets Manager.
    """

    if not SECRET_NAME:
        raise RuntimeError(
            "GOOGLE_CALENDAR_SECRET environment variable " "is not configured."
        )

    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)

        secret_string = response.get("SecretString")

        if not secret_string:
            raise RuntimeError(
                "Google Calendar secret does not contain " "SecretString."
            )

        return json.loads(secret_string)

    except Exception as e:
        log_debug(logger, "SECRETS MANAGER ERROR:", str(e))
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
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or perform OAuth login
    if not creds or not creds.valid:

        # Refresh existing token
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            # Initial local OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

            creds = flow.run_local_server(port=8081, open_browser=False)

        # Save token locally
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# -----------------------------
# LAMBDA AUTHENTICATION
# -----------------------------


def get_lambda_service():
    """
    Authenticate using Google OAuth credentials
    stored in AWS Secrets Manager.
    """

    token_data = get_google_token_from_secrets_manager()

    try:
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    except Exception as e:
        log_debug(logger, "GOOGLE CREDENTIAL ERROR:", str(e))
        raise

    # Refresh expired credentials
    if not creds.valid:

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())

            except Exception as e:
                log_debug(logger, "GOOGLE TOKEN REFRESH ERROR:", str(e))
                raise

        else:
            raise RuntimeError(
                "Google Calendar credentials are " "invalid and cannot be refreshed."
            )

    return build("calendar", "v3", credentials=creds)


# -----------------------------
# GET CALENDAR SERVICE
# -----------------------------


def get_service(user_id: int):

    db = SessionLocal()

    try:
        google_account = (
            db.query(GoogleAccount).filter(GoogleAccount.user_id == user_id).first()
        )

        if not google_account:
            raise RuntimeError("Google Calendar is not connected for this user.")

        creds = Credentials(
            token=None,
            refresh_token=google_account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES,
        )

        if not creds.valid:

            if not creds.refresh_token:
                raise RuntimeError("Google Calendar refresh token is missing.")

            creds.refresh(Request())

        return build("calendar", "v3", credentials=creds)

    finally:
        db.close()


# -----------------------------
# CREATE EVENT
# -----------------------------


def create_event(user_id, title, start, end, email):
    service = get_service(user_id)

    event = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "Asia/Colombo"},
        "end": {"dateTime": end, "timeZone": "Asia/Colombo"},
        "attendees": [{"email": email}],
    }

    try:

        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        log_debug(logger, "\n=== GOOGLE CALENDAR RESPONSE ===")

        log_debug(logger, "Event ID:", created_event.get("id"))

        log_debug(logger, "HTML Link:", created_event.get("htmlLink"))

        log_debug(logger, "Status:", created_event.get("status"))

        log_debug(logger, "================================\n")

        if not created_event.get("id"):
            return {"error": "Event creation failed"}

        return {
            "success": True,
            "event_id": created_event.get("id"),
            "link": created_event.get("htmlLink"),
            "status": created_event.get("status"),
        }

    except Exception as e:

        log_debug(logger, "CALENDAR ERROR:", str(e))

        return {"error": str(e)}


# -----------------------------
# CHECK AVAILABILITY
# -----------------------------


def check_availability(user_id, start, end):
    service = get_service(user_id)

    def normalize(dt):
        if "Z" not in dt and "+" not in dt:
            return dt + "+05:30"

        return dt

    start = normalize(start)
    end = normalize(end)

    log_debug(logger, "\n=== AVAILABILITY DEBUG ===")
    log_debug(logger, "START:", start)
    log_debug(logger, "END:", end)
    log_debug(logger, "==========================\n")

    try:

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])

        log_debug(logger, "EVENT COUNT:", len(items))

        for event in items:
            log_debug(logger,
                " -",
                event.get("summary"),
                "|",
                event.get("start"),
            )

        return {
            "available": len(items) == 0,
            "start": start,
            "end": end,
            "events": [
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                }
                for event in items
            ],
        }

    except Exception as e:

        log_debug(logger, "AVAILABILITY ERROR:", str(e))

        return {"error": str(e)}


def find_available_slots(
    user_id,
    window_start,
    window_end,
    duration_minutes,
):
    service = get_service(user_id)

    def parse_datetime(value):
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        if "+" not in value:
            value = value + "+05:30"

        return datetime.fromisoformat(value)

    try:

        start = parse_datetime(window_start)
        end = parse_datetime(window_end)

        # Make sure the range is valid
        if end <= start:
            return {
                "success": False,
                "error": (
                    f"Invalid availability window: "
                    f"{start.isoformat()} -> {end.isoformat()}"
                ),
            }

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        busy_periods = []

        for event in events:

            event_start = event.get("start", {}).get("dateTime")

            event_end = event.get("end", {}).get("dateTime")

            # Ignore all-day events for now
            if not event_start or not event_end:
                continue

            busy_periods.append(
                (
                    parse_datetime(event_start),
                    parse_datetime(event_end),
                )
            )

        # ---------------------------------
        # FIND FREE SLOTS
        # ---------------------------------

        slots = []

        current = start
        duration = timedelta(minutes=duration_minutes)

        while current + duration <= end:

            slot_end = current + duration

            overlapping = False

            for busy_start, busy_end in busy_periods:

                if current < busy_end and slot_end > busy_start:
                    overlapping = True
                    break

            if not overlapping:

                slots.append(
                    {
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                    }
                )

            current += timedelta(minutes=30)

        return {
            "success": True,
            "window_start": window_start,
            "window_end": window_end,
            "duration_minutes": duration_minutes,
            "available_slots": slots,
        }

    except Exception as e:

        log_debug(logger, "FIND SLOTS ERROR:", str(e))

        return {"error": str(e)}


# -----------------------------
# FIND EVENTS
# -----------------------------

def find_events(
    user_id,
    start,
    end,
):
    """
    Find calendar events within a specific time range.
    """

    service = get_service(user_id)

    def normalize(dt):
        if "Z" not in dt and "+" not in dt:
            return dt + "+05:30"

        return dt

    start = normalize(start)
    end = normalize(end)

    log_debug(logger, "\n=== FIND EVENTS ===")
    log_debug(logger, "START:", start)
    log_debug(logger, "END:", end)
    log_debug(logger, "===================\n")

    try:

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get(
            "items",
            []
        )

        log_debug(logger,
            "EVENT COUNT:",
            len(events)
        )

        return {
            "success": True,
            "events": [
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "status": event.get("status"),
                    "htmlLink": event.get("htmlLink"),
                }
                for event in events
            ],
        }

    except Exception as e:

        log_debug(logger,
            "FIND EVENTS ERROR:",
            str(e)
        )

        return {
            "success": False,
            "error": str(e),
        }

# -----------------------------
# DELETE EVENT
# -----------------------------


def delete_event(user_id, event_id):
    service = get_service(user_id)

    try:

        service.events().delete(calendarId="primary", eventId=event_id).execute()

        return {"success": True}

    except Exception as e:

        log_debug(logger, "DELETE ERROR:", str(e))

        return {"error": str(e)}

# -----------------------------
# UPDATE EVENT
# -----------------------------

def update_event(
    user_id,
    event_id,
    start,
    end,
):
    """
    Update an existing Google Calendar event
    with a new start and end time.
    """

    service = get_service(user_id)

    try:

        # ---------------------------------
        # Get existing event
        # ---------------------------------

        event = (
            service.events()
            .get(
                calendarId="primary",
                eventId=event_id,
            )
            .execute()
        )

        # ---------------------------------
        # Update time
        # ---------------------------------

        event["start"] = {
            "dateTime": start,
            "timeZone": "Asia/Colombo",
        }

        event["end"] = {
            "dateTime": end,
            "timeZone": "Asia/Colombo",
        }

        # ---------------------------------
        # Update Google Calendar
        # ---------------------------------

        updated_event = (
            service.events()
            .update(
                calendarId="primary",
                eventId=event_id,
                body=event,
            )
            .execute()
        )

        log_debug(logger,
            "\n=== GOOGLE CALENDAR UPDATE ==="
        )

        log_debug(logger,
            "Event ID:",
            updated_event.get("id"),
        )

        log_debug(logger,
            "HTML Link:",
            updated_event.get("htmlLink"),
        )

        log_debug(logger,
            "Status:",
            updated_event.get("status"),
        )

        log_debug(logger,
            "===============================\n"
        )

        if not updated_event.get("id"):

            return {
                "success": False,
                "error": (
                    "Event update failed."
                ),
            }

        return {
            "success": True,
            "event_id": updated_event.get(
                "id"
            ),
            "link": updated_event.get(
                "htmlLink"
            ),
            "status": updated_event.get(
                "status"
            ),
            "start": updated_event.get(
                "start"
            ),
            "end": updated_event.get(
                "end"
            ),
        }

    except Exception as e:

        log_debug(logger,
            "UPDATE EVENT ERROR:",
            str(e)
        )

        return {
            "success": False,
            "error": str(e),
        }