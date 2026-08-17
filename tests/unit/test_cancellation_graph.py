from unittest.mock import patch

from backend.workflows.cancellation_graph import (
    parse_cancellation_request,
    find_cancellation_event,
    request_cancellation_confirmation,
    cancel_event,
    confirm,
)


def test_find_cancellation_event_success():

    state = {
        "user_id": 1,
        "window_start": "2026-08-17T19:00:00+05:30",
        "window_end": "2026-08-17T19:30:00+05:30",
    }

    mock_result = {
        "success": True,
        "events": [
            {
                "id": "event-123",
                "summary": "Test Appointment",
                "start": {
                    "dateTime":
                        "2026-08-17T19:00:00+05:30"
                },
                "end": {
                    "dateTime":
                        "2026-08-17T19:30:00+05:30"
                },
            }
        ],
    }

    with patch(
        "backend.workflows.cancellation_graph.find_events",
        return_value=mock_result,
    ):

        result = find_cancellation_event(state)

    assert result["event_id"] == "event-123"

    assert (
        result["event"]["summary"]
        == "Test Appointment"
    )

    assert (
        result["confirmation_required"]
        is True
    )


def test_find_cancellation_event_not_found():

    state = {
        "user_id": 1,
        "window_start": "2026-08-17T19:00:00+05:30",
        "window_end": "2026-08-17T19:30:00+05:30",
    }

    mock_result = {
        "success": True,
        "events": [],
    }

    with patch(
        "backend.workflows.cancellation_graph.find_events",
        return_value=mock_result,
    ):

        result = find_cancellation_event(state)

    assert (
        result["cancellation_result"]["success"]
        is False
    )

    assert (
        "couldn't find"
        in result["cancellation_result"]["error"]
    )


def test_find_cancellation_event_calendar_error():

    state = {
        "user_id": 1,
        "window_start": "2026-08-17T19:00:00+05:30",
        "window_end": "2026-08-17T19:30:00+05:30",
    }

    mock_result = {
        "success": False,
        "error": "Google Calendar API failed",
    }

    with patch(
        "backend.workflows.cancellation_graph.find_events",
        return_value=mock_result,
    ):

        result = find_cancellation_event(state)

    assert (
        result["cancellation_result"]["success"]
        is False
    )

    assert (
        result["cancellation_result"]["error"]
        == "Google Calendar API failed"
    )


def test_request_cancellation_confirmation():

    state = {
        "event": {
            "id": "event-123",
            "summary": "Test Appointment",
            "start": {
                "dateTime":
                    "2026-08-17T19:00:00+05:30"
            },
        }
    }

    result = request_cancellation_confirmation(
        state
    )

    response = result["final_response"]

    assert (
        response["needs_confirmation"]
        is True
    )

    assert (
        "Test Appointment"
        in response["message"]
    )


def test_cancel_event_success():

    state = {
        "user_id": 1,
        "event_id": "event-123",
    }

    mock_result = {
        "success": True,
    }

    with patch(
        "backend.workflows.cancellation_graph.delete_event",
        return_value=mock_result,
    ):

        result = cancel_event(state)

    assert (
        result["cancellation_result"]["success"]
        is True
    )

    assert (
        result["cancellation_result"]["event_id"]
        == "event-123"
    )


def test_cancel_event_failure():

    state = {
        "user_id": 1,
        "event_id": "event-123",
    }

    mock_result = {
        "success": False,
        "error": "Google Calendar API failed",
    }

    with patch(
        "backend.workflows.cancellation_graph.delete_event",
        return_value=mock_result,
    ):

        result = cancel_event(state)

    assert (
        result["cancellation_result"]["success"]
        is False
    )

    assert (
        result["cancellation_result"]["error"]
        == "Google Calendar API failed"
    )


def test_cancel_event_without_event_id():

    state = {
        "user_id": 1,
        "event_id": None,
    }

    result = cancel_event(state)

    assert (
        result["cancellation_result"]["success"]
        is False
    )


def test_confirm_successful_cancellation():

    state = {
        "cancellation_result": {
            "success": True,
            "event_id": "event-123",
        }
    }

    result = confirm(state)

    response = result["final_response"]

    assert response["success"] is True

    assert (
        response["event_id"]
        == "event-123"
    )

    assert (
        "cancelled"
        in response["message"]
    )


def test_confirm_failed_cancellation():

    state = {
        "cancellation_result": {
            "success": False,
            "error":
                "Unable to cancel the appointment.",
        }
    }

    result = confirm(state)

    response = result["final_response"]

    assert response["success"] is False

    assert (
        response["message"]
        == "Unable to cancel the appointment."
    )