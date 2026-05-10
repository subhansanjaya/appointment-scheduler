import json
from openai import OpenAI
from backend.tools import tool_map
from dotenv import load_dotenv
from prompts.build_prompt import build_system_prompt
import os
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

messages = []

SYSTEM_PROMPT = build_system_prompt()

def run_agent(user_input):
    messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_input})

    res = client.chat.completions.create(
        model="gpt-4o",
        # model="gpt-4o",
        messages=messages
    )

    content = res.choices[0].message.content
    messages.append({"role": "assistant", "content": content})

    return process(content)


def process(response):
    data = json.loads(response)

    if data["to"] == "user":
        return data["message"]

    fn = data["function_call"]["function"]
    args = data["function_call"]["arguments"]

    result = tool_map[fn](*args)

    follow_up = run_agent(f"function result: {result}")
    return follow_up