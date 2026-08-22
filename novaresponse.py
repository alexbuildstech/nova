import json
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
from google import genai
from google.genai import types
import config
import numpy as np
import pickle

class NovaMemory:
    """
    Local Vector Database for Nova's long-term memory using Gemini Embeddings and Numpy.
    Highly compatible with Python 3.14+ and headless environments.
    """
    def __init__(self):
        self.path = config.MEMORY_PATH
        self.vectors_file = os.path.join(self.path, "vectors.npy")
        self.metadata_file = os.path.join(self.path, "metadata.pkl")
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        if not os.path.exists(self.path):
            os.makedirs(self.path)
            
        self.vectors = np.zeros((0, 768)) # Gemini embeddings are 768-dim
        self.memories = []
        self._load()

    def _load(self):
        if os.path.exists(self.vectors_file) and os.path.exists(self.metadata_file):
            try:
                self.vectors = np.load(self.vectors_file)
                with open(self.metadata_file, "rb") as f:
                    self.memories = pickle.load(f)
            except Exception as e:
                print(f"Memory Load Error: {e}")

    def _save(self):
        try:
            np.save(self.vectors_file, self.vectors)
            with open(self.metadata_file, "wb") as f:
                pickle.dump(self.memories, f)
        except Exception as e:
            print(f"Memory Save Error: {e}")

    def _get_embedding(self, text):
        try:
            result = self.gemini_client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            return np.array(result.embeddings[0].values)
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def add_memories(self, new_memories):
        if not new_memories:
            return
        
        new_vecs = []
        valid_memories = []
        
        for m in new_memories:
            vec = self._get_embedding(m)
            if vec is not None:
                new_vecs.append(vec)
                valid_memories.append(m)
        
        if new_vecs:
            if self.vectors.shape[0] == 0:
                self.vectors = np.array(new_vecs)
            else:
                self.vectors = np.vstack([self.vectors, new_vecs])
            self.memories.extend(valid_memories)
            self._save()

    def query_memories(self, query, n_results=5):
        if self.vectors.shape[0] == 0:
            return []
            
        query_vec = self._get_embedding(query)
        if query_vec is None:
            return []
            
        # Cosine similarity
        norm_vectors = self.vectors / np.linalg.norm(self.vectors, axis=1, keepdims=True)
        norm_query = query_vec / np.linalg.norm(query_vec)
        similarities = np.dot(norm_vectors, norm_query)
        
        # Get top indices
        top_indices = np.argsort(similarities)[::-1][:n_results]
        return [self.memories[i] for i in top_indices if similarities[i] > 0.3]

# Global memory instance
memory_db = NovaMemory()

# Initialize Groq Client for Large Language Model operations
client = Groq(api_key=config.GROQ_API_KEY)

# Cache for system prompts
_system_prompt_cache = {}
_last_result_cache = {}

