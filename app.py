from flask import Flask, jsonify

app = Flask(__name__)

# Temporary in-memory rope database
ropes = {
    "1001": {
        "color": "Red",
        "length": "50m",
        "thickness": "10mm",
        "batch": "BATCH-A1"
    },
    "1002": {
        "color": "Blue",
        "length": "30m",
        "thickness": "8mm",
        "batch": "BATCH-B7"
    }
}

@app.route("/")
def home():
    return "Rope Tagging System is Live"

@app.route("/rope/<rope_id>")
def rope(rope_id):
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
