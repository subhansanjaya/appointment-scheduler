from datetime import datetime

from backend.workflows.booking_service import (
    run_booking_workflow,
)

from backend.availability_service import (
    run_availability_workflow,
)

from backend.workflows.cancellation_service import (
    run_cancellation_workflow,
)

from backend.workflows.rescheduling_service import (
    run_rescheduling_workflow,
)



# ============================================================
# FIND SLOT FROM USER INPUT
# ============================================================

def find_selected_slot(
    user_input: str,
    slots: list,
):
    """
    Match a user's selection against previously
    returned availability slots.

    Supports:

        7:30 PM
        19:30
        first
        second
        third
    """

    if not slots:
        return None

    text = user_input.strip().lower()

    # --------------------------------------------------------
    # Position selection
    # --------------------------------------------------------

    positions = {
        "first": 0,
        "1": 0,
        "second": 1,
        "2": 1,
        "third": 2,
        "3": 2,
        "fourth": 3,
        "4": 3,
        "fifth": 4,
        "5": 4,
    }

    for word, index in positions.items():

        if text == word:

            if index < len(slots):
                return slots[index]

    # --------------------------------------------------------
    # Time selection
    # --------------------------------------------------------

    for slot in slots:

        try:

            start = datetime.fromisoformat(
                slot["start"]
            )

            time_12 = start.strftime(
                "%I:%M %p"
            ).lstrip("0").lower()

            time_24 = start.strftime(
                "%H:%M"
            )

            if (
                time_12 in text
                or time_24 in text
            ):

                return slot

        except (
            KeyError,
            ValueError,
            TypeError,
        ):

            continue

    return None


# ============================================================
# SCHEDULING WORKFLOW
# ============================================================

def run_scheduling_workflow(
    user_id: int,
    user_input: str,
    action: str,
    conversation_history: list | None = None,
    workflow_state: dict | None = None,
):

    conversation_history = (
        conversation_history or []
    )

    workflow_state = (
        workflow_state or {}
    )

    print(
        "\n=== SCHEDULING WORKFLOW ==="
    )

    print(
        "ACTION:",
        action,
    )

    print(
        "WORKFLOW STATE:",
        workflow_state,
    )

    print(
        "============================\n"
    )

    # ========================================================
    # BOOK
    # ========================================================

    if action == "BOOK":

        return run_booking_workflow(
            user_id=user_id,
            user_input=user_input,
            conversation_history=conversation_history,
        )

    # ========================================================
    # CHECK AVAILABILITY
    # ========================================================

    if action == "CHECK_AVAILABILITY":

        return run_availability_workflow(
            user_id=user_id,
            user_input=user_input,
            conversation_history=conversation_history,
        )

    # ========================================================
    # SELECT SLOT
    # ========================================================

    if action == "SELECT_SLOT":

        slots = workflow_state.get(
            "available_slots",
            []
        )

        selected_slot = find_selected_slot(
            user_input=user_input,
            slots=slots,
        )

        if not selected_slot:

            return {
                "success": False,
                "message": (
                    "I couldn't identify that "
                    "appointment slot. Please choose "
                    "one of the available times."
                ),
            }

        return {
            "success": True,
            "selected_slot": selected_slot,
            "message": (
                "That slot is available."
            ),
            "needs_email": not bool(
                workflow_state.get("email")
            ),
        }

    # ========================================================
    # CANCEL
    # ========================================================

    if action == "CANCEL":

        return run_cancellation_workflow(
            user_id=user_id,
            user_input=user_input,
            conversation_history=conversation_history,
        )

    # ========================================================
    # RESCHEDULE
    # ========================================================

    if action == "RESCHEDULE":

        return run_rescheduling_workflow(
            user_id=user_id,
            user_input=user_input,
            conversation_history=conversation_history,
        )
    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

    return {
        "success": False,
        "message": (
            "I couldn't determine the scheduling "
            "action you want to perform."
        ),
    }