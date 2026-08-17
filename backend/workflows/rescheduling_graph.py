from typing import TypedDict
import json

from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from langgraph.graph import StateGraph, START, END

from backend.config import (
    OPENAI_API_KEY,
    AGENT_MODEL,
)

from backend.calendar_service import (
    find_events,
    check_availability,
    update_event,
)


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# STATE
# ============================================================

class ReschedulingState(TypedDict, total=False):

    user_id: int
    user_input: str

    conversation_history: list

    # Existing appointment
    old_start: str
    old_end: str

    event_id: str
    event: dict

    # New requested time
    new_start: str
    new_end: str

    # Results
    availability_result: dict
    rescheduling_result: dict

    # Confirmation
    confirmation_required: bool

    final_response: dict


# ============================================================
# PARSE REQUEST
# ============================================================

def parse_rescheduling_request(
    state: ReschedulingState
):

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    today = datetime.now(
        colombo_tz
    ).strftime(
        "%Y-%m-%d"
    )

    history = state.get(
        "conversation_history",
        []
    )

    history_lines = []

    for message in history:

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content",
            ""
        )

        if content:

            history_lines.append(
                f"{role}: {content}"
            )

    history_text = "\n".join(
        history_lines
    )

    prompt = f"""
Today is {today}.
Timezone: Asia/Colombo (+05:30).

You are extracting information for appointment
rescheduling.

Previous conversation:

{history_text}

Current request:

{state["user_input"]}

Extract:

1. The date/time of the EXISTING appointment.
2. The date/time of the NEW requested appointment.

Return ONLY JSON:

{{
    "old_start": "...",
    "old_end": "...",
    "new_start": "...",
    "new_end": "..."
}}

Rules:

- Use Asia/Colombo timezone.
- Convert relative dates such as tomorrow.
- If the old appointment time is given as
  "tomorrow at 7 PM", assume 30 minutes.
- If the new time is "8 PM", use the same date
  and same 30-minute duration.
- If duration is explicitly provided, use it.
- Do not invent missing dates or times.
"""

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": prompt,
            }
        ],
        response_format={
            "type": "json_object"
        },
    )

    data = json.loads(
        response.choices[0]
        .message
        .content
    )

    print(
        "\n=== RESCHEDULING PARSED ==="
    )

    print(data)

    print(
        "============================\n"
    )

    return data


# ============================================================
# FIND EXISTING EVENT
# ============================================================

def find_rescheduling_event(
    state: ReschedulingState
):

    print(
        "\nNODE: find_rescheduling_event"
    )

    result = find_events(
        user_id=state["user_id"],
        start=state["old_start"],
        end=state["old_end"],
    )

    print(
        "FIND EVENTS RESULT:",
        result
    )

    if not result.get("success"):

        return {
            "rescheduling_result": {
                "success": False,
                "error": result.get(
                    "error",
                    "Unable to search the calendar.",
                ),
            }
        }

    events = result.get(
        "events",
        []
    )

    if not events:

        return {
            "rescheduling_result": {
                "success": False,
                "error": (
                    "I couldn't find an appointment "
                    "at the requested time."
                ),
            }
        }

    event = events[0]

    print(
        "MATCHING EVENT:",
        event
    )

    return {
        "event_id": event.get(
            "id"
        ),
        "event": event,
    }


# ============================================================
# CHECK NEW TIME
# ============================================================

def check_new_time(
    state: ReschedulingState
):

    print(
        "\nNODE: check_new_time"
    )

    result = check_availability(
        user_id=state["user_id"],
        start=state["new_start"],
        end=state["new_end"],
    )

    print(
        "NEW TIME AVAILABILITY:",
        result
    )

    if result.get("error"):

        return {
            "rescheduling_result": {
                "success": False,
                "error": result.get(
                    "error",
                    "Unable to check the new time.",
                ),
            }
        }

    if not result.get("available"):

        return {
            "rescheduling_result": {
                "success": False,
                "error": (
                    "The requested new time "
                    "is not available."
                ),
            }
        }

    return {
        "availability_result": result,
        "confirmation_required": True,
    }


# ============================================================
# ROUTE AFTER FIND EVENT
# ============================================================

def route_after_find_event(
    state: ReschedulingState
):

    if state.get(
        "rescheduling_result"
    ):

        return "confirm"

    if state.get(
        "event_id"
    ):

        return "check_new_time"

    return "confirm"


# ============================================================
# ROUTE AFTER NEW TIME CHECK
# ============================================================

def route_after_new_time(
    state: ReschedulingState
):

    if state.get(
        "rescheduling_result"
    ):

        return "confirm"

    return "request_confirmation"


# ============================================================
# REQUEST CONFIRMATION
# ============================================================

