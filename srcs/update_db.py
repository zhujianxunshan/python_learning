import sqlite3
import os

# 检查数据库是否存在
if os.path.exists('book.db'):
    print("发现现有数据库，正在更新结构...")
    
    conn = sqlite3.connect('book.db')
    c = conn.cursor()
    
    # 检查是否已经有likes列
    c.execute('PRAGMA table_info(books)')
    columns = [col[1] for col in c.fetchall()]
    
    if 'likes' not in columns:
        print("添加likes列...")
        try:
            c.execute('ALTER TABLE books ADD COLUMN likes INTEGER DEFAULT 0')
            conn.commit()
            print("成功添加likes列")
        except Exception as e:
            print(f"添加列时出错: {e}")
    else:
        print("likes列已存在")
    
    # 更新现有数据的likes值为0
    c.execute('UPDATE books SET likes = 0 WHERE likes IS NULL')
    conn.commit()
    print("更新现有数据的点赞数")
    
    conn.close()
else:
    print("数据库不存在，将在启动应用时自动创建")

print("数据库更新完成！") 