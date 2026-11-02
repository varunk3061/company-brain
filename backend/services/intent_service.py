def detect_intent(message : str):

    message = message.lower().strip()

    greetings = {
        "hi": "Hello! How can I help you today?",
        "hello": "Hi! How can I assist you?",
        "hey": "Hey! How can I help you?",
        "good morning": "Good morning! How can I help you?",
        "good afternoon": "Good afternoon! How can I help you?",
        "good evening": "Good evening! How can I help you?",
        "how are you": "I'm doing well! How can I help you today?",
        "good night":"Adios Amigos 😎"
    }

    if message in greetings:
        return "greeting", greetings[message]

    return "knowledge", None