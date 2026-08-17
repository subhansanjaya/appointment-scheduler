from backend.calendar_service import (
    find_available_slots,
)


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

    print(
        "\n=== AVAILABILITY PARSED REQUEST ==="
    )

    print(
        "User input:",
        user_input,
    )

    print(
        "Window start:",
        parsed.get(
            "window_start"
        ),
    )

    print(
        "Window end:",
        parsed.get(
            "window_end"
        ),
    )

    print(
        "Exact start:",
        parsed.get(
            "exact_start"
        ),
    )

    print(
        "Exact end:",
        parsed.get(
            "exact_end"
        ),
    )

    print(
        "Duration:",
        parsed.get(
            "duration_minutes"
        ),
    )

    print(
        "Needs slot search:",
        parsed.get(
            "needs_slot_search"
        ),
    )

    print(
        "Auto book:",
        parsed.get(
            "auto_book"
        ),
    )

    print(
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

    print(
        "\n=== FINDING AVAILABLE SLOTS ==="
    )

    print(
        "Start:",
        window_start,
    )

    print(
        "End:",
        window_end,
    )

    print(
        "Duration:",
        duration_minutes,
    )

    print(
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

    print(
        "\n=== CALENDAR AVAILABILITY RESULT ==="
    )

    print(
        result
    )

    print(
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