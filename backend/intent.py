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


def classify_intent(user_input: str) -> str:
    """
    Classify the user's request.

    Returns:
        SCHEDULING
        OTHER
    """

    response = client.chat.completions.create(
        model=INTENT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": """
You are an intent classifier for an appointment scheduling assistant.

Return ONLY one of these two values:

SCHEDULING
OTHER

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

Examples:

"Book a meeting tomorrow at 3pm"
SCHEDULING

"Am I free tomorrow afternoon?"
SCHEDULING

"Do I have anything at 10am?"
SCHEDULING

"Cancel my appointment"
SCHEDULING

"Move my meeting to Friday"
SCHEDULING

"Add john@example.com to the meeting"
SCHEDULING

"What is the weather today?"
OTHER

"Write me a Python program"
OTHER

"Tell me a joke"
OTHER

"Explain quantum physics"
OTHER

If the request is ambiguous but could reasonably be part of
an appointment scheduling conversation, classify it as SCHEDULING.
"""
            },
            {
                "role": "user",
                "content": user_input
            }
        ]
    )

    intent = response.choices[0].message.content.strip().upper()

    if intent not in {"SCHEDULING", "OTHER"}:
        return "OTHER"

    return intent