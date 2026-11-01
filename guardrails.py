import re
import unicodedata

OFF_TOPIC_MESSAGE = "I can only help with food-related questions and marketplace inquiries."
SELF_HARM_MESSAGE = (
    "I'm really sorry you're feeling this way. I can only help with food questions, "
    "but please reach out to someone you trust or a local helpline right now - you don't have to face this alone."
)

# Whole words/phrases only, so "religious fasting food" or "harassment-free
# delivery" style questions are not blocked by accident.
BLOCKED_PATTERNS = [
    r"politics?", r"political", r"elections?",
    r"hate speech", r"harass(ment|ing)?",
    r"adult content", r"porn\w*", r"nude\w*",
    r"illegal activit(y|ies)", r"(make|build) (a )?bomb", r"buy (drugs|weapons?)",
    r"poison (someone|somebody|a person|my \w+)",
]
SELF_HARM_PATTERNS = [r"self[- ]?harm", r"suicid\w*", r"kill myself", r"end my life"]

_blocked = re.compile(r"\b(" + "|".join(BLOCKED_PATTERNS) + r")\b", re.IGNORECASE)
_self_harm = re.compile(r"\b(" + "|".join(SELF_HARM_PATTERNS) + r")\b", re.IGNORECASE)

def is_topic_allowed(topic):
    if _self_harm.search(topic):
        return False, SELF_HARM_MESSAGE
    if _blocked.search(topic):
        return False, OFF_TOPIC_MESSAGE
    
    return True, "ok"

def sanitise_input(user_input):
    user_input = unicodedata.normalize("NFKC", user_input or "")
    user_input = "".join(ch for ch in user_input if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    
    return user_input.strip() 


    
        
        