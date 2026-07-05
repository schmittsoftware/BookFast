import sqlite3

conn = sqlite3.connect("var/boekvast.db")
c = conn.cursor()

c.execute("SELECT id, client_id FROM actions WHERE case_id IS NULL AND kind = 'deadline'")
actions = c.fetchall()

for action_id, client_id in actions:
    c.execute("SELECT id FROM cases WHERE client_id = ? ORDER BY period DESC LIMIT 1", (client_id,))
    case_row = c.fetchone()
    if case_row:
        c.execute("UPDATE actions SET case_id = ? WHERE id = ?", (case_row[0], action_id))

conn.commit()
conn.close()
