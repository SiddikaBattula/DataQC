# import mysql.connector
# from dotenv import load_dotenv
# import os

# load_dotenv()

# conn = mysql.connector.connect(
#     host="192.168.1.138",
#     user=os.getenv("DB_USERNAME"),
#     password=os.getenv("DB_PASSWORD"),
#     port=int(os.getenv("DB_PORT")),
#     database="DK-1140-1-wc"
# )

# cursor = conn.cursor()

# print("\n=== TABLES ===")
# cursor.execute("SHOW TABLES")
# for table in cursor.fetchall():
#     print(table[0])

# # print("\n=== DRILLING COLUMNS ===")
# # cursor.execute("DESCRIBE Drilling")
# # for column in cursor.fetchall():
# #     print(column)

# # print("\n=== SAMPLE DATA ===")
# # cursor = conn.cursor(dictionary=True)
# # cursor.execute("SELECT * FROM Drilling LIMIT 5")

# # for row in cursor.fetchall():
# #     print(row)

# conn.close()





import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host="192.168.1.138",
    user=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    port=int(os.getenv("DB_PORT")),
    database="lkbl-1-wc",
    charset="utf8"
)

print("Connected Successfully")

cursor = conn.cursor()


# cursor.execute("SHOW TABLES FROM `dk-1140-1-wc`;")
# cursor.execute("SHOW COLUMNS FROM drilling")
# cursor.execute("SELECT * FROM drilling LIMIT 5")
# cursor.execute("""
#     SELECT *
#     FROM drilling
#     ORDER BY TIME DESC
#     LIMIT 10
# """)

cursor.execute("SELECT * FROM drilling WHERE DMEA BETWEEN 300 AND 1035")

# cursor.execute("SELECT COUNT(*) FROM cutting")

rows = cursor.fetchall()


for row in rows:
    print(row)


conn.close()