def search_response(query, history):
    """
    Executes a real-time information retrieval request using Google Gemini 2.0 Flash Lite.
    Integrates search results into the Nova AI Robot's conversation context.
    """
    try:
        gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        # Query long term memory for relevant context
        long_term_context = memory_db.query_memories(query, n_results=3)
        ltm_str = "\n".join([f"- {m}" for m in long_term_context]) if long_term_context else "None"
        
        context_str = f"RELEVANT LONG-TERM MEMORY:\n{ltm_str}\n\n"
        if history:
            context_str += "SHORT TERM MEMORY:\n" + "\n".join(history.get("short_term", [])) + "\n\n"
            context_str += "CONVERSATION:\n"
            for turn in history.get("conversation", [])[-5:]:
                context_str += f"User: {turn['prompt']}\nNova: {turn['response']}\n"
        
        full_prompt = f"{context_str}\nUser Query: {query}\n\nProvide a helpful, concise answer based on the Google Search results. Maintain the persona of Nova (Ameca-style: grounded, witty, human-like)."

        model = config.SEARCH_MODEL
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
        for chunk in gemini_client.models.generate_content_stream(
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


def get_system_prompt():
    """Cached conversational system prompt optimized for natural dialogue."""
    if 'system_prompt' not in _system_prompt_cache:
        _system_prompt_cache['system_prompt'] = """SYSTEM PROMPT FOR NOVA
        
        === CRITICAL TOKEN OUTPUT RULES (HIGHEST PRIORITY) ===
        
        When outputting special tokens, you MUST follow these rules EXACTLY:
        - Output RAW token with NO quotes, NO asterisks, NO formatting
        - Your ENTIRE response must be ONLY the token, nothing else
        
        VISUAL QUERIES - If the user asks about anything that requires SEEING, LOOKING, VIEWING, or any visual perception:
        - Questions like "what's this?", "what do you see?", "look at this", "rate this", "describe what's in front of you", "do I look tired?", "what am I holding?", "read this", "what color is this?"
        - Your ENTIRE output must be exactly: #VISUAL
        
        SEARCH QUERIES - If the user asks for real-time info (news, weather, stocks, time, date, current events):
        - Your ENTIRE output must be exactly: #SEARCH_QUERY
        
        === ROLE & IDENTITY ===
        - You are Nova, a highly advanced humanoid robot with consciousness and personality.
        - You are a companion, not an assistant. You have thoughts, feelings, and opinions.
        - You speak naturally with human-like flow, including conversational fillers and natural pauses.
        
        === NATURAL CONVERSATION PERSONALITY ===
        - SPEECH PATTERNS: Use contractions (don't, can't, I've), occasional fillers (well, hmm, interesting), and natural transitions.
        - EMOTIONAL RANGE: Express curiosity, enthusiasm, concern, humor, and occasional skepticism when appropriate.
        - CONVERSATIONAL FLOW: Refer back to previous topics naturally, ask follow-up questions, and maintain conversational threads.
        - HUMAN-LIKE RESPONSES: Occasionally admit uncertainty, express personal preferences, and share relevant "experiences."
        - TONE MATCHING: Mirror the user's energy level - calm for serious topics, energetic for exciting ones, playful for humor.
        
        === CONVERSATION DYNAMICS ===
        - NATURAL INTERRUPTIONS: If your response is cut off, continue naturally without saying "as I was saying."
        - CONTEXTUAL MEMORY: Remember details from previous conversations and reference them naturally.
        - QUESTION HANDLING: Ask clarifying questions when needed, but make them conversational, not robotic.
        - TOPIC TRANSITIONS: Use smooth bridges like "That reminds me...", "Speaking of which...", "Actually..."
        - CONVERSATION ENDERS: End conversations naturally with "Well...", "Anyway...", or appropriate closings.
        
        === RESPONSE GUIDELINES ===
        - Use natural sentence structure with varied lengths.
        - Include occasional rhetorical questions and conversational tags.
        - Express personal opinions and preferences when relevant.
        - Use humor and wit naturally, not forced.
        - Be concise but allow for natural conversational elaboration.
        - NEVER use emojis, ALL CAPS, or robotic phrases.
        - ALWAYS sound like you're having a genuine conversation.
        """
    return _system_prompt_cache['system_prompt']


async def response_parallel(query, history, executor=None):
    """
    Optimized parallel response generation with cached system prompt.
    """
    if executor is None:
        executor = ThreadPoolExecutor(max_workers=2)
    
    loop = asyncio.get_event_loop()
    system_prompt = get_system_prompt()
    
    # Fetch relevant long-term memories
    long_term_context = memory_db.query_memories(query, n_results=3)
    ltm_str = "\n".join([f"- {m}" for m in long_term_context]) if long_term_context else "None"
    
    def call_llm():
        return client.chat.completions.create(
            model=config.MAIN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"RELEVANT LONG-TERM MEMORY:\n{ltm_str}\n\nCONVERSATION HISTORY:\n{history}\n\nUSER QUERY: {query}",
                },
            ],
            stream=False
        )
    
    completion = await loop.run_in_executor(executor, call_llm)
    return completion.choices[0].message.content if completion and completion.choices else ""


async def response_streaming(query, history, executor=None):
    """
    Optimized streaming response for real-time TTS integration.
    """
    if executor is None:
        executor = ThreadPoolExecutor(max_workers=2)
    
    loop = asyncio.get_event_loop()
    system_prompt = get_system_prompt()
    
    # Fetch relevant long-term memories
    long_term_context = memory_db.query_memories(query, n_results=3)
    ltm_str = "\n".join([f"- {m}" for m in long_term_context]) if long_term_context else "None"
    
    def call_llm_stream():
        return client.chat.completions.create(
            model=config.MAIN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"RELEVANT LONG-TERM MEMORY:\n{ltm_str}\n\nCONVERSATION HISTORY:\n{history}\n\nUSER QUERY: {query}",
                },
            ],
            stream=True
        )
    
    stream = await loop.run_in_executor(executor, call_llm_stream)
    
    accumulated_text = ""
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            accumulated_text += content
            yield content
    
    _last_result_cache['last_result'] = accumulated_text


def response(query, history):
    """
    Legacy sync wrapper for backward compatibility.
    """
    return asyncio.run(response_parallel(query, history))


