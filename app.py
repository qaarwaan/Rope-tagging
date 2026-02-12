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
        return "<h2>Rope not found</h2>", 404

    purchase_date = row[7]
    status = compute_status(rope_id, purchase_date)

    cur.close()
    conn.close()

    # Status color logic
    if status == "ACTIVE":
        status_color = "green"
    elif status == "INSPECTION DUE":
        status_color = "orange"
    else:
        status_color = "red"

    return f"""
    <html>
    <head>
        <title>Rope {row[0]}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                padding: 30px;
            }}
            .card {{
                background: white;
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: auto;
            }}
            h1 {{
                margin-top: 0;
            }}
            .status {{
                padding: 8px 15px;
                border-radius: 20px;
                color: white;
                display: inline-block;
                background-color: {status_color};
                font-weight: bold;
            }}
            .label {{
                font-weight: bold;
            }}
            .row {{
                margin-bottom: 10px;
            }}
            .buttons {{
                margin-top: 20px;
            }}
            .btn {{
                display: inline-block;
                padding: 8px 12px;
                background-color: #007BFF;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Rope ID: {row[0]}</h1>

            <div class="row"><span class="label">Product:</span> {row[1]}</div>
            <div class="row"><span class="label">Thickness:</span> {row[2]}</div>
            <div class="row"><span class="label">Original Length:</span> {row[3]}</div>
            <div class="row"><span class="label">Color:</span> {row[4]}</div>
            <div class="row"><span class="label">Batch:</span> {row[5]}</div>
            <div class="row"><span class="label">Manufacturing Date:</span> {row[6]}</div>
            <div class="row"><span class="label">Purchase Date:</span> {row[7]}</div>

            <div class="row">
                <span class="label">Status:</span>
                <span class="status">{status}</span>
            </div>

            <div class="buttons">
                <a class="btn" href="/rope/{row[0]}/inspections">Inspection Log</a>
                <a class="btn" href="/rope/{row[0]}/falls">Fall Records</a>
            </div>
        </div>
    </body>
    </html>
    """


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
