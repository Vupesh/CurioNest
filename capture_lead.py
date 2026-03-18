import re
import os
import psycopg2

from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

EMAIL_REGEX = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
PHONE_REGEX = r"^[0-9]{10}$"


def capture_lead():

    conn = None
    cur = None

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Invalid request payload"
            }), 400

        session_id = data.get("session_id")
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        phone = (data.get("phone") or "").strip()

        # -----------------------------
        # Validation
        # -----------------------------

        if not session_id:
            return jsonify({
                "status": "error",
                "message": "session_id required"
            }), 400

        if not name:
            return jsonify({
                "status": "error",
                "message": "Name required"
            }), 400

        if not re.match(EMAIL_REGEX, email):
            return jsonify({
                "status": "error",
                "message": "Invalid email"
            }), 400

        if not re.match(PHONE_REGEX, phone):
            return jsonify({
                "status": "error",
                "message": "Invalid phone number"
            }), 400

        # -----------------------------
        # DB Connection
        # -----------------------------

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        # -----------------------------
        # Find Lead Session
        # -----------------------------

        cur.execute("""
            SELECT id
            FROM leads
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (session_id,))

        row = cur.fetchone()

        if not row:
            return jsonify({
                "status": "error",
                "message": "Lead not found for session"
            }), 404

        lead_id = row[0]

        # -----------------------------
        # Prevent Duplicate Contact
        # -----------------------------

        cur.execute("""
            SELECT id
            FROM lead_contacts
            WHERE lead_id = %s
        """, (lead_id,))

        existing = cur.fetchone()

        if existing:

            return jsonify({
                "status": "success",
                "message": "Lead already captured"
            })

        # -----------------------------
        # Insert Contact
        # -----------------------------

        cur.execute("""
            INSERT INTO lead_contacts
            (lead_id, name, email, phone)
            VALUES (%s, %s, %s, %s)
        """, (lead_id, name, email, phone))

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Lead captured successfully"
        })

    except Exception as e:

        print("CAPTURE LEAD ERROR:", e)

        if conn:
            conn.rollback()

        return jsonify({
            "status": "error",
            "message": "Internal error capturing lead"
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()