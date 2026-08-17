from unittest.mock import patch

from backend.workflows.booking_graph import (
    route_after_parse,
    route_after_slots,
    route_after_exact_time,
    check_exact_time,
    select_slot,
    book_appointment,
    confirm,
)


# ============================================================
# ROUTING TESTS
# ============================================================

def test_route_to_find_slots():

    state = {
        "needs_slot_search": True
    }

    assert (
        route_after_parse(state)
        == "find_slots"
    )


def test_route_to_exact_time():

    state = {
        "needs_slot_search": False
    }

    assert (
        route_after_parse(state)
        == "check_exact_time"
    )


def test_route_to_select_slot_when_auto_book():

    state = {
        "available_slots": [
            {
                "start": "2026-08-17T14:00:00+05:30",
                "end": "2026-08-17T14:30:00+05:30",
            }
        ],
        "auto_book": True,
    }

    assert (
        route_after_slots(state)
        == "select_slot"
    )


def test_route_to_confirm_when_no_slots():

    state = {
        "available_slots": []
    }

    assert (
        route_after_slots(state)
        == "confirm"
    )


def test_route_to_confirm_when_not_auto_booking():

    state = {
        "available_slots": [
            {
                "start": "2026-08-17T14:00:00+05:30",
                "end": "2026-08-17T14:30:00+05:30",
            }
        ],
        "auto_book": False,
    }

    assert (
        route_after_slots(state)
        == "confirm"
    )


def test_exact_time_available_routes_to_booking():

    state = {
        "selected_slot": {
            "start": "2026-08-17T18:00:00+05:30",
            "end": "2026-08-17T18:30:00+05:30",
        }
    }

    assert (
        route_after_exact_time(state)
        == "book_appointment"
    )


def test_exact_time_unavailable_routes_to_confirm():

    state = {
        "selected_slot": None
    }

    assert (
        route_after_exact_time(state)
        == "confirm"
    )


# ============================================================
# EXACT TIME CHECK
# ============================================================

def test_check_exact_time_available():

    state = {
        "user_id": 1,
        "exact_start":
            "2026-08-17T18:00:00+05:30",
        "exact_end":
            "2026-08-17T18:30:00+05:30",
    }

    mock_result = {
        "available": True,
        "start":
            "2026-08-17T18:00:00+05:30",
        "end":
            "2026-08-17T18:30:00+05:30",
        "events": [],
    }

    with patch(
        "backend.workflows.booking_graph.check_availability",
        return_value=mock_result,
    ):

        result = check_exact_time(
            state
        )

    assert result["selected_slot"] == {
        "start":
            "2026-08-17T18:00:00+05:30",
        "end":
            "2026-08-17T18:30:00+05:30",
    }


def test_check_exact_time_unavailable():

    state = {
        "user_id": 1,
        "exact_start":
            "2026-08-17T17:00:00+05:30",
        "exact_end":
            "2026-08-17T17:30:00+05:30",
    }

    mock_result = {
        "available": False,
        "start":
            "2026-08-17T17:00:00+05:30",
        "end":
            "2026-08-17T17:30:00+05:30",
        "events": [
            {
                "id": "existing-event",
                "summary":
                    "Existing Appointment",
            }
        ],
    }

    with patch(
        "backend.workflows.booking_graph.check_availability",
        return_value=mock_result,
    ):

        result = check_exact_time(
            state
        )

    assert (
        result["selected_slot"]
        is None
    )

    assert (
        result["booking_result"]["success"]
        is False
    )

    assert (
        result["booking_result"]["error"]
        == "The requested time is not available."
    )


def test_check_exact_time_calendar_error():

    state = {
        "user_id": 1,
        "exact_start":
            "2026-08-17T17:00:00+05:30",
        "exact_end":
            "2026-08-17T17:30:00+05:30",
    }

    mock_result = {
        "error":
            "Google Calendar API failed"
    }

    with patch(
        "backend.workflows.booking_graph.check_availability",
        return_value=mock_result,
    ):

        result = check_exact_time(
            state
        )

    assert (
        result["booking_result"]["success"]
        is False
    )

    assert (
        result["booking_result"]["error"]
        == "Google Calendar API failed"
    )


