import sqlite3

# Cek koneksi database dan isi tabel Users
conn = sqlite3.connect("pharmily.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM Users")
users = cursor.fetchall()
print(users)
conn.close()