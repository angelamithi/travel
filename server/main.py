#main.py
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import openai
import os
from dotenv import load_dotenv
import logging
import uuid
from tools.search_flight import search_flight
from models.flight_models import SearchFlightInput
from agents import( Agent,
    HandoffOutputItem,
    ItemHelpers,
    MessageOutputItem,
    RunContextWrapper,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    TResponseInputItem,
    function_tool,
    handoff,
    trace,)
from in_memory_context import get_context, set_context, clear_context,get_all_context
import json
from typing import Optional,List
from run_agents.triage_agent import triage_agent
import asyncio
from openai.types.responses import ResponseTextDeltaEvent
from typing import Optional, AsyncGenerator
from dataclasses import dataclass
from models.context_models import UserInfo



# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logger = logging.getLogger("chat_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("chat_log.txt")
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Check if key exists
if not openai.api_key:
    raise ValueError("Missing OpenAI API key in environment variables")

SERP_API_KEY=os.getenv("SERP_API_KEY")
 

# In-memory conversation store
conversation_store: dict[str, List[TResponseInputItem]] = {}

# Incoming chat message model
class ChatMessage(BaseModel):
    user_id: str
    thread_id: str
    message: str

@app.post("/chat")
async def chat(message: ChatMessage):
    print(">>> /chat endpoint hit")
    print(">>> Message:", message)

    # Retrieve conversation history or start new
    input_items: List[TResponseInputItem] = conversation_store.get(message.thread_id, [])

    # Context object
    user_info = UserInfo(
        user_id=message.user_id,
        thread_id=message.thread_id,
        email="",  # fill from DB if needed
        name="",
        phone=""
    )
    context = user_info

    # Append the latest user input to the history
    user_input = message.message
    input_items.append({"content": user_input, "role": "user"})

    # Start with triage agent
    current_agent = triage_agent
    final_response = ""

    with trace("travel service", group_id=message.thread_id):
        # Initial run
        result = await Runner.run(current_agent, input_items, context=context)

        # Handle agent handoff if it occurred
        for new_item in result.new_items:
            if isinstance(new_item, HandoffOutputItem):
                print(f"Handed off from {new_item.source_agent.name} to {new_item.target_agent.name}")
                current_agent = new_item.target_agent

                # Append assistant reply from first agent
                for item in result.new_items:
                    if isinstance(item, MessageOutputItem):
                        assistant_reply = ItemHelpers.text_message_output(item)
                        input_items.append({"role": "assistant", "content": assistant_reply})

                # Append the user message again for re-evaluation under new agent
                input_items.append({"role": "user", "content": user_input})

                # Rerun with updated agent and preserved message history
                result = await Runner.run(current_agent, input_items, context=context)

        # Process final result
        for new_item in result.new_items:
            agent_name = new_item.agent.name
            if isinstance(new_item, MessageOutputItem):
                output_text = ItemHelpers.text_message_output(new_item)
                print(f"{agent_name}: {output_text}")
                final_response += output_text + " "
                input_items.append({"role": "assistant", "content": output_text})
            elif isinstance(new_item, ToolCallItem):
                print(f"{agent_name}: Calling a tool")
            elif isinstance(new_item, ToolCallOutputItem):
                print(f"{agent_name}: Tool call output: {new_item.output}")
            else:
                print(f"{agent_name}: Skipping item: {new_item.__class__.__name__}")

        # ✅ Save updated conversation history back to store
        conversation_store[message.thread_id] = input_items

    return {"role": "assistant", "content": final_response.strip()}


    

@app.post("/clear_context")
def clear_chat_context(user_id: str, thread_id: str):
    """Optional utility endpoint to clear conversation memory."""
    try:
        clear_context(user_id, thread_id)
        logger.info(f"Cleared context for user_id={user_id}, thread_id={thread_id}")
        return {"status": "context cleared"}
    except Exception as e:
        logger.error(f"Error clearing context: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})



@app.get("/history")
async def get_history(user_id: str, thread_id: str = "default"):
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing required parameter: user_id")

    convo = get_context(user_id, thread_id, "convo") or []
    return {"history": convo}
