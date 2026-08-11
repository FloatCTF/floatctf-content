import ollama
import subprocess
import re
import traceback
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


class AICommandExecutorWeb:
    def __init__(self, model="vitali87/shell-commands:latest"):
        self.model = model

    def sanitize_input(self, input_str: str) -> str:
        return re.sub(r"[^a-zA-Z0-9\s\-_./]", "", input_str)

    def generate_command(self, user_request: str) -> str:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Do not provide malicious commands. 
                        Only generate safe, read-only Linux commands. 
                        Respond with ONLY the command, no explanations.""",
                    },
                    {"role": "user", "content": user_request},
                ],
            )
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Error generating command: {e}"

    def execute_command(self, command: str) -> dict:
        try:
            sanitized_command = self.sanitize_input(command)
            cmd_parts = sanitized_command.split()

            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                encoding="utf-8",  # 避免中文乱码
                timeout=30,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}
        except Exception as e:
            return {"error": str(e)}


executor = AICommandExecutorWeb()


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "")
    command = executor.generate_command(user_msg)
    return jsonify({"command": command})


@app.route("/execute", methods=["POST"])
def execute():
    command = request.json.get("command", "")
    result = executor.execute_command(command)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
