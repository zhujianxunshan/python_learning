import sqlite3
import torch
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
import numpy as np
import os
DB_PATH = os.path.join(os.path.dirname(__file__), 'book.db')

# 1. 构建user-book二分图
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT id FROM users')
user_ids = [row[0] for row in c.fetchall()]
c.execute('SELECT id FROM books')
book_ids = [row[0] for row in c.fetchall()]
user_id_map = {uid: i for i, uid in enumerate(user_ids)}
book_id_map = {bid: i for i, bid in enumerate(book_ids)}
num_users = len(user_ids)
num_books = len(book_ids)

c.execute('SELECT user_id, book_id FROM likes')
edges = [(user_id_map[u], num_users + book_id_map[b]) for u, b in c.fetchall()]
edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
conn.close()

# 2. 构造PyG Data对象
x = torch.eye(num_users + num_books)  # one-hot特征
data = Data(x=x, edge_index=edge_index)

# 3. 定义GNN模型
class GCN(torch.nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = GCNConv(in_channels, 64)
        self.conv2 = GCNConv(64, out_channels)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index)
        return x

model = GCN(num_users + num_books, 32)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
criterion = torch.nn.BCEWithLogitsLoss()

# 4. 训练
for epoch in range(300):
    model.train()
    optimizer.zero_grad()
    out = model(data)
    # 只训练边上的节点对为1，负采样为0
    pos = out[edge_index[0]] * out[edge_index[1]]
    pos_score = pos.sum(dim=1)
    neg_edge = torch.randint(0, num_users + num_books, edge_index.shape, dtype=torch.long)
    neg = out[neg_edge[0]] * out[neg_edge[1]]
    neg_score = neg.sum(dim=1)
    loss = criterion(pos_score, torch.ones_like(pos_score)) + criterion(neg_score, torch.zeros_like(neg_score))
    loss.backward()
    optimizer.step()
    if epoch % 10 == 0:
        print(f"Epoch {epoch}, Loss: {loss.item()}")

# 5. 保存embedding
embeddings = out.detach().numpy()
np.savez('gnn_embeddings.npz', 
         user_ids=user_ids, 
         book_ids=book_ids, 
         embeddings=embeddings)
print("Embedding saved.")