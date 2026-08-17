from typing import TypedDict
import json

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import OpenAI
from langgraph.graph import StateGraph, START, END

from backend.config import (
    OPENAI_API_KEY,
    AGENT_MODEL,
)

from backend.calendar_service import (
    find_events,
    delete_event,
)


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# STATE
# ============================================================

class CancellationState(TypedDict, total=False):

    user_id: int
    user_input: str

    conversation_history: list

    window_start: str
    window_end: str

    event_id: str
    event: dict

    confirmation_required: bool
    confirmed: bool

    cancellation_result: dict

    final_response: dict


# ============================================================
# PARSE REQUEST
# ============================================================

def parse_cancellation_request(
    state: CancellationState
):

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    now = datetime.now(
        colombo_tz
    )

    today = now.date()

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
Current date:
{today.strftime("%Y-%m-%d")}

Timezone:
Asia/Colombo (+05:30)

You are extracting information for appointment
cancellation.

Previous conversation:

{history_text}

Current request:

{state["user_input"]}

Return ONLY JSON:

{{
    "date_expression": "today | tomorrow | explicit_date",
    "explicit_date": null,
    "hour": 0,
    "minute": 0,
    "duration_minutes": 30
}}

Rules:

- Do NOT calculate dates.
- Do NOT return window_start.
- Do NOT return window_end.
- If the user says "today", return:
  "date_expression": "today"

- If the user says "tomorrow", return:
  "date_expression": "tomorrow"

- If the user provides an explicit date such as
  "August 20", return:
  "date_expression": "explicit_date"
  and put the date in "explicit_date"
  using YYYY-MM-DD.

- Extract the requested time as hour and minute.
- Use 24-hour values.
- "4 AM" means hour 4, minute 0.
- "4 PM" means hour 16, minute 0.
- "7:30 PM" means hour 19, minute 30.

- If duration is explicitly provided, use it.
- If no duration is provided, use 30 minutes.

