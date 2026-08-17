from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.calendar_service import (
    find_available_slots,
)

from backend.workflows.booking_graph import (
    booking_graph,
)


# ============================================================
# END-TO-END BOOKING TEST
# ============================================================

def test_booking_graph_end_to_end():

    timezone = ZoneInfo(
        "Asia/Colombo"
    )

    tomorrow = (
        datetime.now(timezone)
        + timedelta(days=1)
    ).date()

    window_start = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        12,
        0,
        tzinfo=timezone,
    )

    window_end = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        17,
        0,
        tzinfo=timezone,
    )

    # ========================================================
    # FIND A REAL AVAILABLE SLOT
    # ========================================================

    availability = find_available_slots(
        user_id=1,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        duration_minutes=30,
    )

    print(
        "\n=== INTEGRATION AVAILABILITY ==="
    )

    print(
        availability
    )

    print(
        "================================\n"
    )

    assert availability.get(
        "success"
    ) is True

    slots = availability.get(
        "available_slots",
        []
    )

    # --------------------------------------------------------
    # The real calendar may simply be fully booked.
    # That is not a booking-graph failure.
    # --------------------------------------------------------

    if not slots:

        pytest.skip(
            "No 30-minute slots are currently "
            "available tomorrow afternoon."
        )

    # ========================================================
    # SELECT FIRST REAL SLOT
    # ========================================================

    selected_slot = slots[0]

    start = datetime.fromisoformat(
        selected_slot["start"]
    )

    end = datetime.fromisoformat(
        selected_slot["end"]
    )

    # ========================================================
    # BUILD USER REQUEST
    # ========================================================

    date_text = start.strftime(
        "%A"
    )

    time_text = start.strftime(
        "%-I:%M %p"
    )

    user_input = (
        f"Book a 30-minute appointment "
        f"tomorrow at {time_text} "
        f"for info@weaveapps.com"
    )

    print(
        "\n=== SELECTED TEST SLOT ==="
    )

    print(
        selected_slot
    )

    print(
        "USER INPUT:",
        user_input,
    )

    print(
        "===========================\n"
    )

    # ========================================================
    # RUN REAL BOOKING GRAPH
    # ========================================================

    state = {
        "user_id": 1,
        "user_input": user_input,
    }

    result = booking_graph.invoke(
        state
    )

    print(
        "\n=== FINAL RESPONSE ==="
    )

    print(
        result["final_response"]
    )

    print(
        "======================\n"
    )

    # ========================================================
    # ASSERT BOOKING
    # ========================================================

    assert (
        result["final_response"]["success"]
        is True
    )

    assert (
        result["final_response"]["event_id"]
        is not None
    )