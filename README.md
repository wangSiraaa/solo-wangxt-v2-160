# 技术选型多准则分析台（MCDA：显式 WSM + TOPSIS）

> 一个总分不能掩盖成本与收益方向写反。本项目把**指标方向、单位、权重来源、每一步转换、
> 排名对候选集合的依赖**全部摊开给委员会复核；算法排序是给定口径下的参考，不包装成客观唯一最佳选择。

## 它刻意展示什么

| 议题 | 处理方式 |
|---|---|
| 收益型 / 成本型 / 目标区间型方向 | 三类指标分别规范化（min-max 反向 / 区间内=1 向外衰减），成本型绝不会变成"越大越好" |
| 常量列 | 不自动给满分：默认从加权计算剔除并重分配权重；显式保留时恒为中性 0.5（不是 1） |
| 缺失值 | 中位数（默认）/ 均值 / 最差 0 三种插补，单元格描边标注，**绝不插补成满分** |
| 极端异常值 | MAD 修正 z 分数先**只标记**；用户显式开启才裁剪（MAD / P5–P95），步骤矩阵可见变化 |
| 权重可核对 | 人工权重原始合计不要求=100，有效指标内归一；每行列出人工来源（评审会/财务模型） |
| 人工 vs 数据推得 | 熵权法（SciPy/NumPy）单独一列，纯熵权/纯人工/α 组合三种口径可切换 |
| 重复指标 | Pearson + Spearman 双阈值（>0.98）检出，提示"双重加权"，可一键移出再看排名 |
| 增删候选的排名逆转 | `/reversal` 对比完整集与删除集，输出每位候选的位移与逐列贡献变化 |
| 决策版本 | PostgreSQL 保存原始指标、单位、观测值与版本快照（JSONB 选项 + 快照表），历史可复算 |

## 排名逆转为什么会发生（也是教学点）

- min-max 规范化的端点来自**当前候选集合**；TOPSIS 的正/负理想解同样如此。
- 因此增删一个候选会改变所有人的分数参照系——这是方法机制，不是谁"客观变好了"。
- 一个非平凡性质：固定指标与正权重时，min-max **WSM 对既有候选的相对序不随增删逆转**
  （测试 `test_rank_reversal_is_method_specific` 同时验证了同组数据上 TOPSIS 逆转而 WSM 不逆转）。
  委员会若观察到 WSM 名次变动，原因通常是：权重口径、指标剔除、裁剪、插补策略发生了变化。

## 技术栈

- **backend/**：FastAPI + NumPy + SciPy（熵权、MAD、相关系数）+ psycopg3
- **db/schema.sql**：PostgreSQL 表结构（criteria / candidates / measurements / decision_versions / version_snapshots）
- **frontend/**：Angular 20 standalone（无隐藏第三方图表库，矩阵热力图手写，全部数字可逐格核对）
- 无 `DATABASE_URL` 时后端显式降级为同构内存仓储（`/health` 标注"未持久化"），便于本地/CI 运行

## 本地运行

```bash
# 后端（内存仓储，零外部依赖）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 前端
cd frontend
npm install
npm start                 # http://localhost:4200，代理 /analyze 等到 :8000

# 测试
cd backend && python3 -m pytest -q
```

## 用真实 PostgreSQL 运行

```bash
docker compose up --build
# 后端 DATABASE_URL=postgresql://mcda:mcda@db:5432/mcda
# 前端 http://localhost:4200
```

或仅启数据库后：`DATABASE_URL=postgresql://... uvicorn app.main:app`（首次自动建表）。

## API 速览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 后端持久化形态（postgresql / memory） |
| GET/POST | `/criteria` `/candidates` `/values` | 原始指标、单位、方向、观测值 CRUD |
| POST | `/analyze` | 即席分析，body 为选项（缺失策略/裁剪/权重口径/移出集合） |
| GET | `/versions` `/versions/{id}/report` | 决策版本与其复算报告 |
| POST | `/reversal` | 完整候选集 vs 删除集的排名逆转对比 |

`/analyze` 报告包含 5 个逐步矩阵：原始数据 → 插补/裁剪 → 按类型规范化[0,1] → 权重与加权矩阵 → TOPSIS 距离。

## 内置演示数据（backend/app/seed.py）

- `sso_support`：四方案全为 1 的常量列（演示不自动满分）
- `B / sec_score`：缺失值（演示插补不送分）
- `D / perf_qps = 20000`：MAD 修正 z≈8.8 的极端异常值
- `tco_year` 与 `license_cost`：Spearman=1 的疑似重复指标
- 人工权重合计 = 110（演示归一与核对）
- 5 个预置决策版本：基线 / 剔除重复指标 / 裁剪异常 / 纯熵权 / 人工+熵权 50-50
