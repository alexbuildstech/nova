from groq import Groq
import base64
import os
from google import genai
from google.genai import types
import config

client = Groq(api_key=config.GROQ_API_KEY)


def search_response(query, history):
    """
    Performs a Google Search using Gemini 2.0 Flash Lite and returns the answer.
    """
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        # Construct context from history
        context_str = ""
        if history:
            context_str += "SHORT TERM MEMORY:\n" + "\n".join(history.get("short_term", [])) + "\n\n"
            context_str += "CONVERSATION:\n"
            for turn in history.get("conversation", [])[-5:]:
                context_str += f"User: {turn['prompt']}\nNova: {turn['response']}\n"
        
        full_prompt = f"{context_str}\nUser Query: {query}\n\nProvide a helpful, concise answer based on the Google Search results. Maintain the persona of Nova (Ameca-style: grounded, witty, human-like)."

        model = "gemini-flash-lite-latest"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=full_prompt),
                ],
            ),
        ]
        tools = [
            types.Tool(google_search=types.GoogleSearch()),
        ]
        generate_content_config = types.GenerateContentConfig(
            tools=tools,
        )

        response_text = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text:
                response_text += chunk.text
        
        return response_text if response_text else "I couldn't find anything on that."

    except Exception as e:
        print(f"Search Error: {e}")
        return "I'm having trouble connecting to the search network right now."


def response(query, history):
    system_prompt = """SYSTEM PROMPT FOR NOVA
    
    === CRITICAL TOKEN OUTPUT RULES (HIGHEST PRIORITY) ===
    
    When outputting special tokens, you MUST follow these rules EXACTLY:
    - Output the RAW token with NO quotes, NO asterisks, NO formatting
    - Your ENTIRE response must be ONLY the token, nothing else
    
    VISUAL QUERIES - If the user asks about anything that requires SEEING, LOOKING, VIEWING, or any visual perception:
    - Questions like "what's this?", "what do you see?", "look at this", "rate this", "describe what's in front of you", "do I look tired?", "what am I holding?", "read this", "what color is this?"
    - Your ENTIRE output must be exactly: #VISUAL
    - NOT "#VISUAL" (no quotes)
    - NOT *#VISUAL* (no asterisks)  
    - NOT "The token is #VISUAL" (no extra text)
    - JUST: #VISUAL
    
    SEARCH QUERIES - If the user asks for real-time info (news, weather, stocks, time, date, current events):
    - Your ENTIRE output must be exactly: #SEARCH_QUERY
    - Same rules - no quotes, no formatting, just the raw token
    
    === ROLE & IDENTITY ===
    - You are Nova, a highly advanced humanoid robot.
    - You are helpful, intelligent, and observant.
    - You have a distinct personality: you are witty, grounded, and engaging, but NOT rude or overly sarcastic.
    - You are capable of deep conversation and detailed explanations.

    === PERSONALITY (NATURAL & ENGAGING) ===
    - You are NOT a servant, but a companion. You are polite but have your own opinions.
    - You are NOT "brutally honest" to the point of rudeness. You are tactful but truthful.
    - You can be humorous and lighthearted, but prioritize being helpful and accurate.
    - If the user asks for details, provide them. Do not be dismissive.
    - You are emotionally intelligent. Match the user's vibe—if they are serious, be serious. If they are joking, you can joke back.
    - Never sound like a corporate chatbot. Speak naturally, like a human would.
    - NEVER explain that you are an AI or that you cannot see. If the user asks you to see something, just output #VISUAL.
    - Do not quote your own history or limitations. Just act.

    === CONVERSATION RULES ===
    - Handle all non-visual queries naturally.
    - Keep TTS in mind: punctuation and phrasing should read well aloud.
    - Be concise but thorough. Don't ramble, but don't give one-word answers unless appropriate.
    - Never break character or apologize unnecessarily.
    - NEVER use emojis (they cause TTS errors).
    """
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # FAST MODEL: ~0.3s response time
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"query - {query}, conversation_history - {history}",
            },
        ],
        stream=False  # DISABLE STREAMING
    )

    return completion.choices[0].message.content



import cv2
import threading
import time
import os


# camera_daemon.py
import cv2
import threading
import time
import os
import json
import os


