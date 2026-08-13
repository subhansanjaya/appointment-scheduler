import json
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from backend.intent import classify_intent
from backend.tools import tool_map
from prompts.build_prompt import build_system_prompt


load_dotenv()


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


AGENT_MODEL = os.getenv(
    "AGENT_MODEL",
    "gpt-4o"
)


messages = []


# -----------------------------
# SYSTEM PROMPT
# -----------------------------

def get_system_prompt():
    today = datetime.now().strftime("%Y-%m-%d")

    return build_system_prompt(today)


# -----------------------------
# MAIN ENTRY POINT
# -----------------------------

def run_agent(user_input):

    # ---------------------------------
    # INTENT GATE
    # ---------------------------------

    intent = classify_intent(user_input)

    print("\n=== INTENT CLASSIFICATION ===")
    print("Input:", user_input)
    print("Intent:", intent)
    print("=============================\n")

    if intent != "SCHEDULING":
        return (
            "I'm an appointment scheduling assistant. "
            "I can help you book, check, cancel, or "
            "reschedule appointments."
        )

    # ---------------------------------
    # INITIALIZE SYSTEM PROMPT
    # ---------------------------------

    if not messages:
        messages.append({
            "role": "system",
            "content": get_system_prompt()
        })

    # ---------------------------------
    # ADD USER MESSAGE
    # ---------------------------------

    messages.append({
        "role": "user",
        "content": user_input
    })

    # ---------------------------------
    # CALL AGENT
    # ---------------------------------

    res = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=messages
    )

    message = res.choices[0].message.content

    messages.append({
        "role": "assistant",
        "content": message
    })

    # ---------------------------------
    # PROCESS RESPONSE
    # ---------------------------------

    return process(message)


# -----------------------------
# TOOL PROCESSOR
# -----------------------------

def process(response):

    try:
        data = json.loads(response)

    except json.JSONDecodeError:
        print("INVALID AGENT RESPONSE:", response)

        return (
            "Sorry, I couldn't process that request. "
            "Please try again."
        )

    # ---------------------------------
    # NORMAL USER RESPONSE
    # ---------------------------------

    if data.get("to") == "user":
        return data.get("message")

    # ---------------------------------
    # TOOL CALL
    # ---------------------------------

    function_call = data.get("function_call")

    if not function_call:
        return (
            "Sorry, I couldn't determine what action "
            "to take."
        )

    fn = function_call.get("function")
    args = function_call.get("arguments", {})

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return "Invalid tool arguments."

    print("\n--- TOOL CALL ---")
    print("Function:", fn)
    print("Args:", args)

    # ---------------------------------
    # CHECK TOOL
    # ---------------------------------

    if fn not in tool_map:
        return f"Unknown tool: {fn}"

    # ---------------------------------
    # EXECUTE TOOL
    # ---------------------------------

    try:
        result = tool_map[fn](**args)

    except Exception as e:
        print("TOOL ERROR:", str(e))

        return (
            f"Tool execution failed: {str(e)}"
        )

    print("Result:", result)

    # ---------------------------------
    # HANDLE TOOL ERROR
    # ---------------------------------

    if (
        isinstance(result, dict)
        and result.get("error")
    ):
        return f"Failed: {result['error']}"

    # ---------------------------------
    # TOOL RESPONSES
    # ---------------------------------

    if fn == "schedule_appointment":
        return "Appointment successfully scheduled."

    if fn == "check_appointment_availability":
        return f"Availability checked: {result}"

    if fn == "delete_appointment":
        return "🗑️ Appointment deleted successfully."

    return "Action completed successfully."