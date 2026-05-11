"""
Calendar Service Module

Provides Google Calendar integration:
- OAuth authentication (persisted token)
- Create events
- Check availability
- Delete events
"""

import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# -----------------------------
# AUTH 
# -----------------------------
def get_service():
    creds = None

    # Load saved token if available
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If no valid creds → login once
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Save token for future use
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# -----------------------------
# CREATE EVENT
# -----------------------------
def create_event(title, start, end, email):
    service = get_service()

    event = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end, "timeZone": "Asia/Kolkata"},
        "attendees": [{"email": email}]
    }

    try:
        created_event = service.events().insert(
            calendarId="primary",
            body=event
        ).execute()

        print("\n=== GOOGLE CALENDAR RESPONSE ===")
        print("Event ID:", created_event.get("id"))
        print("HTML Link:", created_event.get("htmlLink"))
        print("Status:", created_event.get("status"))
        print("================================\n")

        if not created_event.get("id"):
            return {"error": "Event creation failed"}

        return {
            "success": True,
            "event_id": created_event.get("id"),
            "link": created_event.get("htmlLink"),
            "status": created_event.get("status")
        }

    except Exception as e:
        print("CALENDAR ERROR:", str(e))
        return {"error": str(e)}


# -----------------------------
# CHECK AVAILABILITY 
# -----------------------------
def check_availability(start, end):
    service = get_service()

    def normalize(dt):
        if "Z" not in dt and "+" not in dt:
            return dt + "+05:30"
        return dt

    start = normalize(start)
    end = normalize(end)

    print("\n=== AVAILABILITY DEBUG ===")
    print("START:", start)
    print("END:", end)
    print("==========================\n")

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        items = events_result.get("items", [])

        print("EVENT COUNT:", len(items))

        for e in items:
            print(" -", e.get("summary"), "|", e["start"])

        return items

    except Exception as e:
        print("AVAILABILITY ERROR:", str(e))
        return {"error": str(e)}


# -----------------------------
# DELETE EVENT
# -----------------------------
def delete_event(event_id):
    service = get_service()

    try:
        service.events().delete(
            calendarId="primary",
            eventId=event_id
        ).execute()

        return {"success": True}

    except Exception as e:
        print("DELETE ERROR:", str(e))
        return {"error": str(e)}