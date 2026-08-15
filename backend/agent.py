import json
from datetime import datetime
from openai import OpenAI
from backend.config import OPENAI_API_KEY, AGENT_MODEL
from backend.conversation_service import (
    get_or_create_conversation,
    get_messages,
    save_message,
)
from backend.tools import tool_map, openai_tools
from prompts.build_prompt import build_system_prompt


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# -----------------------------
# SYSTEM PROMPT
# -----------------------------

def get_system_prompt():
    today = datetime.now().strftime("%Y-%m-%d")

    return build_system_prompt(today)


# -----------------------------
# MAIN ENTRY POINT
# -----------------------------

def run_agent(
    db,
    user_id,
    user_input,
):

    # ---------------------------------
    # GET CONVERSATION
    # ---------------------------------

    conversation = get_or_create_conversation(
        db,
        user_id,
    )

    messages = get_messages(
        db,
        conversation.id,
    )

    # ---------------------------------
    # SAVE USER MESSAGE
    # ---------------------------------

    save_message(
        db,
        conversation.id,
        "user",
        user_input,
    )

    # ---------------------------------
    # BUILD LLM MESSAGES
    # ---------------------------------

    llm_messages = [
        {
            "role": "system",
            "content": get_system_prompt(),
        }
    ]

    llm_messages.extend(messages)

    llm_messages.append({
        "role": "user",
        "content": user_input,
    })

    # ---------------------------------
    # FIRST LLM CALL
    # ---------------------------------

    res = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=llm_messages,
        tools=openai_tools,
    )

    message = res.choices[0].message

    # ---------------------------------
    # NORMAL RESPONSE
    # ---------------------------------

    if not message.tool_calls:

        final_response = message.content

        save_message(
            db,
            conversation.id,
            "assistant",
            final_response,
        )

        return final_response

    # ---------------------------------
    # TOOL CALL
    # ---------------------------------

    # Add the assistant's native tool-call
    # message to the conversation.
    llm_messages.append(message)

    # ---------------------------------
    # SAVE ASSISTANT TOOL CALL
    # ---------------------------------

    tool_calls_data = []

    for tool_call in message.tool_calls:

        tool_calls_data.append({
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        })

    save_message(
        db,
        conversation.id,
        "assistant",
        json.dumps({
            "tool_calls": tool_calls_data
        }),
    )

    # ---------------------------------
    # EXECUTE TOOLS
    # ---------------------------------

    for tool_call in message.tool_calls:

        fn = tool_call.function.name

        args = json.loads(
            tool_call.function.arguments
        )

        print("\n--- TOOL CALL ---")
        print("Function:", fn)
        print("Args:", args)

        # ---------------------------------
        # CHECK TOOL
        # ---------------------------------

        if fn not in tool_map:
            return f"Unknown tool: {fn}"

        # ---------------------------------
        # INJECT AUTHENTICATED USER
        # ---------------------------------

        args["user_id"] = user_id

        # ---------------------------------
        # EXECUTE TOOL
        # ---------------------------------

        try:

            result = tool_map[fn](**args)

        except Exception as e:

            print("TOOL ERROR:", str(e))

            result = {
                "error": str(e)
            }

        print("Result:", result)

        # ---------------------------------
        # SAVE TOOL RESULT
        # ---------------------------------

        save_message(
            db,
            conversation.id,
            "tool",
            json.dumps(result),
            tool_call_id=tool_call.id,
        )

        # ---------------------------------
        # SEND TOOL RESULT TO OPENAI
        # ---------------------------------

        llm_messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })

    # ---------------------------------
    # SECOND LLM CALL
    # ---------------------------------

    final_res = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=llm_messages,
        tools=openai_tools,
    )

    final_message = final_res.choices[0].message

    final_response = final_message.content

    # ---------------------------------
    # SAVE FINAL RESPONSE
    # ---------------------------------

    save_message(
        db,
        conversation.id,
        "assistant",
        final_response,
    )

    return final_response