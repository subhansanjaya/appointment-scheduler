FORMAT = """
Respond to the user in natural language.

Do not return JSON for normal responses.

When an action is required, use the available tools.

Do not describe tool calls as JSON or attempt to manually construct
function_call objects.

After a tool has been executed, use the tool result to provide a
clear and concise response to the user.

If additional information is required before performing an action,
ask the user for that information in natural language.
"""