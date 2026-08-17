from backend.workflows.rescheduling_graph import (
    rescheduling_graph,
)


def run_rescheduling_workflow(
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

    result = rescheduling_graph.invoke(
        state
    )

    final_response = result.get(
        "final_response",
        {
            "success": False,
            "message": (
                "Unable to process the "
                "rescheduling request."
            ),
        },
    )

    # --------------------------------------------------------
    # Preserve pending rescheduling information.
    # --------------------------------------------------------

    for key in [
        "event_id",
        "event",
        "old_start",
        "old_end",
        "new_start",
        "new_end",
    ]:

        if result.get(key) is not None:

            final_response[key] = (
                result[key]
            )

    return final_response