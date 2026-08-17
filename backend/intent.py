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
        RAG
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
You are the intent classifier for an appointment
scheduling assistant.

The assistant has ONLY three supported request types:

1. SCHEDULING
2. RAG
3. OTHER

Return ONLY one of:

SCHEDULING
RAG
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

Use SCHEDULING for requests related to appointments,
calendar events, or an ongoing scheduling conversation.

Examples:

"Book an appointment tomorrow at 5 PM"
→ SCHEDULING

"Find me an available slot tomorrow"
→ SCHEDULING

"Is 3 PM available?"
→ SCHEDULING

"Cancel my appointment"
→ SCHEDULING

"Reschedule my appointment"
→ SCHEDULING

"What time would you prefer?"
User: "Tomorrow at 3 PM"
→ SCHEDULING

If the user is clearly answering an assistant question
from an ongoing scheduling conversation, use SCHEDULING.

Example:

assistant:
"What email address should I associate with the appointment?"

user:
"info@weaveapps.com"

→ SCHEDULING

Example:

assistant:
"What time would you prefer?"

user:
"Tomorrow at 3 PM"

→ SCHEDULING

Example:

assistant:
"Would you like me to book this slot?"

user:
"Yes"

→ SCHEDULING

==================================================
RAG
==================================================

Use RAG when the user is asking a question that should
be answered using the application's connected knowledge
base, policies, documentation, or business information.

Examples:

"What is the cancellation policy?"
→ RAG

"What is the rescheduling policy?"
→ RAG

"What are the appointment rules?"
→ RAG

"How late can I cancel?"
→ RAG

"How early should I book?"
→ RAG

"What is the default appointment duration?"
→ RAG

"Is an email required for booking?"
→ RAG

"What are your working hours?"
→ RAG

"Tell me about your booking policy."
→ RAG

Only classify as RAG when the question is related to
information that the application's knowledge base is
intended to answer.

==================================================
OTHER
==================================================

Use OTHER for questions unrelated to appointment
scheduling and unrelated to the application's
knowledge base.

Examples:

"Who is the Prime Minister of Sri Lanka?"
→ OTHER

"What is the weather today?"
→ OTHER

"Write me a Python program"
→ OTHER

"Explain quantum physics"
→ OTHER

"Tell me a joke"
→ OTHER

"What is Python?"
→ OTHER

Do NOT classify general knowledge questions as RAG.

==================================================
IMPORTANT RULES
==================================================

1. Use the conversation history.

2. A short message may be SCHEDULING if it is clearly
   answering a pending scheduling question.

3. Do not use RAG for general knowledge.

4. Do not use SCHEDULING merely because the word
   "appointment" appeared somewhere in unrelated text.

5. If the request is not scheduling and cannot reasonably
   be answered from the application's knowledge base,
   return OTHER.

6. When uncertain between RAG and OTHER, use OTHER.

Return ONLY:
SCHEDULING
RAG
or
OTHER
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
        "RAG",
        "OTHER",
    }:
        return "OTHER"

    return intent