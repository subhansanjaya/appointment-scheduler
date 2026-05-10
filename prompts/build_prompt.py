
from prompts.formatting import FORMAT
from prompts.role import ROLE
from prompts.rules import RULES
from prompts.tools import TOOLS


def build_system_prompt():
    return f"""
{ROLE}

{RULES}

{TOOLS}

{FORMAT}
"""