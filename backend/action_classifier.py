import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


ACTION_MODEL = os.getenv(
    "ACTION_MODEL",
    "gpt-4o-mini"
)


VALID_ACTIONS = {
    "BOOK",
    "CHECK_AVAILABILITY",
    "CANCEL",
    "RESCHEDULE",
}


def classify_action(
    user_input: str,
    conversation_history: list | None = None,
) -> str:

    """
    Determine what scheduling action the user wants.

    Returns one of:

        BOOK
        CHECK_AVAILABILITY
        CANCEL
        RESCHEDULE
    """

    conversation_history = (
        conversation_history or []
    )

    history_lines = []

    for message in conversation_history:

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        history_lines.append(
            f"{role}: {content}"
        )

    history_text = "\n".join(
        history_lines
    )

    response = client.chat.completions.create(
        model=ACTION_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": f"""
You are an action classifier for an appointment
scheduling assistant.

Return ONLY ONE of:

BOOK
CHECK_AVAILABILITY
CANCEL
RESCHEDULE

==================================================
CONVERSATION HISTORY
==================================================

{history_text}

==================================================
CURRENT USER MESSAGE
==================================================

{user_input}

==================================================
BOOK
==================================================

Use BOOK when the user wants to create a new
appointment.

Examples:

"Book a meeting tomorrow at 3 PM"

"Make an appointment tomorrow"

"Schedule a 30 minute meeting"

"Find me a slot tomorrow and book it"

==================================================
CHECK_AVAILABILITY
==================================================

Use CHECK_AVAILABILITY when the user only wants
to know what times are available.

Examples:

"What times are available tomorrow?"

"Show me available slots around 7 PM"

"Am I free tomorrow afternoon?"

"Do I have anything at 10 AM?"

"Show me available appointment slots"

If the user asks for available times but does NOT
explicitly ask to book one, use CHECK_AVAILABILITY.

==================================================
CANCEL
==================================================

Use CANCEL when the user wants to cancel or delete
an existing appointment.

Examples:

"Cancel my appointment"

"Delete my meeting tomorrow"

"Cancel my appointment tomorrow at 7 PM"

"I don't want the meeting anymore"

==================================================
RESCHEDULE
==================================================

Use RESCHEDULE when the user wants to move an
existing appointment to another date or time.

Examples:

"Move my appointment to 8 PM"

"Reschedule tomorrow's meeting to Friday"

"Change my meeting from 7 PM to 8 PM"

==================================================
CONVERSATIONAL FOLLOW-UPS
==================================================

Use the conversation history.

Short messages can be follow-ups.

For example:

assistant:
"What email address should I associate with the appointment?"

user:
"info@weaveapps.com"

→ BOOK

Another example:

assistant:
"Here are the available slots."

user:
"Show me"

→ CHECK_AVAILABILITY

Another example:

assistant:
"I found your appointment. Would you like me to cancel it?"

user:
"Yes"

→ CANCEL

Another example:

assistant:
"What time would you like to move it to?"

user:
"8 PM"

→ RESCHEDULE

If the current message is ambiguous but clearly
continues an existing scheduling conversation,
use the action from the previous scheduling context.
"""
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
    )

    action = (
        response
        .choices[0]
        .message
        .content
        .strip()
        .upper()
    )

    if action not in VALID_ACTIONS:
        return "BOOK"

    return action