import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


INTENT_MODEL = os.getenv(
    "INTENT_MODEL",
    "gpt-4o-mini"
)


def classify_intent(
    user_input: str,
    conversation_history: list | None = None,
) -> str:

    """
    Classify the user's request.

    Returns:

        SCHEDULING
        OTHER

    The classifier uses conversation history so that
    short follow-up messages such as:

        info@weaveapps.com
        yes
        tomorrow
        30 minutes

    can be understood in the context of an ongoing
    scheduling conversation.
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
        model=INTENT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": f"""
You are an intent classifier for an appointment
scheduling assistant.

Return ONLY one of these two values:

SCHEDULING
OTHER

==================================================
CONVERSATION HISTORY
==================================================

{history_text}

==================================================
CURRENT USER MESSAGE
==================================================

{user_input}

==================================================
SCHEDULING
==================================================

SCHEDULING includes requests about:

- booking an appointment
- scheduling a meeting
- checking calendar availability
- checking whether a time is free
- cancelling an appointment
- deleting an appointment
- rescheduling an appointment
- changing an appointment time
- changing an appointment date
- appointment duration
- appointment participants
- adding an attendee
- calendar events
- existing appointments

Also classify the message as SCHEDULING when it is
clearly answering a question from an ongoing scheduling
conversation.

For example:

assistant:
"What email address should I associate with the appointment?"

user:
"info@weaveapps.com"

→ SCHEDULING

Another example:

assistant:
"What time would you prefer?"

user:
"Tomorrow at 3 PM"

→ SCHEDULING

Another example:

assistant:
"What would you like to call the appointment?"

user:
"Project meeting"

→ SCHEDULING

Another example:

assistant:
"Would you like me to book this slot?"

user:
"Yes"

→ SCHEDULING

==================================================
OTHER
==================================================

OTHER includes requests unrelated to appointment
scheduling.

Examples:

"What is the weather today?"

→ OTHER

"Write me a Python program"

→ OTHER

"Tell me a joke"

→ OTHER

"Explain quantum physics"

→ OTHER

==================================================
IMPORTANT
==================================================

Use the conversation history.

A short message by itself may look unrelated to
scheduling.

For example:

"info@weaveapps.com"

would normally be ambiguous.

However, if the previous assistant message asks
for an email address for an appointment, classify
it as:

SCHEDULING

If the request is ambiguous but could reasonably be
part of an appointment scheduling conversation,
classify it as:

SCHEDULING
"""
            },
            {
                "role": "user",
                "content": user_input
            }
        ]
    )

    intent = (
        response
        .choices[0]
        .message
        .content
        .strip()
        .upper()
    )

    if intent not in {
        "SCHEDULING",
        "OTHER",
    }:
        return "OTHER"

    return intent