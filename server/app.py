from flask import Flask, request, Response, jsonify,stream_with_context
import asyncio
from run_agents.triage_agent import triage_agent
from context import set_context, get_context
from models.flight_models import SearchFlightOutput
from flask_cors import CORS
from dotenv import load_dotenv
import os
from openai.types.responses import ResponseTextDeltaEvent
from agents import Runner


def create_app():
    app = Flask(__name__)
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environmental variables")

    CORS(app, resources={r"/*": {"origins": "*"}})



    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json()
        user_message = data.get("message")
        thread_id = data.get("thread_id") or "default"
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "Missing required field: user_id"}), 400

        convo = get_context(user_id, thread_id, "convo") or []
        convo.append({"role": "user", "content": user_message})

        async def async_event_stream():
            final_output = ""
            output_data = None

            result = Runner.run_streamed(triage_agent, convo)

            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    chunk = event.data.delta
                    final_output += chunk
                    yield f"data: {chunk}\n\n"
                elif event.type == "tool_end":
                    output_data = event.output

            updated_convo = result.to_input_list()
            set_context(user_id, thread_id, "convo", updated_convo)

            if isinstance(output_data, dict):
                if "destination" in output_data:
                    set_context(user_id, thread_id, "last_flight_destination", output_data["destination"])
                if "origin" in output_data:
                    set_context(user_id, thread_id, "last_flight_origin", output_data["origin"])

        def sync_wrapper():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            gen = async_event_stream()

            try:
                while True:
                    yield loop.run_until_complete(gen.__anext__())
            except StopAsyncIteration:
                return
            finally:
                loop.close()

        return Response(stream_with_context(sync_wrapper()), content_type="text/event-stream")


    @app.route("/history", methods=["GET"])
    def get_history():
        user_id = request.args.get("user_id")
        thread_id = request.args.get("thread_id", "default")

        if not user_id:
            return jsonify({"error": "Missing required parameter: user_id"}), 400

        convo = get_context(user_id, thread_id, "convo") or []
        return jsonify({"history": convo})

    return app

app = create_app()
