from unittest.mock import patch

from backend.action_classifier import (
    classify_action,
)


def test_classify_book():

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "BOOK"
                }
            }
        ]
    }

    with patch(
        "backend.action_classifier.client.chat.completions.create"
    ) as mock:

        mock.return_value.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {
                            "content": "BOOK"
                        },
                    )()
                },
            )()
        ]

        result = classify_action(
            "Book an appointment tomorrow at 7 PM"
        )

    assert result == "BOOK"


def test_classify_availability():

    with patch(
        "backend.action_classifier.client.chat.completions.create"
    ) as mock:

        mock.return_value.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {
                            "content":
                                "CHECK_AVAILABILITY"
                        },
                    )()
                },
            )()
        ]

        result = classify_action(
            "Show me available slots tomorrow"
        )

    assert result == "CHECK_AVAILABILITY"


def test_classify_cancel():

    with patch(
        "backend.action_classifier.client.chat.completions.create"
    ) as mock:

        mock.return_value.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {
                            "content": "CANCEL"
                        },
                    )()
                },
            )()
        ]

        result = classify_action(
            "Cancel my appointment tomorrow"
        )

    assert result == "CANCEL"


def test_classify_reschedule():

    with patch(
        "backend.action_classifier.client.chat.completions.create"
    ) as mock:

        mock.return_value.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {
                            "content": "RESCHEDULE"
                        },
                    )()
                },
            )()
        ]

        result = classify_action(
            "Move my appointment to 8 PM"
        )

    assert result == "RESCHEDULE"