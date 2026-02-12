from flask import Flask, jsonify, request, Response
import psycopg2
import os
import bcrypt
import random
import string
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# ---------------- DB CONNECTION ----------------

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# ---------------- ID GENERATOR ----------------

def generate_rope_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# ---------------- AUTH ----------------

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

# ---------------- STATUS LOGIC ----------------

def compute_status(rope_id, purchase_date):
    conn = get_connection()
    cur = conn.cursor()

    # Last inspection
    cur.execute("""
        SELECT inspection_date FROM inspection_logs
        WHERE rope_id = %s
        ORDER BY inspection_date DESC
        LIMIT 1
    """, (rope_id,))
    inspection_row = cur.fetchone()

    if inspection_row:
        base_date = inspection_row[0]
    else:
        base_date = purchase_date

    next_due = base_date + timedelta(days=365)

    # Count falls since base_date
    cur.execute("""
        SELECT fall_type FROM fall_logs
        WHERE rope_id = %s AND fall_date >= %s
    """, (rope_id, base_date))

    falls = cur.fetchall()
    cur.close()
    conn.close()

    major = sum(1 for f in falls if f[0] == 'major')
    minor = sum(1 for f in falls if f[0] == 'minor')

    today = datetime.today().date()

    if major >= 1:
        return "DAMAGED"
    elif minor >= 2:
        return "DAMAGED"
    elif today > next_due:
        return "INSPECTION DUE"
    else:
        return "ACTIVE"

# ---------------- PUBLIC ROUTE ----------------

@app.route("/rope/<rope_id>")
def rope_details(rope_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT rope_id, product_name, thickness, original_length,
               color, batch, manufacturing_date, purchase_date
        FROM ropes WHERE rope_id = %s
    """, (rope_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "Rope not found"}), 404

    purchase_date = row[7]
    status = compute_status(rope_id, purchase_date)

    cur.close()
    conn.close()

    return jsonify({
        "rope_id": row[0],
        "product_name": row[1],
        "thickness": row[2],
        "original_length": row[3],
        "color": row[4],
        "batch": row[5],
        "manufacturing_date": str(row[6]),
        "purchase_date": str(row[7]),
        "status": status
    })

# ---------------- ADMIN PANEL ----------------

@app.route("/admin")
@requires_auth
def admin_page():
    return """
    <h2>Create New Rope</h2>
    <form method="POST" action="/admin/create">
        Product Name: <input name="product_name"><br><br>
        Thickness: <input name="thickness"><br><br>
        Original Length: <input name="original_length"><br><br>
        Color: <input name="color"><br><br>
        Batch: <input name="batch"><br><br>
        Manufacturing Date: <input type="date" name="manufacturing_date"><br><br>
        Purchase Date: <input type="date" name="purchase_date"><br><br>
        Customer Password: <input type="password" name="customer_password"><br><br>
        <button type="submit">Create Rope</button>
    </form>
    """

@app.route("/admin/create", methods=["POST"])
@requires_auth
def create_rope():
    rope_id = generate_rope_id()

    password_hash = bcrypt.hashpw(
        request.form["customer_password"].encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO ropes (
            rope_id, product_name, thickness, original_length,
            color, batch, manufacturing_date, purchase_date,
            customer_password_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        rope_id,
        request.form["product_name"],
        request.form["thickness"],
        request.form["original_length"],
        request.form["color"],
        request.form["batch"],
        request.form["manufacturing_date"],
        request.form["purchase_date"],
        password_hash
    ))

    conn.commit()
    cur.close()
    conn.close()

    return f"""
    <h3>Rope Created Successfully!</h3>
    <p><strong>Rope ID:</strong> {rope_id}</p>
    <p>Share this ID in the NFC tag.</p>
    <a href="/admin">Create Another Rope</a>
    """

if __name__ == "__main__":
    app.run()