# ============================================================
# SLOT SELECTION
# ============================================================

def test_select_slot_selects_first_available_slot():

    state = {
        "available_slots": [
            {
                "start":
                    "2026-08-17T14:00:00+05:30",
                "end":
                    "2026-08-17T14:30:00+05:30",
            },
            {
                "start":
                    "2026-08-17T14:30:00+05:30",
                "end":
                    "2026-08-17T15:00:00+05:30",
            },
        ]
    }

    result = select_slot(
        state
    )

    assert (
        result["selected_slot"]
        == {
            "start":
                "2026-08-17T14:00:00+05:30",
            "end":
                "2026-08-17T14:30:00+05:30",
        }
    )


def test_select_slot_when_no_slots():

    state = {
        "available_slots": []
    }

    result = select_slot(
        state
    )

    assert (
        result["selected_slot"]
        is None
    )


# ============================================================
# BOOKING
# ============================================================

def test_book_appointment_success():

    state = {
        "user_id": 1,
        "title": "Test Appointment",
        "email": "info@weaveapps.com",
        "selected_slot": {
            "start":
                "2026-08-17T18:00:00+05:30",
            "end":
                "2026-08-17T18:30:00+05:30",
        },
    }

    mock_result = {
        "success": True,
        "event_id": "test-event-123",
        "link":
            "https://calendar.google.com/test",
        "status": "confirmed",
    }

    with patch(
        "backend.workflows.booking_graph.create_event",
        return_value=mock_result,
    ):

        result = book_appointment(
            state
        )

    assert (
        result["booking_result"]
        == mock_result
    )


def test_book_appointment_when_no_selected_slot():

    state = {
        "user_id": 1,
        "title": "Test Appointment",
        "email": "info@weaveapps.com",
        "selected_slot": None,
    }

    result = book_appointment(
        state
    )

    assert (
        result["booking_result"]["success"]
        is False
    )

    assert (
        result["booking_result"]["error"]
        == "No available slot was found."
    )


# ============================================================
# CONFIRMATION
# ============================================================

def test_confirm_successful_booking():

    state = {
        "booking_result": {
            "success": True,
            "event_id": "test-event-123",
            "link":
                "https://calendar.google.com/test",
            "status": "confirmed",
        },
        "selected_slot": {
            "start":
                "2026-08-17T18:00:00+05:30",
            "end":
                "2026-08-17T18:30:00+05:30",
        },
    }

    result = confirm(
        state
    )

    response = result[
        "final_response"
    ]

    assert (
        response["success"]
        is True
    )

    assert (
        response["event_id"]
        == "test-event-123"
    )

    assert (
        response["link"]
        == "https://calendar.google.com/test"
    )

    assert (
        response["start"]
        == "2026-08-17T18:00:00+05:30"
    )

    assert (
        response["end"]
        == "2026-08-17T18:30:00+05:30"
    )


def test_confirm_failed_booking():

    state = {
        "booking_result": {
            "success": False,
            "error":
                "The requested time is not available.",
        }
    }

    result = confirm(
        state
    )

    response = result[
        "final_response"
    ]

    assert (
        response["success"]
        is False
    )

    assert (
        response["message"]
        == "The requested time is not available."
    )


def test_confirm_available_slots():

    state = {
        "available_slots": [
            {
                "start":
                    "2026-08-17T14:00:00+05:30",
                "end":
                    "2026-08-17T14:30:00+05:30",
            },
            {
                "start":
                    "2026-08-17T15:00:00+05:30",
                "end":
                    "2026-08-17T15:30:00+05:30",
            },
        ]
    }

    result = confirm(
        state
    )

    response = result[
        "final_response"
    ]

    assert (
        response["success"]
        is True
    )

    assert (
        response["slots"]
        == state["available_slots"]
    )


def test_confirm_no_available_slots():

    state = {
        "available_slots": []
    }

    result = confirm(
        state
    )

    response = result[
        "final_response"
    ]

    assert (
        response["success"]
        is False
    )

    assert (
        response["message"]
        == "No available appointment slots "
           "were found."
    )