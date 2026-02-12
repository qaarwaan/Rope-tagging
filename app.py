from flask import Flask, jsonify
import psycopg2
import os

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route("/")
def home():
    return "Rope Tagging System is Live (DB Connected)"

@app.route("/rope/<rope_id>")
def rope(rope_id):
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
    "SELECT rope_id, color, length, thickness, batch FROM rope_details WHERE rope_id = %s",
    (rope_id,)
)

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row:
            return jsonify({
                "rope_id": row[0],
                "details": {
                    "color": row[1],
                    "length": row[2],
                    "thickness": row[3],
                    "batch": row[4]
                }
            })
        else:
            return jsonify({"error": "Rope not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
