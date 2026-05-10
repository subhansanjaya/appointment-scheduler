# backend/tools.py
from backend.calendar_service import create_event, check_availability, delete_event

tool_map = {
    "schedule_appointment": create_event,
    "check_appointment_availability": check_availability,
    "delete_appointment": delete_event
}