import json
from openai import OpenAI
from backend.tools import tool_map
from dotenv import load_dotenv
from prompts.build_prompt import build_system_prompt
from datetime import datetime
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    # IMPORTANT: refresh system prompt correctly
    if not messages:
        messages.append({
            "role": "system",
            "content": get_system_prompt()
        })

    messages.append({"role": "user", "content": user_input})

    res = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    message = res.choices[0].message.content
    messages.append({"role": "assistant", "content": message})

    return process(message)


# -----------------------------
# TOOL PROCESSOR
# -----------------------------
def process(response):
    data = json.loads(response)

    if data.get("to") == "user":
        return data.get("message")

    fn = data["function_call"]["function"]
    args = data["function_call"]["arguments"]

    if isinstance(args, str):
        args = json.loads(args)

    print("\n--- TOOL CALL ---")
    print("Function:", fn)
    print("Args:", args)

    if fn not in tool_map:
        return f"Unknown tool: {fn}"

    try:
        result = tool_map[fn](**args)
    except Exception as e:
        return f"Tool execution failed: {str(e)}"

    print("Result:", result)

    if isinstance(result, dict) and result.get("error"):
        return f"Failed: {result['error']}"

    if fn == "schedule_appointment":
        return "Appointment successfully scheduled."

    if fn == "check_appointment_availability":
        return f"Availability checked: {result}"

    if fn == "delete_appointment":
        return "🗑️ Appointment deleted successfully."

    return "Action completed successfully."