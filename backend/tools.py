# # backend/tools.py
from backend.calendar_service import (
    create_event,
    check_availability,
    delete_event,
)


tool_map = {
    "schedule_appointment": create_event,
    "check_appointment_availability": check_availability,
    "delete_appointment": delete_event,
}


openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "schedule_appointment",
            "description": "Schedule an appointment on the user's Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the appointment."
                    },
                    "start": {
                        "type": "string",
                        "description": "Appointment start time in ISO 8601 format."
                    },
                    "end": {
                        "type": "string",
                        "description": "Appointment end time in ISO 8601 format."
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address associated with the appointment."
                    }
                },
                "required": [
                    "title",
                    "start",
                    "end",
                    "email"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_appointment_availability",
            "description": "Check the user's Google Calendar for availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "Start of the period to check in ISO 8601 format."
                    },
                    "end": {
                        "type": "string",
                        "description": "End of the period to check in ISO 8601 format."
                    }
                },
                "required": [
                    "start",
                    "end"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "delete_appointment",
            "description": "Delete an appointment from the user's Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "Google Calendar event ID."
                    }
                },
                "required": [
                    "event_id"
                ]
            }
        }
    }
]