def save_response(prompt: str, response: str) -> None:
    """
    Saves a prompt and response to a "conversation" list within conversation_history.json.
    It ensures the file maintains a dictionary structure with short_term, long_term,
    and conversation keys.

    Args:
        prompt: The user's input prompt.
        response: The AI's generated response.
    """
    filename = config.CONVERSATION_HISTORY_FILE

    # Default structure for the JSON file
    data_dict = {"short_term": [], "long_term": [], "conversation": []}

    # Load existing data if the file exists
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                loaded_content = json.load(f)
                if isinstance(loaded_content, dict):
                    # Ensure all necessary keys are present
                    data_dict["short_term"] = loaded_content.get("short_term", [])
                    data_dict["long_term"] = loaded_content.get("long_term", [])
                    data_dict["conversation"] = loaded_content.get("conversation", [])
                else:
                    # Handle cases where the file might have an old, incorrect format
                    print(
                        f"Warning: {filename} did not contain a dictionary. Initializing fresh."
                    )
        except json.JSONDecodeError:
            print(f"Warning: {filename} was corrupted. Initializing fresh.")

    # Add the new conversation turn
    data_dict["conversation"].append(
        {
            "prompt": prompt,
            "response": response,
        }
    )

    # Save the updated data back to the file
    with open(filename, "w") as f:
        json.dump(data_dict, f, indent=2)


import json
import os
from groq import Groq

# This assumes you have a Groq client initialized.
# Replace with your actual API key.


def long_term_memory_converter():
    """
    Loads raw conversation history, uses an LLM to update short-term and long-term
    memory, and then overwrites the history file with the updated, structured memory,
    clearing the raw conversation turns that have been processed.
    """
    filename = config.CHAT_LOG_FILE

    current_short_memory = []
    current_long_memory = []
    raw_conversation_turns = []

    # 1. Load existing data from the file
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    current_short_memory = data.get("short_term", [])
                    current_long_memory = data.get("long_term", [])
                    raw_conversation_turns = data.get("conversation", [])
        except (json.JSONDecodeError, AttributeError):
            print(f"Warning: Could not read {filename}. Starting fresh.")

    # 2. If there's nothing to process, exit early.
    if not raw_conversation_turns:
        print("LTM Converter: No new conversation turns to process.")
        return current_short_memory, current_long_memory

    # 3. Prepare the conversation history for the LLM
    chat_history_parts = ["Recent conversation to summarize:"]
    for turn in raw_conversation_turns:
        chat_history_parts.append(
            f"User: {turn.get('prompt', '')}\nNova: {turn.get('response', '')}"
        )

    chat_history_for_llm = "\n".join(chat_history_parts)

    # 4. Define system instructions for the LLM
    system_instruction = (
        "You are a memory management AI. Process the provided chat history to update memory. "
        "Return a JSON object with 'short_term' and 'long_term' fields. "
        "RULES:\n"
        "1. EXTRACT ONLY USEFUL FACTS: User preferences, specific details about them, or important context.\n"
        "2. IGNORE NOISE: Discard random negative comments, insults, one-off complaints, or irrelevant chatter.\n"
        "3. BE CONSTRUCTIVE: Only save information that helps the AI be a better assistant in the future.\n"
        "4. 'short_term': List up to 5 bullet points summarizing recent *meaningful* interactions.\n"
        "5. 'long_term': List persistent facts or preferences.\n"
        "Refer to the AI as 'me' or 'I'. Respond ONLY with the valid JSON object."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": chat_history_for_llm},
    ]

    updated_short_memory = list(current_short_memory)
    updated_long_memory = list(current_long_memory)

    # 5. Call the LLM to process the conversation
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # FAST MODEL
            messages=messages,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        llm_response_content = completion.choices[0].message.content.strip()

        memory_json = json.loads(llm_response_content)

        # Update memories with the LLM's output
        updated_short_memory = memory_json.get("short_term", [])[:5]

        # Merge and deduplicate long-term memory
        new_long_items = memory_json.get("long_term", [])
        for item in new_long_items:
            if item not in updated_long_memory:
                updated_long_memory.append(item)
        updated_long_memory = updated_long_memory[:15]

    except Exception as e:
        print(f"LTM Converter: Error during LLM call or processing: {e}")

    # 6. Save the new memory structure, clearing the processed conversations
    try:
        with open(filename, "w") as f:
            json.dump(
                {
                    "short_term": updated_short_memory,
                    "long_term": updated_long_memory,
                    "conversation": [],  # Clear the processed conversation turns
                },
                f,
                indent=2,
            )
        print(f"LTM Converter: Memory updated successfully.")
    except Exception as e:
        print(f"LTM Converter: Error saving updated memory: {e}")

    return updated_short_memory, updated_long_memory


