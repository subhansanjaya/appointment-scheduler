import json

from sqlalchemy.orm import Session

from backend.models import (
    Conversation,
    Message,
)


# ============================================================
# CONVERSATION
# ============================================================

def get_or_create_conversation(
    db: Session,
    user_id: int,
) -> Conversation:

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == user_id
        )
        .order_by(
            Conversation.created_at.desc()
        )
        .first()
    )

    if not conversation:

        conversation = Conversation(
            user_id=user_id
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    return conversation


# ============================================================
# GET MESSAGES
# ============================================================

def get_messages(
    db: Session,
    conversation_id: int,
):

    messages = (
        db.query(Message)
        .filter(
            Message.conversation_id
            == conversation_id
        )
        .order_by(
            Message.created_at.asc()
        )
        .all()
    )

    result = []

    for message in messages:

        # ----------------------------------------------------
        # WORKFLOW STATE
        #
        # Workflow state is internal application state.
        # Do NOT send it to the LLM as a chat message.
        # ----------------------------------------------------

        if message.role == "workflow_state":

            continue

        # ----------------------------------------------------
        # ASSISTANT TOOL CALL
        # ----------------------------------------------------

        if message.role == "assistant":

            try:

                content = json.loads(
                    message.content
                )

                if "tool_calls" in content:

                    result.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": (
                                content[
                                    "tool_calls"
                                ]
                            ),
                        }
                    )

                    continue

            except (
                json.JSONDecodeError,
                TypeError,
            ):

                pass

        # ----------------------------------------------------
        # TOOL RESULT
        # ----------------------------------------------------

        if message.role == "tool":

            result.append(
                {
                    "role": "tool",
                    "tool_call_id": (
                        message.tool_call_id
                    ),
                    "content": message.content,
                }
            )

            continue

        # ----------------------------------------------------
        # NORMAL MESSAGE
        # ----------------------------------------------------

        result.append(
            {
                "role": message.role,
                "content": message.content,
            }
        )

    return result


# ============================================================
# SAVE MESSAGE
# ============================================================

def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    tool_call_id: str | None = None,
):

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_call_id=tool_call_id,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


# ============================================================
# SAVE WORKFLOW STATE
# ============================================================

def save_workflow_state(
    db: Session,
    conversation_id: int,
    state: dict,
):

    """
    Save internal scheduling workflow state.

    This state is intentionally NOT returned by
    get_messages(), because it should not be sent
    to the LLM as a normal conversation message.

    Example:

    {
        "action": "CHECK_AVAILABILITY",
        "available_slots": [...],
        "duration_minutes": 30,
        "window_start": "...",
        "window_end": "...",
        "email": null,
        "title": "Appointment"
    }
    """

    # --------------------------------------------------------
    # Remove previous workflow state
    #
    # We only need the latest pending state.
    # --------------------------------------------------------

    (
        db.query(Message)
        .filter(
            Message.conversation_id
            == conversation_id,
            Message.role
            == "workflow_state",
        )
        .delete(
            synchronize_session=False
        )
    )

    # --------------------------------------------------------
    # Save latest state
    # --------------------------------------------------------

    message = Message(
        conversation_id=conversation_id,
        role="workflow_state",
        content=json.dumps(
            state
        ),
        tool_call_id=None,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


# ============================================================
# GET WORKFLOW STATE
# ============================================================

def get_workflow_state(
    db: Session,
    conversation_id: int,
):

    """
    Return the latest internal workflow state.

    Returns:
        dict | None
    """

    message = (
        db.query(Message)
        .filter(
            Message.conversation_id
            == conversation_id,
            Message.role
            == "workflow_state",
        )
        .order_by(
            Message.created_at.desc()
        )
        .first()
    )

    if not message:

        return None

    try:

        return json.loads(
            message.content
        )

    except (
        json.JSONDecodeError,
        TypeError,
    ):

        return None


# ============================================================
# CLEAR WORKFLOW STATE
# ============================================================

def clear_workflow_state(
    db: Session,
    conversation_id: int,
):

    """
    Remove pending workflow state after the
    workflow has been completed.
    """

    (
        db.query(Message)
        .filter(
            Message.conversation_id
            == conversation_id,
            Message.role
            == "workflow_state",
        )
        .delete(
            synchronize_session=False
        )
    )

    db.commit()