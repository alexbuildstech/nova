import json
import os

def clear_chat_log():
    filename = "chat_log.json"
    empty_structure = {
        "short_term": [],
        "long_term": [],
        "conversation": []
    }
    
    try:
        with open(filename, "w") as f:
            json.dump(empty_structure, f, indent=2)
        print(f"✅ Successfully cleared {filename}. Memory has been reset.")
    except Exception as e:
        print(f"❌ Error clearing chat log: {e}")

if __name__ == "__main__":
    clear_chat_log()
