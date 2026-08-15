import json
from sqlalchemy.orm import Session
from backend.models import Conversation, Message


def get_or_create_conversation(
    db: Session,
    user_id: int,
) -> Conversation:

    conversation = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .first()
    )

    if not conversation:
        conversation = Conversation(user_id=user_id)

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    return conversation


def get_messages(
    db: Session,
    conversation_id: int,
):

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    result = []

    for message in messages:
        # ---------------------------------
        # ASSISTANT TOOL CALL
        # ---------------------------------

        if message.role == "assistant":
            try:
                content = json.loads(message.content)

                if "tool_calls" in content:
                    result.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": content["tool_calls"],
                        }
                    )

                    continue

            except json.JSONDecodeError:
                pass

        # ---------------------------------
        # TOOL RESULT
        # ---------------------------------

        if message.role == "tool":
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content,
                }
            )

            continue

        # ---------------------------------
        # NORMAL MESSAGE
        # ---------------------------------

        result.append(
            {
                "role": message.role,
                "content": message.content,
            }
        )

    return result


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
