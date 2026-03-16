from flask import request, jsonify
import psycopg2
import os


def get_conn():

    return psycopg2.connect(
        dbname="curionest_db",
        user="postgres",
        password=os.getenv("DB_PASSWORD"),
        host="localhost",
        port="5432"
    )


def capture_lead():

    data = request.get_json()

    lead_id = data.get("lead_id")
    name = data.get("name")
    email = data.get("email")
    phone = data.get("mobile")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO lead_contacts
        (lead_id,name,email,phone)
        VALUES (%s,%s,%s,%s)
        """,
        (lead_id,name,email,phone)
    )

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status":"lead_saved"})