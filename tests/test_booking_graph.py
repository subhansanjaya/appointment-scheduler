from backend.workflows.booking_graph import booking_graph

from unittest.mock import patch
USER_ID = 1
EMAIL = "info@weaveapps.com"


def test_exact_time_unavailable():

    state = {
        "user_id": USER_ID,
        "user_input": (
            "Book a test appointment tomorrow at 5 PM "
            "for 30 minutes at info@weaveapps.com"
        ),
    }

    result = booking_graph.invoke(state)

    print("\n=== EXACT TIME UNAVAILABLE ===")
    print(result["final_response"])

    assert result["final_response"]["success"] is False


def test_exact_time_available():

    state = {
        "user_id": USER_ID,
        "user_input": (
            "Book a test appointment tomorrow at 9 PM "
            "for 30 minutes at info@weaveapps.com"
        ),
    }

    mock_availability = {
        "available": True,
        "start": "2026-08-17T21:00:00+05:30",
        "end": "2026-08-17T21:30:00+05:30",
        "events": [],
    }

    with patch(
        "backend.workflows.booking_graph.check_availability",
        return_value=mock_availability,
    ):

        result = booking_graph.invoke(state)

    print("\n=== EXACT TIME AVAILABLE ===")
    print(result["final_response"])

    assert result["final_response"]["success"] is True