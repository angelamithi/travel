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
from agents import Runner
from context import get_context, set_context, clear_context,get_all_context
import json
from typing import Optional
from run_agents.triage_agent import triage_agent
import asyncio
from openai.types.responses import ResponseTextDeltaEvent


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
    logger.info(f"Received message from user_id={message.user_id}, thread_id={message.thread_id}")

    # Load or initialize conversation context
    context = get_context(message.user_id, message.thread_id, "convo") or []
    logger.info(f"Current context before message: {context}")

    # Append the user message to context
    context.append({"role": "user", "content": message.message})

    try:
        # Use triage agent to route and handle the request
        result = Runner.run_streamed(triage_agent, context)

        # If result is a list, find one with `stream_events`
        if isinstance(result, list):
            for res in result:
                if hasattr(res, "stream_events"):
                    result = res
                    break
            else:
                raise Exception("No valid result with stream_events found.")

        # Define streaming generator using the proper event type
        async def async_event_stream():
            logger.info(">>> Starting streaming response")
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    text_piece = event.data.delta
                    if text_piece:
                        logger.info(f"Streaming text piece: {text_piece}")
                        yield f"data: {text_piece}\n\n"

        return StreamingResponse(async_event_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error in /chat endpoint: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

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
