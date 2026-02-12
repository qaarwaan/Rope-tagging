from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Rope Tagging System is Live"

@app.route("/rope/<rope_id>")
def rope(rope_id):
    return f"Details for Rope ID: {rope_id}"

if __name__ == "__main__":
    app.run()