def request_rescheduling_confirmation(
    state: ReschedulingState
):

    print(
        "\nNODE: request_rescheduling_confirmation"
    )

    event = state.get(
        "event",
        {}
    )

    title = event.get(
        "summary",
        "Appointment",
    )

    message = (
        f"I found '{title}'. "
        f"The requested new time is available. "
        f"Would you like me to reschedule it?"
    )

    return {
        "final_response": {
            "success": False,
            "needs_confirmation": True,
            "message": message,
        },

        "event_id": state.get(
            "event_id"
        ),

        "event": event,

        "old_start": state.get(
            "old_start"
        ),

        "old_end": state.get(
            "old_end"
        ),

        "new_start": state.get(
            "new_start"
        ),

        "new_end": state.get(
            "new_end"
        ),
    }


# ============================================================
# UPDATE EVENT
# ============================================================

def reschedule_event(
    state: ReschedulingState
):

    print(
        "\nNODE: reschedule_event"
    )

    event_id = state.get(
        "event_id"
    )

    new_start = state.get(
        "new_start"
    )

    new_end = state.get(
        "new_end"
    )

    if not event_id:

        return {
            "rescheduling_result": {
                "success": False,
                "error": (
                    "No appointment was found "
                    "to reschedule."
                ),
            }
        }

    if not new_start or not new_end:

        return {
            "rescheduling_result": {
                "success": False,
                "error": (
                    "The new appointment time "
                    "is missing."
                ),
            }
        }

    result = update_event(
        user_id=state["user_id"],
        event_id=event_id,
        start=new_start,
        end=new_end,
    )

    print(
        "UPDATE RESULT:",
        result
    )

    if result.get("success"):

        return {
            "rescheduling_result": {
                "success": True,
                "event_id": event_id,
                "link": result.get(
                    "link"
                ),
                "start": new_start,
                "end": new_end,
            }
        }

    return {
        "rescheduling_result": {
            "success": False,
            "error": result.get(
                "error",
                "Unable to reschedule the appointment.",
            ),
        }
    }


# ============================================================
# CONFIRM
# ============================================================

def confirm(
    state: ReschedulingState
):

    print(
        "\nNODE: rescheduling_confirm"
    )

    result = state.get(
        "rescheduling_result"
    )

    if result:

        if result.get("success"):

            final_response = {
                "success": True,
                "message": (
                    "Your appointment has been "
                    "rescheduled successfully."
                ),
                "event_id": result.get(
                    "event_id"
                ),
                "link": result.get(
                    "link"
                ),
                "start": result.get(
                    "start"
                ),
                "end": result.get(
                    "end"
                ),
            }

        else:

            final_response = {
                "success": False,
                "message": result.get(
                    "error",
                    "Unable to reschedule the appointment.",
                ),
            }

    else:

        final_response = state.get(
            "final_response",
            {
                "success": False,
                "message": (
                    "Unable to process the "
                    "rescheduling request."
                ),
            },
        )

    print(
        "FINAL RESCHEDULING RESPONSE:",
        final_response
    )

    return {
        "final_response": final_response
    }


# ============================================================
# GRAPH
# ============================================================

graph_builder = StateGraph(
    ReschedulingState
)


graph_builder.add_node(
    "parse_rescheduling_request",
    parse_rescheduling_request,
)

graph_builder.add_node(
    "find_rescheduling_event",
    find_rescheduling_event,
)

graph_builder.add_node(
    "check_new_time",
    check_new_time,
)

graph_builder.add_node(
    "request_confirmation",
    request_rescheduling_confirmation,
)

graph_builder.add_node(
    "reschedule_event",
    reschedule_event,
)

graph_builder.add_node(
    "confirm",
    confirm,
)


# ============================================================
# EDGES
# ============================================================

graph_builder.add_edge(
    START,
    "parse_rescheduling_request",
)

graph_builder.add_edge(
    "parse_rescheduling_request",
    "find_rescheduling_event",
)

graph_builder.add_conditional_edges(
    "find_rescheduling_event",
    route_after_find_event,
    {
        "check_new_time":
            "check_new_time",

        "confirm":
            "confirm",
    },
)

graph_builder.add_conditional_edges(
    "check_new_time",
    route_after_new_time,
    {
        "request_confirmation":
            "request_confirmation",

        "confirm":
            "confirm",
    },
)

# First request ends at confirmation.
graph_builder.add_edge(
    "request_confirmation",
    END,
)

# The actual update happens after user confirms.
graph_builder.add_edge(
    "reschedule_event",
    "confirm",
)

graph_builder.add_edge(
    "confirm",
    END,
)


# ============================================================
# COMPILE
# ============================================================

rescheduling_graph = (
    graph_builder.compile()
)