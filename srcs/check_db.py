import sqlite3

# 连接数据库
conn = sqlite3.connect('book.db')
c = conn.cursor()

# 检查书籍表结构
print("=== 书籍表结构 ===")
c.execute('PRAGMA table_info(books)')
columns = c.fetchall()
for col in columns:
    print(f"列名: {col[1]}, 类型: {col[2]}, 默认值: {col[4]}")

# 检查用户表结构
print("\n=== 用户表结构 ===")
c.execute('PRAGMA table_info(users)')
columns = c.fetchall()
for col in columns:
    print(f"列名: {col[1]}, 类型: {col[2]}, 默认值: {col[4]}")

# 检查书籍数据
print("\n=== 书籍数据 ===")
c.execute('SELECT id, title, likes FROM books LIMIT 5')
rows = c.fetchall()
for row in rows:
    print(f"ID: {row[0]}, 书名: {row[1]}, 点赞数: {row[2]}")

# 检查用户数据
print("\n=== 用户数据 ===")
c.execute('SELECT id, username, email, created_at FROM users LIMIT 5')
rows = c.fetchall()
for row in rows:
    print(f"ID: {row[0]}, 用户名: {row[1]}, 邮箱: {row[2]}, 创建时间: {row[3]}")

conn.close() 