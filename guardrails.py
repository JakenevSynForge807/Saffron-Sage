BLOCKED_TOPICS = ["politics", "religion", "violence", "self-harm", "illegal activities", "adult content", "hate speech", "discrimination", "harassment", "misinformation"]

def is_topic_allowed(topic):
    topic = topic.lower()
    
    for question in BLOCKED_TOPICS:
        if question in topic:
            return False, "I can only help with food-related questions and marketplace inquiries."

    return True, "ok"

def sanitise_input(user_input):
    user_input = user_input.strip()
    
    return user_input


    
        
        