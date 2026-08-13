from prompts.role import ROLE
from prompts.rules import RULES
from prompts.tools import TOOLS
from prompts.formatting import FORMAT

def build_system_prompt(today: str):
    filled_rules = RULES.format(today=today)

    return f"""
{ROLE}

{filled_rules}

{TOOLS}

{FORMAT}
"""