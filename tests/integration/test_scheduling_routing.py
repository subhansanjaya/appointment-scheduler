from unittest.mock import patch

from backend.workflows.scheduling_service import (
    run_scheduling_workflow,
)

def test_book_routes_to_booking():

    with patch(
        "backend.workflows.scheduling_service.run_booking_workflow"
    ) as mock_booking:

        mock_booking.return_value = {
            "success": True,
            "message": "Booking successful",
        }

        result = run_scheduling_workflow(
            user_id=1,
            user_input=(
                "Book an appointment tomorrow"
            ),
            action="BOOK",
        )

        mock_booking.assert_called_once()

        assert result["success"] is True


def test_availability_routes_correctly():

    with patch(
        "backend.workflows.scheduling_service.run_availability_workflow"
    ) as mock_availability:

        mock_availability.return_value = {
            "success": True,
            "message": "Available slots found",
        }

        result = run_scheduling_workflow(
            user_id=1,
            user_input=(
                "Show me available slots tomorrow"
            ),
            action="CHECK_AVAILABILITY",
        )

        mock_availability.assert_called_once()

        assert result["success"] is True


def test_cancel_routes_correctly():

    with patch(
        "backend.workflows.scheduling_service.run_cancellation_workflow"
    ) as mock_cancel:

        mock_cancel.return_value = {
            "success": True,
            "message": "Cancellation started",
        }

        result = run_scheduling_workflow(
            user_id=1,
            user_input=(
                "Cancel my appointment tomorrow"
            ),
            action="CANCEL",
        )

        mock_cancel.assert_called_once()

        assert result["success"] is True