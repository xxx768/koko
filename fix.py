import sqlite3
conn = sqlite3.connect('dev.db')
conn.execute("UPDATE alembic_version SET version_num = '32cc6a2848f3';")
conn.commit()
conn.close()
print('done')