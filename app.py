from flask import Flask, jsonify
import json

app = Flask(__name__)

def load_ropes():
    with open("ropes.json", "r") as file:
        return json.load(file)

@app.route("/")
def home():
    return "Rope Tagging System is Live"

@app.route("/rope/<rope_id>")
def rope(rope_id):
    ropes = load_ropes()
    rope_data = ropes.get(rope_id)

    if rope_data:
        return jsonify({
            "rope_id": rope_id,
            "details": rope_data
        })
    else:
        return jsonify({
            "error": "Rope not found"
        }), 404

if __name__ == "__main__":
    app.run()
