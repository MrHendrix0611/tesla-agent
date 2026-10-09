class Context:
    def __init__(self):
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append({
            "role": "user",
            "content": content
        }
        )

    def add_assistant_message(self, content: str):
        self.messages.append({
            "role": "assistant",
            "content": content
        })

    def get_messages(self):
        return self.messages