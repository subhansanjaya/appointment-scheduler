from backend.workflows.booking_graph import (
    booking_graph,
)


def run_booking_workflow(
    user_id: int,
    user_input: str,
    conversation_history: list | None = None,
):

    state = {
        "user_id": user_id,
        "user_input": user_input,
        "conversation_history": (
            conversation_history or []
        ),
    }

    result = booking_graph.invoke(
        state
    )

    return result.get(
        "final_response",
        {
            "success": False,
            "message": (
                "Unable to process the "
                "booking request."
            ),
        },
    )