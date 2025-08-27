from .turkish import TurkishPrompt
from .tryprompt1 import TryPrompt1

# Dictionary of available prompts
AVAILABLE_PROMPTS = {
    'turkish': TurkishPrompt,
    'tryprompt1': TryPrompt1,
}

def get_prompt(prompt_type='tryprompt1'):
    """Get a prompt by type"""
    return AVAILABLE_PROMPTS.get(prompt_type, TryPrompt1).get_prompt()
