# # # backend/tools.py
# from backend.calendar_service import (
#     create_event,
#     check_availability,
#     find_available_slots,
#     delete_event,
# )

# tool_map = {
#     "schedule_appointment": create_event,
#     "check_appointment_availability": check_availability,
#     "find_available_slots": find_available_slots,
#     "delete_appointment": delete_event,
# }


# openai_tools = [
#     {
#         "type": "function",
#         "function": {
#             "name": "schedule_appointment",
#             "description": "Schedule an appointment on the user's Google Calendar.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "title": {
#                         "type": "string",
#                         "description": "Title of the appointment.",
#                     },
#                     "start": {
#                         "type": "string",
#                         "description": "Appointment start time in ISO 8601 format.",
#                     },
#                     "end": {
#                         "type": "string",
#                         "description": "Appointment end time in ISO 8601 format.",
#                     },
#                     "email": {
#                         "type": "string",
#                         "description": "Email address associated with the appointment.",
#                     },
#                 },
#                 "required": ["title", "start", "end", "email"],
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "check_appointment_availability",
#             "description": "Check the user's Google Calendar for availability.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "start": {
#                         "type": "string",
#                         "description": "Start of the period to check in ISO 8601 format.",
#                     },
#                     "end": {
#                         "type": "string",
#                         "description": "End of the period to check in ISO 8601 format.",
#                     },
#                 },
#                 "required": ["start", "end"],
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "find_available_slots",
#             "description": (
#                 "Find available appointment slots within a specified " "time window."
#             ),
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "window_start": {
#                         "type": "string",
#                         "description": (
#                             "Start of the search window in ISO 8601 format."
#                         ),
#                     },
#                     "window_end": {
#                         "type": "string",
#                         "description": ("End of the search window in ISO 8601 format."),
#                     },
#                     "duration_minutes": {
#                         "type": "integer",
#                         "description": ("Required appointment duration in minutes."),
#                     },
#                 },
#                 "required": [
#                     "window_start",
#                     "window_end",
#                     "duration_minutes",
#                 ],
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "delete_appointment",
#             "description": "Delete an appointment from the user's Google Calendar.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "event_id": {
#                         "type": "string",
#                         "description": "Google Calendar event ID.",
#                     }
#                 },
#                 "required": ["event_id"],
#             },
#         },
#     },
# ]


# backend/tools.py

# This file can be kept temporarily for non-scheduling tools.
#
# Scheduling is now handled by:
#
# agent.py
#     ↓
# intent.py
#     ↓
# booking_service.py
#     ↓
# booking_graph.py
#     ↓
# calendar_service.py
#
# Do not expose calendar functions as general LLM tools.

tool_map = {}

openai_tools = []