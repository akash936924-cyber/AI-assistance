from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="ollama",
    timeout=120.0
)

DEFAULT_MODEL = "gemma3:1b"

SYSTEM_PROMPT = """
You are a helpful and friendly AI assistant.
Reply in the same language as the user.
Understand the full conversation before answering.
Give clear, useful answers instead of replying with only an emoji,
unless the user explicitly asks for an emoji.
If the user asks a question, answer it directly.
"""


def clean_settings(raw):
    """Validate the settings sent by the browser and fall back to defaults."""
    raw = raw if isinstance(raw, dict) else {}

    try:
        temperature = float(raw.get("temperature", 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = min(max(temperature, 0.0), 2.0)

    try:
        max_tokens = int(raw.get("max_tokens", 1024))
    except (TypeError, ValueError):
        max_tokens = 1024
    max_tokens = min(max(max_tokens, 64), 4096)

    model = raw.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 100:
        model = DEFAULT_MODEL
    model = model.strip()

    system = raw.get("system")
    if not isinstance(system, str) or not system.strip():
        system = SYSTEM_PROMPT
    system = system.strip()[:2000]

    return model, temperature, max_tokens, system


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/models")
def models():
    """List the models installed in Ollama for the settings dropdown."""
    try:
        names = sorted(m.id for m in client.models.list().data)
        return jsonify({"models": names or [DEFAULT_MODEL]})
    except Exception:
        app.logger.exception("Could not list models")
        return jsonify({"models": [DEFAULT_MODEL]})


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])
        model, temperature, max_tokens, system_prompt = clean_settings(
            data.get("settings")
        )

        if not isinstance(messages, list) or not messages:
            return jsonify({"reply": "Please enter a message."}), 400

        # Accept only valid user/assistant messages.
        valid_messages = []
        for message in messages:
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")

            if role not in ("user", "assistant"):
                continue

            if not isinstance(content, str) or not content.strip():
                continue

            valid_messages.append({
                "role": role,
                "content": content.strip()
            })

        if not valid_messages or valid_messages[-1]["role"] != "user":
            return jsonify({
                "reply": "Please send a new message."
            }), 400

        # Limit context to the most recent 20 messages.
        conversation = valid_messages[-20:]

        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        def generate():
            try:
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    piece = chunk.choices[0].delta.content
                    if piece:
                        yield piece
            except Exception:
                app.logger.exception("Streaming failed midway")
                yield "\n\n[Connection lost. Please try again.]"

        return Response(
            stream_with_context(generate()),
            mimetype="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception:
        app.logger.exception("Chat request failed")
        return jsonify({
            "reply": "AI connection failed. Check whether Ollama is running and the selected model is available."
        }), 500


if __name__ == "__main__":
    app.run(debug=True)