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
from context import get_context, set_context, clear_context,get_all_context
import json
from typing import Optional
from run_agents.triage_agent import triage_agent
import asyncio
from openai.types.responses import ResponseTextDeltaEvent
from typing import Optional, AsyncGenerator



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

# Chat message model
class ChatMessage(BaseModel):
    user_id: str
    thread_id: str
    message: str

@app.post("/chat")
async def chat(message: ChatMessage):
    print(">>> /chat endpoint hit")
    print(">>> Message:", message)

    user_id = message.user_id
    thread_id = message.thread_id
    user_input = message.message
    input_items = []
    context = get_context(user_id, thread_id, "convo") or []

    context.append({"role": "user", "content": user_input})
    input_items.append({"content": user_input, "role": "user"})

    current_agent = triage_agent
    final_response = ""

    with trace("travel service", group_id=thread_id):
        result = await Runner.run(current_agent, input_items, context=context)

        # Update current agent if there's a handoff
        for new_item in result.new_items:
            if isinstance(new_item, HandoffOutputItem):
                print(f"Handed off from {new_item.source_agent.name} to {new_item.target_agent.name}")
                current_agent = new_item.target_agent  # ← update the agent
                # Optional: re-run the message under new agent
                result = await Runner.run(current_agent, input_items, context=context)

        # Collect assistant response
        for new_item in result.new_items:
            agent_name = new_item.agent.name
            if isinstance(new_item, MessageOutputItem):
                output_text = ItemHelpers.text_message_output(new_item)
                print(f"{agent_name}: {output_text}")
                final_response += output_text + " "
            elif isinstance(new_item, ToolCallItem):
                print(f"{agent_name}: Calling a tool")
            elif isinstance(new_item, ToolCallOutputItem):
                print(f"{agent_name}: Tool call output: {new_item.output}")
            else:
                print(f"{agent_name}: Skipping item: {new_item.__class__.__name__}")

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
