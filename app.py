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
            h1 {
                margin-bottom: 10px;
            }
            p {
                color: #555;
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

    inspections = cur.fetchall()

    cur.close()
    conn.close()

    rows_html = ""
    for i in inspections:
        rows_html += f"""
        <tr>
            <td>{i[0]}</td>
            <td>{i[1] or ""}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Inspection Log</title>
        <style>
            body {{ font-family: Arial; padding: 30px; background:#f5f5f5; }}
            .card {{
                background:white;
                padding:20px;
                border-radius:10px;
                max-width:700px;
                margin:auto;
                box-shadow:0 4px 10px rgba(0,0,0,0.1);
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                margin-top:15px;
            }}
            th, td {{
                border:1px solid #ddd;
                padding:8px;
                text-align:left;
            }}
            th {{ background:#f0f0f0; }}
            .btn {{
                display:inline-block;
                padding:8px 12px;
                background:#007BFF;
                color:white;
                text-decoration:none;
                border-radius:5px;
                margin-top:15px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Inspection Log - {rope_id}</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Comment</th>
                </tr>
                {rows_html}
            </table>

            <a class="btn" href="/rope/{rope_id}/inspections/add-new">Add Inspection</a>
            <br><br>
            <a href="/rope/{rope_id}">← Back to Overview</a>
        </div>
    </body>
    </html>
    """

@app.route("/rope/<rope_id>/inspections/add-new", methods=["GET", "POST"])
@requires_auth
def add_inspection(rope_id):
    if request.method == "POST":
        inspection_date_str = request.form["inspection_date"]
        comment = request.form["comment"]

        inspection_date = datetime.strptime(inspection_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        # 1️⃣ Prevent future date
        if inspection_date > today:
            return "<h3>Error: Inspection date cannot be in the future.</h3><a href=''>Go Back</a>"

        conn = get_connection()
        cur = conn.cursor()

        # 2️⃣ Prevent duplicate inspection on same date
        cur.execute("""
            SELECT 1 FROM inspection_logs
            WHERE rope_id = %s AND inspection_date = %s
        """, (rope_id, inspection_date))

        if cur.fetchone():
            cur.close()
            conn.close()
            return "<h3>Error: Inspection already recorded for this date.</h3><a href=''>Go Back</a>"

        cur.execute("""
            INSERT INTO inspection_logs (rope_id, inspection_date, comment)
            VALUES (%s, %s, %s)
        """, (rope_id, inspection_date, comment))

        conn.commit()
        cur.close()
        conn.close()

        return f"""
        <h3>Inspection Added Successfully</h3>
        <a href="/rope/{rope_id}/inspections">Back to Inspection Log</a>
        """

    return f"""
    <html>
    <body style="font-family:Arial;padding:30px;">
        <h2>Add Inspection - {rope_id}</h2>
        <form method="POST">
            Date: <input type="date" name="inspection_date" required><br><br>
            Comment: <input type="text" name="comment"><br><br>
            <button type="submit">Submit</button>
        </form>
        <br>
        <a href="/rope/{rope_id}/inspections">← Back</a>
    </body>
    </html>
    """



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

    falls = cur.fetchall()

    cur.close()
    conn.close()

    rows_html = ""
    for f in falls:
        rows_html += f"""
        <tr>
            <td>{f[0]}</td>
            <td>{f[1]}</td>
            <td>{f[2] or ""}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Fall Records</title>
    </head>
    <body style="font-family:Arial;padding:30px;background:#f5f5f5;">
        <div style="background:white;padding:20px;border-radius:10px;max-width:700px;margin:auto;">
            <h2>Fall Records - {rope_id}</h2>
            <table border="1" width="100%" cellpadding="8">
                <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Comment</th>
                </tr>
                {rows_html}
            </table>

            <br>
            <a href="/rope/{rope_id}/falls/add-new">Add Fall Record</a>
            <br><br>
            <a href="/rope/{rope_id}">← Back to Overview</a>
        </div>
    </body>
    </html>
    """


@app.route("/rope/<rope_id>/falls/add-new", methods=["GET", "POST"])
@requires_auth
def add_fall(rope_id):
    if request.method == "POST":
        fall_date_str = request.form["fall_date"]
        fall_type = request.form["fall_type"]
        comment = request.form["comment"]

        fall_date = datetime.strptime(fall_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        # 1️⃣ Prevent future date
        if fall_date > today:
            return "<h3>Error: Fall date cannot be in the future.</h3><a href=''>Go Back</a>"

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO fall_logs (rope_id, fall_date, fall_type, comment)
            VALUES (%s, %s, %s, %s)
        """, (rope_id, fall_date, fall_type, comment))

        conn.commit()
        cur.close()
        conn.close()

        return f"""
        <h3>Fall Record Added</h3>
        <a href="/rope/{rope_id}/falls">Back to Fall Records</a>
        """

    return f"""
    <html>
    <body style="font-family:Arial;padding:30px;">
        <h2>Add Fall Record - {rope_id}</h2>
        <form method="POST">
            Date: <input type="date" name="fall_date" required><br><br>
            Type:
            <select name="fall_type">
                <option value="major">Major</option>
                <option value="minor">Minor</option>
            </select><br><br>
            Comment: <input type="text" name="comment"><br><br>
            <button type="submit">Submit</button>
        </form>
        <br>
        <a href="/rope/{rope_id}/falls">← Back</a>
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

 full_url = request.host_url.rstrip("/") + f"/rope/{rope_id}"

return f"""
<h3>Rope Created Successfully!</h3>
<p><strong>Rope ID:</strong> {rope_id}</p>
<p><strong>Rope Link:</strong></p>
<p>
    <a href="{full_url}" target="_blank">
        {full_url}
    </a>
</p>
<p>Use this full link for the NFC tag.</p>
<br>
<a href="/admin">Create Another Rope</a>
"""




if __name__ == "__main__":
    app.run()


@app.errorhandler(404)
def page_not_found(e):
    return """
    <html>
    <body style="font-family:Arial;text-align:center;padding:50px;">
        <h2>Page Not Found</h2>
        <p>The link you accessed is invalid.</p>
        <a href="/">Go to Home</a>
    </body>
    </html>
    """, 404