- Do not invent a date.
- Do not perform date arithmetic.
"""

    response = client.chat.completions.create(
        model=AGENT_MODEL,
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

    # ========================================================
    # RESOLVE DATE IN PYTHON
    # ========================================================

    date_expression = data.get(
        "date_expression"
    )

    if date_expression == "today":

        target_date = today

    elif date_expression == "tomorrow":

        target_date = (
            today + timedelta(days=1)
        )

    elif (
        date_expression == "explicit_date"
        and data.get("explicit_date")
    ):

        target_date = datetime.strptime(
            data["explicit_date"],
            "%Y-%m-%d",
        ).date()

    else:

        return {
            "cancellation_result": {
                "success": False,
                "error": (
                    "Please provide the date and "
                    "time of the appointment."
                ),
            }
        }

    # ========================================================
    # TIME
    # ========================================================

    hour = int(
        data.get(
            "hour",
            0,
        )
    )

    minute = int(
        data.get(
            "minute",
            0,
        )
    )

    duration_minutes = int(
        data.get(
            "duration_minutes",
            30,
        )
    )

    # ========================================================
    # BUILD DATETIME
    # ========================================================

    start_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=colombo_tz,
    )

    end_dt = (
        start_dt
        + timedelta(
            minutes=duration_minutes
        )
    )

    result = {
        "window_start": start_dt.isoformat(),
        "window_end": end_dt.isoformat(),
    }

    print(
        "\n=== CANCELLATION PARSED ==="
    )

    print(
        "LLM EXTRACTION:",
        data,
    )

    print(
        "RESOLVED DATE:",
        target_date,
    )

    print(
        "WINDOW START:",
        result["window_start"],
    )

    print(
        "WINDOW END:",
        result["window_end"],
    )

    print(
        "===========================\n"
    )

    return result


# ============================================================
# FIND EVENT
# ============================================================

def find_cancellation_event(
    state: CancellationState
):

    print(
        "\nNODE: find_cancellation_event"
    )

    window_start = state["window_start"]

    # ========================================================
    # TARGET DATE / TIME
    # ========================================================

    target_dt = datetime.fromisoformat(
        window_start
    )

    # ========================================================
    # SEARCH THE ENTIRE DAY
    # ========================================================

    day_start = target_dt.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    day_end = (
        day_start
        + timedelta(days=1)
    )

    search_start = day_start.isoformat()
    search_end = day_end.isoformat()

    print(
        "\n=== CANCELLATION DAY SEARCH ==="
    )

    print(
        "TARGET:",
        target_dt.isoformat(),
    )

    print(
        "SEARCH START:",
        search_start,
    )

    print(
        "SEARCH END:",
        search_end,
    )

    print(
        "================================\n"
    )

    result = find_events(
        user_id=state["user_id"],
        start=search_start,
        end=search_end,
    )

    if not result.get("success"):

        return {
            "cancellation_result": {
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

    print(
        "CANCELLATION EVENTS:",
        len(events),
    )

    # ========================================================
    # FIND EVENT AT REQUESTED TIME
    # ========================================================

    matching_events = []

    for event in events:

        event_start = (
            event.get(
                "start",
                {}
            ).get(
                "dateTime"
            )
        )

        if not event_start:
            continue

        try:

            event_start_dt = (
                datetime.fromisoformat(
                    event_start
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            continue

        print(
            "EVENT:",
            event.get(
                "summary",
                "Appointment",
            ),
            "|",
            event_start_dt.isoformat(),
        )

        # Exact requested date/time
        if (
            event_start_dt.date()
            == target_dt.date()
            and
            event_start_dt.hour
            == target_dt.hour
            and
            event_start_dt.minute
            == target_dt.minute
        ):

            matching_events.append(
                event
            )

    # ========================================================
    # NO EXACT MATCH
    # ========================================================

    if not matching_events:

        print(
            "NO EVENT FOUND AT REQUESTED TIME"
        )

        return {
            "cancellation_result": {
                "success": False,
                "error": (
                    "I couldn't find an appointment "
                    "at that time."
                ),
            }
        }

    # ========================================================
    # MATCH
    # ========================================================

    event = matching_events[0]

    print(
        "\nMATCHING EVENT:",
        event,
    )

    return {
        "event_id": event.get(
            "id"
        ),

        "event": event,

        "confirmation_required": True,
    }


# ============================================================
# REQUEST CONFIRMATION
# ============================================================

def request_cancellation_confirmation(
    state: CancellationState
):

    print(
        "\nNODE: request_cancellation_confirmation"
    )

    event = state.get(
        "event",
        {}
    )

    title = event.get(
        "summary",
        "Appointment",
    )

    start = event.get(
        "start",
        {}
    ).get(
        "dateTime"
    )

    final_response = {
        "success": False,
        "needs_confirmation": True,
        "message": (
            f"I found '{title}'"
            + (
                f" at {start}"
                if start
                else ""
            )
            + ". Would you like me to cancel it?"
        ),
    }

    return {
        "final_response": final_response,

        # IMPORTANT:
        # Expose these so agent.py can persist them.
        "event_id": state.get(
            "event_id"
        ),

        "event": state.get(
            "event",
            {}
        ),
    }


# ============================================================
# ROUTE AFTER FIND EVENT
# ============================================================

def route_after_find_event(
    state: CancellationState
):

    if state.get(
        "cancellation_result"
    ):

        return "confirm"

    if state.get(
        "event_id"
    ):

        return "request_confirmation"

    return "confirm"


# ============================================================
# DELETE EVENT
# ============================================================

def cancel_event(
    state: CancellationState
):

    print(
        "\nNODE: cancel_event"
    )

    event_id = state.get(
        "event_id"
    )

    if not event_id:

        return {
            "cancellation_result": {
                "success": False,
                "error": (
                    "No appointment was found "
                    "to cancel."
                ),
            }
        }

    result = delete_event(
        user_id=state["user_id"],
        event_id=event_id,
    )

    print(
        "DELETE RESULT:",
        result
    )

    if result.get("success"):

        return {
            "cancellation_result": {
                "success": True,
                "event_id": event_id,
            }
        }

    return {
        "cancellation_result": {
            "success": False,
            "error": result.get(
                "error",
                "Unable to cancel the appointment.",
            ),
        }
    }


# ============================================================
# CONFIRM
# ============================================================

def confirm(
    state: CancellationState
):

    print(
        "\nNODE: cancellation_confirm"
    )

    result = state.get(
        "cancellation_result"
    )

    if result:

        if result.get("success"):

            final_response = {
                "success": True,
                "message": (
                    "Your appointment has been "
                    "cancelled successfully."
                ),
                "event_id": result.get(
                    "event_id"
                ),
            }

        else:

            final_response = {
                "success": False,
                "message": result.get(
                    "error",
                    "Unable to cancel the appointment.",
                ),
            }

    else:

        final_response = state.get(
            "final_response",
            {
                "success": False,
                "message": (
                    "Unable to process the "
                    "cancellation request."
                ),
            },
        )

    print(
        "FINAL CANCELLATION RESPONSE:",
        final_response
    )

    return {
        "final_response": final_response
    }


# ============================================================
# GRAPH
# ============================================================

graph_builder = StateGraph(
    CancellationState
)


graph_builder.add_node(
    "parse_cancellation_request",
    parse_cancellation_request,
)

graph_builder.add_node(
    "find_cancellation_event",
    find_cancellation_event,
)

graph_builder.add_node(
    "request_confirmation",
    request_cancellation_confirmation,
)

graph_builder.add_node(
    "cancel_event",
    cancel_event,
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
    "parse_cancellation_request",
)

graph_builder.add_edge(
    "parse_cancellation_request",
    "find_cancellation_event",
)

graph_builder.add_conditional_edges(
    "find_cancellation_event",
    route_after_find_event,
    {
        "request_confirmation":
            "request_confirmation",

        "confirm":
            "confirm",
    },
)

graph_builder.add_edge(
    "request_confirmation",
    END,
)

graph_builder.add_edge(
    "cancel_event",
    "confirm",
)

graph_builder.add_edge(
    "confirm",
    END,
)


# ============================================================
# COMPILE
# ============================================================

cancellation_graph = (
    graph_builder.compile()
)