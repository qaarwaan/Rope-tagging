from flask import Flask, jsonify, request, Response
import psycopg2
import os
from functools import wraps

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# -------- BASIC AUTH --------
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# -------- ROUTES --------

@app.route("/")
def home():
    return "Rope Tagging System is Live"

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

# -------- ADMIN PAGE --------

@app.route("/admin")
@requires_auth
def admin_page():
    return """
    <h2>Add New Rope</h2>
    <form method="POST" action="/admin/add">
        Rope ID: <input name="rope_id"><br><br>
        Color: <input name="color"><br><br>
        Length: <input name="length"><br><br>
        Thickness: <input name="thickness"><br><br>
        Batch: <input name="batch"><br><br>
        <button type="submit">Add Rope</button>
    </form>
    """

@app.route("/admin/add", methods=["POST"])
@requires_auth
def add_rope():
    rope_id = request.form.get("rope_id")
    color = request.form.get("color")
    length = request.form.get("length")
    thickness = request.form.get("thickness")
    batch = request.form.get("batch")

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO rope_details (rope_id, color, length, thickness, batch) VALUES (%s, %s, %s, %s, %s)",
            (rope_id, color, length, thickness, batch)
        )

        conn.commit()
        cur.close()
        conn.close()

        return f"Rope {rope_id} added successfully!"

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run()
