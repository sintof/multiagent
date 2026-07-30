"""
Seeds data/company.db for the text-to-SQL agent (F5). Synthetic data for a fictional
company "Northwind Analytics" — matches the narrative in sample_company_notes.txt
(Q3 churn spike, starter-tier driven, slow support response) so retriever + SQL agent
tell a consistent story when tested together later.
"""

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "company.db"

random.seed(42)


def build():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            tier TEXT NOT NULL,               -- 'starter' or 'enterprise'
            signup_quarter TEXT NOT NULL,      -- 'Q1','Q2','Q3'
            status TEXT NOT NULL,              -- 'active' or 'churned'
            churn_quarter TEXT                 -- NULL if active
        )
    """)
    cur.execute("""
        CREATE TABLE support_tickets (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            response_hours REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    customers = []
    cid = 1

    # Starter tier: 100 customers. 3 churned Q2 (2.9%), 4 churned Q3 (4.2%, rounding to match notes)
    for i in range(100):
        churn_q = None
        status = "active"
        if i < 3:
            status, churn_q = "churned", "Q2"
        elif i < 7:
            status, churn_q = "churned", "Q3"
        customers.append((cid, "starter", "Q1", status, churn_q))
        cid += 1

    # Enterprise tier: 12 customers, none churned, 3 expanded (handled at revenue-narrative level only)
    for i in range(12):
        customers.append((cid, "enterprise", "Q1", "active", None))
        cid += 1

    cur.executemany(
        "INSERT INTO customers (id, tier, signup_quarter, status, churn_quarter) VALUES (?,?,?,?,?)",
        customers,
    )

    tickets = []
    tid = 1
    for cust_id, tier, _, _, _ in customers:
        for quarter in ("Q1", "Q2", "Q3"):
            # Starter tier support got slow in Q3 (avg ~36h); enterprise stayed fast (~8-10h)
            if tier == "starter" and quarter == "Q3":
                hours = random.uniform(28, 44)
            elif tier == "starter":
                hours = random.uniform(8, 14)
            else:
                hours = random.uniform(4, 10)
            tickets.append((tid, cust_id, quarter, round(hours, 1)))
            tid += 1

    cur.executemany(
        "INSERT INTO support_tickets (id, customer_id, quarter, response_hours) VALUES (?,?,?,?)",
        tickets,
    )

    conn.commit()
    conn.close()
    print(f"seeded {DB_PATH} — {len(customers)} customers, {len(tickets)} tickets")


if __name__ == "__main__":
    build()
