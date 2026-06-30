import sqlite3
conn = sqlite3.connect('dev.db')
print(conn.execute('SELECT * FROM alembic_version;').fetchall())
conn.close()