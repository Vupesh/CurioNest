from flask import request, jsonify
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def capture_lead():

    try:

        data = request.get_json()

        session_id = data.get("session_id")
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")

        if not session_id:
            return jsonify({
                "status": "error",
                "message": "session_id required"
            }), 400

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        # get latest lead for session

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
                "message": "lead not found"
            }), 404

        lead_id = row[0]

        # insert contact

        cur.execute("""
            INSERT INTO lead_contacts
            (lead_id, name, email, phone)
            VALUES (%s,%s,%s,%s)
        """, (lead_id, name, email, phone))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({
            "status": "success"
        })

    except Exception as e:

        print("CAPTURE LEAD ERROR:", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500