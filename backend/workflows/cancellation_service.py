from backend.workflows.cancellation_graph import (
    cancellation_graph,
)


def run_cancellation_workflow(
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

    result = cancellation_graph.invoke(
        state
    )

    final_response = result.get(
        "final_response",
        {
            "success": False,
            "message": (
                "Unable to process the "
                "cancellation request."
            ),
        },
    )

    # --------------------------------------------------------
    # Preserve event information for confirmation state.
    # --------------------------------------------------------

    if result.get("event_id"):

        final_response[
            "event_id"
        ] = result.get(
            "event_id"
        )

    if result.get("event"):

        final_response[
            "event"
        ] = result.get(
            "event"
        )

    return final_response