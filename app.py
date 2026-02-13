from flask import Flask, jsonify, request, Response, render_template, redirect
import psycopg2
import os
import bcrypt
import random
import string
from datetime import datetime, timedelta
from functools import wraps
from supabase import create_client, Client



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


# ---------------- LANDING PAGE ----------------
@app.route("/")
def landing_page():
    return """
    <html>
    <head>
        <title>Rope Tracking</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Rope Tracking System</h1>
            <p>Please scan your NFC tag to view rope details.</p>
        </div>
    </body>
    </html>
    """

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
        return "Rope not found", 404

    rope = {
        "rope_id": row[0],
        "product_name": row[1],
        "thickness": row[2],
        "original_length": row[3],
        "color": row[4],
        "batch": row[5],
        "manufacturing_date": row[6],
        "purchase_date": row[7],
    }

    status = compute_status(rope_id, rope["purchase_date"])

    if status == "ACTIVE":
        status_color = "green"
    elif status == "INSPECTION DUE":
        status_color = "orange"
    else:
        status_color = "red"

    cur.execute("""
        SELECT image_url FROM product_variants
        WHERE product_name = %s AND color = %s
        LIMIT 1
    """, (rope["product_name"], rope["color"]))

    variant = cur.fetchone()
    image_url = variant[0] if variant else None

    cur.close()
    conn.close()

    return render_template(
        "overview.html",
        rope=rope,
        status=status,
        status_color=status_color,
        image_url=image_url
    )




@app.route("/rope/<rope_id>/inspections")
def inspection_list(rope_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT inspection_date, comment
        FROM inspection_logs
        WHERE rope_id = %s
        ORDER BY inspection_date DESC
    """, (rope_id,))

    rows = cur.fetchall()

    inspections = [
        {
            "inspection_date": r[0],
            "comment": r[1]
        }
        for r in rows
    ]

    cur.close()
    conn.close()

    return render_template(
        "inspections.html",
        rope_id=rope_id,
        inspections=inspections
    )


@app.route("/rope/<rope_id>/inspections/add-new", methods=["GET", "POST"])
@requires_auth
def add_inspection(rope_id):
    if request.method == "POST":
        inspection_date_str = request.form["inspection_date"]
        comment = request.form["comment"]

        inspection_date = datetime.strptime(inspection_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        if inspection_date > today:
            return "Inspection date cannot be in the future", 400

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT 1 FROM inspection_logs
            WHERE rope_id = %s AND inspection_date = %s
        """, (rope_id, inspection_date))

        if cur.fetchone():
            cur.close()
            conn.close()
            return "Inspection already recorded for this date", 400

        cur.execute("""
            INSERT INTO inspection_logs (rope_id, inspection_date, comment)
            VALUES (%s, %s, %s)
        """, (rope_id, inspection_date, comment))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(f"/rope/{rope_id}/inspections")

    return render_template("add_inspection.html", rope_id=rope_id)



@app.route("/rope/<rope_id>/falls")
def fall_list(rope_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT fall_date, fall_type, comment
        FROM fall_logs
        WHERE rope_id = %s
        ORDER BY fall_date DESC
    """, (rope_id,))

    rows = cur.fetchall()

    falls = [
        {
            "fall_date": r[0],
            "fall_type": r[1],
            "comment": r[2]
        }
        for r in rows
    ]

    cur.close()
    conn.close()

    return render_template(
        "falls.html",
        rope_id=rope_id,
        falls=falls
    )



@app.route("/rope/<rope_id>/falls/add-new", methods=["GET", "POST"])
@requires_auth
def add_fall(rope_id):
    if request.method == "POST":
        fall_date_str = request.form["fall_date"]
        fall_type = request.form["fall_type"]
        comment = request.form["comment"]

        fall_date = datetime.strptime(fall_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        if fall_date > today:
            return "Fall date cannot be in the future", 400

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO fall_logs (rope_id, fall_date, fall_type, comment)
            VALUES (%s, %s, %s, %s)
        """, (rope_id, fall_date, fall_type, comment))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(f"/rope/{rope_id}/falls")

    return render_template("add_fall.html", rope_id=rope_id)




# ---------------- ADMIN PANEL ----------------

@app.route("/admin")
@requires_auth
def admin_page():
    return render_template("admin.html")


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

    full_url = request.host_url.rstrip("/") + f"/rope/{rope_id}"

    return render_template(
        "rope_created.html",
        rope_id=rope_id,
        full_url=full_url
    )



# ------------- INVALID URL --------------

@app.errorhandler(404)
def page_not_found(e):
    return """
    <html>
    <body style="font-family:Arial;text-align:center;padding:50px;">
        <h2>404 - Page Not Found</h2>
        <p>The link you accessed is invalid.</p>
        <a href="/">Go to Home</a>
    </body>
    </html>
    """, 404



if __name__ == "__main__":
    app.run()


