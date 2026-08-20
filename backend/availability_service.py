import logging

from backend.calendar_service import (
    find_available_slots,
)
from backend.logging_utils import log_debug


logger = logging.getLogger(__name__)


def run_availability_workflow(
    user_id: int,
    user_input: str,
    conversation_history: list | None = None,
):
    """
    Handle availability-only requests.

    Email is not required because this workflow
    only checks availability.

    Conversation history is passed to the parser
    so follow-up requests such as:

        "How about 7 PM?"

    can reuse the date from the previous request.
    """

    from backend.workflows.booking_graph import (
        parse_request,
    )

    # ========================================================
    # CONVERSATION HISTORY
    # ========================================================

    conversation_history = (
        conversation_history or []
    )

    state = {
        "user_id": user_id,
        "user_input": user_input,
        "conversation_history": (
            conversation_history
        ),
    }

    # ========================================================
    # PARSE REQUEST
    # ========================================================

    parsed = parse_request(
        state
    )

    log_debug(logger,
        "\n=== AVAILABILITY PARSED REQUEST ==="
    )

    log_debug(logger,
        "User input:",
        user_input,
    )

    log_debug(logger,
        "Window start:",
        parsed.get(
            "window_start"
        ),
    )

    log_debug(logger,
        "Window end:",
        parsed.get(
            "window_end"
        ),
    )

    log_debug(logger,
        "Exact start:",
        parsed.get(
            "exact_start"
        ),
    )

    log_debug(logger,
        "Exact end:",
        parsed.get(
            "exact_end"
        ),
    )

    log_debug(logger,
        "Duration:",
        parsed.get(
            "duration_minutes"
        ),
    )

    log_debug(logger,
        "Needs slot search:",
        parsed.get(
            "needs_slot_search"
        ),
    )

    log_debug(logger,
        "Auto book:",
        parsed.get(
            "auto_book"
        ),
    )

    log_debug(logger,
        "===================================\n"
    )

    # ========================================================
    # EXTRACT PARAMETERS
    # ========================================================

    window_start = parsed.get(
        "window_start"
    )

    window_end = parsed.get(
        "window_end"
    )

    duration_minutes = parsed.get(
        "duration_minutes",
        30,
    )

    title = parsed.get(
        "title",
        "Appointment",
    )

    # ========================================================
    # VALIDATE
    # ========================================================

    if not window_start or not window_end:

        return {
            "success": False,

            "message": (
                "Please provide a date and "
                "time range so I can check availability."
            ),

            "slots": [],

            "window_start": (
                window_start
            ),

            "window_end": (
                window_end
            ),

            "duration_minutes": (
                duration_minutes
            ),

            "title": title,
        }

    # ========================================================
    # FIND AVAILABLE SLOTS
    # ========================================================

    log_debug(logger,
        "\n=== FINDING AVAILABLE SLOTS ==="
    )

    log_debug(logger,
        "Start:",
        window_start,
    )

    log_debug(logger,
        "End:",
        window_end,
    )

    log_debug(logger,
        "Duration:",
        duration_minutes,
    )

    log_debug(logger,
        "================================\n"
    )

    result = find_available_slots(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        duration_minutes=duration_minutes,
    )

    # ========================================================
    # CALENDAR RESULT
    # ========================================================

    log_debug(logger,
        "\n=== CALENDAR AVAILABILITY RESULT ==="
    )

    log_debug(logger,
        result
    )

    log_debug(logger,
        "====================================\n"
    )

    # ========================================================
    # CALENDAR ERROR
    # ========================================================

    if not result.get(
        "success"
    ):

        return {
            "success": False,

            "message": result.get(
                "error",
                "Unable to check availability.",
            ),

            "slots": [],

            "window_start": (
                window_start
            ),

            "window_end": (
                window_end
            ),

            "duration_minutes": (
                duration_minutes
            ),

            "title": title,
        }

    # ========================================================
    # EXTRACT SLOTS
    # ========================================================

    slots = result.get(
        "available_slots",
        []
    )

    # ========================================================
    # NO SLOTS
    # ========================================================

    if not slots:

        return {
            "success": False,

            "message": (
                "No available appointment "
                "slots were found."
            ),

            "slots": [],

            "window_start": (
                window_start
            ),

            "window_end": (
                window_end
            ),

            "duration_minutes": (
                duration_minutes
            ),

            "title": title,
        }

    # ========================================================
    # SUCCESS
    # ========================================================

    return {
        "success": True,

        "message": (
            "Available appointment slots "
            "were found."
        ),

        "slots": slots,

        "window_start": (
            window_start
        ),

        "window_end": (
            window_end
        ),

        "duration_minutes": (
            duration_minutes
        ),

        "title": title,
    }