import os
import sqlite3
import hashlib
import secrets
from flask import Flask, jsonify, send_from_directory, request, session
from werkzeug.utils import secure_filename
from collections import Counter
import re
import numpy as np

EMBEDDING_PATH = os.path.join(os.path.dirname(__file__), 'gnn_embeddings.npz')
if os.path.exists(EMBEDDING_PATH):
    gnn_data = np.load(EMBEDDING_PATH, allow_pickle=True)
    user_ids = list(gnn_data['user_ids'])
    book_ids = list(gnn_data['book_ids'])
    embeddings = gnn_data['embeddings']
else:
    gnn_data = None
    user_ids = []
    book_ids = []
    embeddings = None

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'your-secret-key-here'  # 用于session加密
DB_PATH = os.path.join(os.path.dirname(__file__), 'book.db')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'covers')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 创建书籍表
    c.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        description TEXT,
        categories TEXT,
        cover TEXT,
        detail_url TEXT,
        likes INTEGER DEFAULT 0
    )''')
    
    # 创建用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 新增点赞表
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, book_id)
    )''')
    
    # 新增浏览表
    c.execute('''CREATE TABLE IF NOT EXISTS views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    """对密码进行哈希处理"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """验证密码"""
    return hash_password(password) == password_hash

@app.route('/')
def index():
    # 返回 web.html
    return send_from_directory(os.path.dirname(__file__), 'web.html')

@app.route('/register.html')
def register_page():
    # 返回注册页面
    return send_from_directory(os.path.dirname(__file__), 'register.html')

# 用户注册API
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    # 验证输入
    if not username or not email or not password:
        return jsonify({'error': '所有字段都是必填的'}), 400
    
    if len(username) < 3:
        return jsonify({'error': '用户名至少需要3个字符'}), 400
    
    if len(password) < 8:
        return jsonify({'error': '密码至少需要8个字符'}), 400
    
    # 验证邮箱格式
    if '@' not in email or '.' not in email:
        return jsonify({'error': '请输入有效的邮箱地址'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 检查用户名是否已存在
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        if c.fetchone():
            conn.close()
            return jsonify({'error': '用户名已存在'}), 400
        
        # 检查邮箱是否已存在
        c.execute('SELECT id FROM users WHERE email = ?', (email,))
        if c.fetchone():
            conn.close()
            return jsonify({'error': '邮箱已被注册'}), 400
        
        # 创建新用户
        password_hash = hash_password(password)
        c.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                  (username, email, password_hash))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '注册成功！'})
        
    except Exception as e:
        return jsonify({'error': '注册失败，请稍后重试'}), 500

# 用户登录API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username_or_email = data.get('username_or_email', '').strip()
    password = data.get('password', '').strip()
    
    # 验证输入
    if not username_or_email or not password:
        return jsonify({'error': '用户名/邮箱和密码都是必填的'}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 查找用户（支持用户名或邮箱登录）
        c.execute('SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?',
                  (username_or_email, username_or_email))
        user = c.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': '用户名/邮箱或密码错误'}), 401
        
        user_id, username, email, password_hash = user
        
        # 验证密码
        if not verify_password(password, password_hash):
            return jsonify({'error': '用户名/邮箱或密码错误'}), 401
        
        # 设置session
        session['user_id'] = user_id
        session['username'] = username
        session['email'] = email
        
        return jsonify({
            'success': True, 
            'message': '登录成功！',
            'user': {
                'id': user_id,
                'username': username,
                'email': email
            }
        })
        
    except Exception as e:
        return jsonify({'error': '登录失败，请稍后重试'}), 500

# 用户登出API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': '已成功登出'})

# 获取当前用户信息API
@app.route('/api/user', methods=['GET'])
def get_current_user():
    if 'user_id' in session:
        return jsonify({
            'success': True,
            'user': {
                'id': session['user_id'],
                'username': session['username'],
                'email': session['email']
            }
        })
    else:
        return jsonify({'success': False, 'user': None})

# 检查用户是否已登录的装饰器
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/api/random_book')
def random_book():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM books ORDER BY RANDOM() LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify(row_to_book(row))
    return jsonify({"error": "没有书籍"}), 404

@app.route('/api/books')
def get_books():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM books')
    rows = c.fetchall()
    conn.close()
    return jsonify([row_to_book(row) for row in rows])

@app.route('/api/recommend', methods=['POST'])
def recommend():
    # 简单实现：随机推荐3本未被选择的书
    data = request.get_json()
    selected_ids = data.get('selected_ids', [])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = 'SELECT * FROM books WHERE id NOT IN ({}) ORDER BY RANDOM() LIMIT 3'.format(
        ','.join(['?']*len(selected_ids)) if selected_ids else '0')
    c.execute(q, selected_ids)
    rows = c.fetchall()
    conn.close()
    return jsonify([row_to_book(row) for row in rows])

@app.route('/api/add_book', methods=['POST'])
def add_book():
    data = request.get_json()
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    categories = data.get('categories', '').strip()
    # 统一多分隔符为英文逗号
    if categories:
        cats = re.split(r'[，,|\s]+', categories)
        categories = ','.join([c for c in cats if c])
    cover = data.get('cover', '').strip()
    description = data.get('description', '').strip()
    if not title or not author:
        return jsonify({'error': '书名和作者不能为空'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO books (title, author, description, categories, cover, detail_url, likes) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (title, author, description, categories, cover, data.get('detail_url', ''), 0))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/like_book', methods=['POST'])
@login_required
def like_book():
    data = request.get_json()
    book_id = data.get('id')
    user_id = session.get('user_id')
    if not book_id:
        return jsonify({'error': '缺少书籍id'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 检查是否已点赞
    c.execute('SELECT 1 FROM likes WHERE user_id=? AND book_id=?', (user_id, book_id))
    if c.fetchone():
        conn.close()
        return jsonify({'error': '你已经点赞过该书籍'}), 400
    # 写入likes表
    c.execute('INSERT INTO likes (user_id, book_id) VALUES (?, ?)', (user_id, book_id))
    # 更新books表的likes字段（可选，或直接统计likes表）
    c.execute('UPDATE books SET likes = (SELECT COUNT(*) FROM likes WHERE book_id=?) WHERE id=?', (book_id, book_id))
    conn.commit()
    # 获取最新点赞数
    c.execute('SELECT likes FROM books WHERE id = ?', (book_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return jsonify({'success': True, 'likes': result[0]})
    return jsonify({'error': '书籍不存在'}), 404

@app.route('/api/view_book', methods=['POST'])
@login_required
def view_book():
    data = request.get_json()
    book_id = data.get('id')
    user_id = session.get('user_id')
    if not book_id:
        return jsonify({'error': '缺少书籍id'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO views (user_id, book_id) VALUES (?, ?)', (user_id, book_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/user_profile', methods=['GET'])
@login_required
def user_profile():
    user_id = session.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 统计点赞最多的类别和作者
    c.execute('''SELECT b.categories, COUNT(*) as cnt FROM likes l JOIN books b ON l.book_id = b.id WHERE l.user_id=? GROUP BY b.categories ORDER BY cnt DESC LIMIT 3''', (user_id,))
    fav_categories = []
    for row in c.fetchall():
        if row[0]:
            fav_categories.extend([cat for cat in re.split(r'[，,|\s]+', row[0]) if cat])
    c.execute('''SELECT b.author, COUNT(*) as cnt FROM likes l JOIN books b ON l.book_id = b.id WHERE l.user_id=? GROUP BY b.author ORDER BY cnt DESC LIMIT 3''', (user_id,))
    fav_authors = [row[0] for row in c.fetchall() if row[0]]
    # 统计最近浏览的书籍
    c.execute('''SELECT b.title FROM views v JOIN books b ON v.book_id = b.id WHERE v.user_id=? ORDER BY v.timestamp DESC LIMIT 5''', (user_id,))
    recent_views = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({
        'fav_categories': fav_categories,
        'fav_authors': fav_authors,
        'recent_views': recent_views
    })

@app.route('/api/upload_cover', methods=['POST'])
def upload_cover():
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    # 避免重名覆盖
    base, ext = os.path.splitext(filename)
    i = 1
    while os.path.exists(save_path):
        filename = f"{base}_{i}{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        i += 1
    file.save(save_path)
    url = f"/static/covers/{filename}"
    return jsonify({'url': url})

@app.route('/api/delete_book', methods=['POST'])
def delete_book():
    data = request.get_json()
    book_id = data.get('id')
    if not book_id:
        return jsonify({'error': '缺少书籍id'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM books WHERE id=?', (book_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

def old_recommend_by_profile():
    # 这里用你原来的内容推荐逻辑，或随机推荐3本未看过的书
    user_id = session.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT book_id FROM likes WHERE user_id=?', (user_id,))
    liked_ids = set(row[0] for row in c.fetchall())
    c.execute('SELECT book_id FROM views WHERE user_id=?', (user_id,))
    viewed_ids = set(row[0] for row in c.fetchall())
    exclude_ids = liked_ids | viewed_ids
    q = 'SELECT * FROM books'
    params = []
    if exclude_ids:
        q += ' WHERE id NOT IN ({})'.format(','.join(['?']*len(exclude_ids)))
        params = list(exclude_ids)
    q += ' ORDER BY RANDOM() LIMIT 3'
    c.execute(q, params)
    books = [row_to_book(row) for row in c.fetchall()]
    conn.close()
    return jsonify(books)

@app.route('/api/recommend_by_profile', methods=['GET'])
@login_required
def recommend_by_profile():
    user_id = session.get('user_id')
    print("当前用户id:", user_id)
    print("embedding文件user_ids:", user_ids)
    if not gnn_data or user_id not in user_ids:
        print("GNN embedding 不存在或用户不在embedding中，回退推荐")
        return old_recommend_by_profile()
    user_idx = user_ids.index(user_id)
    user_emb = embeddings[user_idx]
    # 过滤掉已点赞/浏览的书
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT book_id FROM likes WHERE user_id=?', (user_id,))
    liked_ids = set(row[0] for row in c.fetchall())
    c.execute('SELECT book_id FROM views WHERE user_id=?', (user_id,))
    viewed_ids = set(row[0] for row in c.fetchall())
    exclude_ids = liked_ids | viewed_ids
    conn.close()
    print("排除的书籍id:", exclude_ids)
    # 计算所有未看过书的相似度
    book_scores = []
    for i, bid in enumerate(book_ids):
        if bid in exclude_ids:
            continue
        book_emb = embeddings[len(user_ids) + i]
        score = np.dot(user_emb, book_emb)
        book_scores.append((bid, score))
    print("GNN推荐分数:", book_scores)
    # 取分数最高的3本
    top_books = sorted(book_scores, key=lambda x: -x[1])[:3]
    print("GNN推荐top3:", top_books)
    result = []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for bid, _ in top_books:
        c.execute('SELECT * FROM books WHERE id=?', (int(bid),))
        row = c.fetchone()
        if row:
            result.append(row_to_book(row))
    conn.close()
    # 如果推荐为空，回退到原有推荐
    if not result:
        print("GNN推荐结果为空，回退推荐")
        return old_recommend_by_profile()
    print("GNN最终推荐结果:", result)
    return jsonify(result)

def row_to_book(row):
    return {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'description': row[3],
        'categories': re.split(r'[，,|\s]+', row[4]) if row[4] else [],
        'cover': row[5],
        'detail_url': row[6] if len(row) > 6 else '',
        'likes': row[7] if len(row) > 7 else 0
    }

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)