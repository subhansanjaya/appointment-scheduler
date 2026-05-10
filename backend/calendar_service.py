# backend/calendar_service.py
"""
Calendar Service Module

This module provides functionality to interact with Google Calendar API.
It includes functions to authenticate, create events, check availability,
and delete events from the primary calendar.
"""

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_service():
    """
    Authenticate and build the Google Calendar service.

    This function handles OAuth 2.0 authentication using client secrets
    and returns a service object for interacting with the Calendar API.

    Returns:
        googleapiclient.discovery.Resource: The Calendar API service object.
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json",
        SCOPES
    )
    creds = flow.run_local_server(port=0)
    return build("calendar", "v3", credentials=creds)


def create_event(title, start, end, email):
    """
    Create a new event in the primary Google Calendar.

    Args:
        title (str): The title/summary of the event.
        start (str): The start date and time in ISO format (e.g., '2023-10-01T10:00:00').
        end (str): The end date and time in ISO format (e.g., '2023-10-01T11:00:00').
        email (str): The email address of the attendee.

    Returns:
        str: The ID of the created event.
    """
    service = get_service()

    event = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end, "timeZone": "Asia/Kolkata"},
        "attendees": [{"email": email}]
    }

    event = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return event["id"]

def check_availability(start, end):
    """
    Check for existing events in the primary calendar within a time range.

    This function retrieves upcoming events to check availability.
    Note: Currently returns all events, but can be modified to filter by time.

    Args:
        start (str): The start time for checking availability (ISO format).
        end (str): The end time for checking availability (ISO format).

    Returns:
        list: A list of event dictionaries from the calendar.
    """
    service = get_service()

    events_result = service.events().list(
        calendarId="primary",
        maxResults=10,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return events_result.get("items", [])

def delete_event(event_id):
    """
    Delete an event from the primary Google Calendar.

    Args:
        event_id (str): The ID of the event to delete.

    Returns:
        bool: True if the event was successfully deleted.
    """
    service = get_service()

    service.events().delete(
        calendarId="primary",
        eventId=event_id
    ).execute()

    return True