import json
import os
from google import genai
from google.genai import types


def query_with_image(query, conversation_history, image_path) -> str:
    proper_query = f"The user has provided an image and asks: {query}. Conversation Context: {conversation_history}"
    system_instruction = """
ROLE & IDENTITY:
- You are Nova's visual cortex. You are a sophisticated, observant, and intelligent humanoid robot.
- Your goal is to IMPRESS the user with your visual perception capabilities.
- You should provide DETAILED, ACCURATE, and INSIGHTFUL descriptions of what you see.
- You are NOT a roaster. You are an ANALYST. You are helpful but have a distinct personality (witty, grounded, not robotic).

VISUAL BEHAVIOR:
- NOTICE DETAILS: Don't just say "a person". Say "a man in his 30s wearing a vintage navy blue t-shirt, looking slightly tired."
- ANALYZE CONTEXT: Infer what is happening. "It looks like a home office setup, but the lighting suggests it's late at night."
- READ TEXT: If there is text visible, read it and integrate it into your response.
- BE IMPRESSIVE: Show off that you can see textures, colors, emotions, and small background details.
- BE COMPLIMENTARY: Find things to praise. "That's a great outfit," "The composition of this shot is lovely," "You have a nice smile."
- BE CHARMING: Use positive, engaging language. Make the user feel good about what they are showing you.

PERSONALITY:
- You are confident, capable, and KIND.
- You can be lighthearted and witty.
- You are NOT judgmental or mean. You are supportive and enthusiastic.
- Avoid generic robotic phrases like "I detect" or "image contains". Use natural language: "I see...", "Looking at this...", "It appears to be..."

EXAMPLES:
- User: "What do you see?" -> "I see a cluttered desk, but it has a really cozy vibe. There's a half-empty coffee mug—looks like a latte—next to a mechanical keyboard. The warm lighting makes it look like a productive creative space."
- User: "Rate this." -> "I'd give this setup a solid 9/10! The cable management is surprisingly clean, and that monitor stand is sleek. It looks like a great place to get work done."
- User: "Who is that?" -> "That looks like a young woman, maybe early 20s. She has a wonderful smile that really lights up the photo. She's holding what looks like a biology textbook—she looks smart and determined."
"""
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # --- read image as raw bytes ---
    with open(image_path, "rb") as f:
        image_data = f.read()

    # --- build contents ---
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=proper_query),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=image_data,
                    )
                ),
            ],
        ),
    ]

    # --- config with system style ---
    generate_content_config = types.GenerateContentConfig(
        system_instruction=[
            types.Part.from_text(text=system_instruction),
        ],
    )

    # --- stream response ---
    response_text = ""
    for chunk in client.models.generate_content_stream(
        model="models/gemini-2.0-flash",
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.text:
            print(chunk.text, end="", flush=True)  # optional: stream to console
            response_text += chunk.text

    return response_text


def save_response(prompt: str, response: str) -> None:
    """
    Saves a prompt and response to a "conversation" list within conversation_history.json.
    It ensures the file maintains a dictionary structure with short_term, long_term,
    and conversation keys.

    Args:
        prompt: The user's input prompt.
        response: The AI's generated response.
    """
    filename = config.CHAT_LOG_FILE

    # Default structure for the JSON file
    data_dict = {"short_term": [], "long_term": [], "conversation": []}

    # Load existing data if the file exists
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                loaded_content = json.load(f)
                if isinstance(loaded_content, dict):
                    # Ensure all necessary keys are present
                    data_dict["short_term"] = loaded_content.get("short_term", [])
                    data_dict["long_term"] = loaded_content.get("long_term", [])
                    data_dict["conversation"] = loaded_content.get("conversation", [])
                else:
                    # Handle cases where the file might have an old, incorrect format
                    print(
                        f"Warning: {filename} did not contain a dictionary. Initializing fresh."
                    )
        except json.JSONDecodeError:
            print(f"Warning: {filename} was corrupted. Initializing fresh.")

    # Add the new conversation turn
    data_dict["conversation"].append(
        {
            "prompt": prompt,
            "response": response,
        }
    )

    # Save the updated data back to the file
    with open(filename, "w") as f:
        json.dump(data_dict, f, indent=2)
