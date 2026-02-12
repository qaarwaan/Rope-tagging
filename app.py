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
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return True

    # Check customer login
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT customer_password_hash FROM ropes WHERE rope_id = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            stored_hash = row[0].encode()
            return bcrypt.checkpw(password.encode(), stored_hash)

    except:
        return False

    return False


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
    ret