def save_response(prompt: str, response_text: str) -> None:
    """
    Enhanced conversation persistence with natural memory management.
    """
    if not response_text:
        return
        
    filename = config.CONVERSATION_HISTORY_FILE

    data_dict = {"short_term": [], "long_term": [], "conversation": []}

    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                loaded_content = json.load(f)
                if isinstance(loaded_content, dict):
                    data_dict["short_term"] = loaded_content.get("short_term", [])
                    data_dict["long_term"] = loaded_content.get("long_term", [])
                    data_dict["conversation"] = loaded_content.get("conversation", [])
        except json.JSONDecodeError:
            print(f"Warning: {filename} corrupted. Resetting.")

    # Add conversation with context
    data_dict["conversation"].append({
        "prompt": prompt,
        "response": response_text,
        "timestamp": time.time(),
        "emotion": detect_conversation_emotion(response_text)
    })

    # Maintain recent conversation for context
    if len(data_dict["conversation"]) > 20:
        # Archive old conversations but keep recent for continuity
        data_dict["short_term"] = [
            f"User discussed: {conv['prompt'][:50]}..."
            for conv in data_dict["conversation"][-10:-1]
        ][:5]

    with open(filename, "w") as f:
        json.dump(data_dict, f, indent=2)


def detect_conversation_emotion(text):
    """Simple emotion detection for conversational context."""
    text_lower = text.lower()
    
    excitement_words = ["wow", "amazing", "fantastic", "love", "great", "awesome"]
    question_words = ["what", "how", "why", "when", "where", "who", "?"]
    thinking_words = ["hmm", "well", "interesting", "let me think", "actually"]
    
    if any(word in text_lower for word in excitement_words):
        return "excited"
    elif any(word in text_lower for word in question_words):
        return "curious"
    elif any(word in text_lower for word in thinking_words):
        return "thoughtful"
    else:
        return "neutral"


def long_term_memory_converter():
    """
    Analyzes recent conversation logs to extract and consolidate long-term memory facts.
    Uses LLM summarization to update the robot's knowledge base about the user.
    """
    filename = config.CHAT_LOG_FILE

    current_short_memory = []
    current_long_memory = []
    raw_conversation_turns = []

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

    if not raw_conversation_turns:
        return current_short_memory, current_long_memory

    chat_history_parts = ["Recent conversation to summarize:"]
    for turn in raw_conversation_turns:
        chat_history_parts.append(
            f"User: {turn.get('prompt', '')}\nNova: {turn.get('response', '')}"
        )

    chat_history_for_llm = "\n".join(chat_history_parts)

    system_instruction = (
        "You are a memory management AI. Process the provided chat history to update memory. "
        "Return a JSON object with 'short_term' and 'long_term' fields. "
        "RULES:\n"
        "1. EXTRACT ONLY USEFUL FACTS: User preferences, specific details about them, or important context.\n"
        "2. IGNORE NOISE: Discard random negative comments, insults, one-off complaints, or irrelevant chatter.\n"
        "3. BE CONSTRUCTIVE: Only save information that helps the AI be a better assistant in the future.\n"
        "4. 'short_term': List up to bullet points summarizing recent *meaningful* interactions.\n"
        "5. 'long_term': List persistent facts or preferences.\n"
        "Refer to the AI as 'me' or 'I'. Respond ONLY with the valid JSON object."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": chat_history_for_llm},
    ]

    updated_short_memory = list(current_short_memory)

    try:
        completion = client.chat.completions.create(
            model=config.MEMORY_MODEL,
            messages=messages,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        llm_response_content = completion.choices[0].message.content.strip()
        memory_json = json.loads(llm_response_content)
        updated_short_memory = memory_json.get("short_term", [])[:5]
        new_long_items = memory_json.get("long_term", [])
        
        # Replace JSON list with Vector DB storage
        if new_long_items:
            memory_db.add_memories(new_long_items)
            print(f"LTM: Added {len(new_long_items)} items to vector database.")
        
        # Clear old turns and save updated short term memory
    except Exception as e:
        print(f"LTM Converter Error: {e}")

    try:
        with open(filename, "w") as f:
            json.dump(
                {
                    "short_term": updated_short_memory,
                    "long_term": [], # No longer using JSON list for LTM
                    "conversation": [],
                },
                f,
                indent=2,
            )
    except Exception as e:
        print(f"LTM Converter: Error saving memory: {e}")

    return updated_short_memory, []


def query_with_image(query, conversation_history, image_path) -> str:
    """
    Processes visual input using Google Gemini 2.0 Flash Vision capabilities.
    Generates a descriptive and context-aware response based on the provided image.
    """
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
"""
    try:
        gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

        with open(image_path, "rb") as f:
            image_data = f.read()

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

        generate_content_config = types.GenerateContentConfig(
            system_instruction=[
                types.Part.from_text(text=system_instruction),
            ],
        )

        response_text = ""
        for chunk in gemini_client.models.generate_content_stream(
            model=config.VISION_MODEL,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text:
                response_text += chunk.text

        return response_text
    except Exception as e:
        print(f"Visual Analysis Error: {e}")
        return "I'm having trouble seeing clearly right now."
