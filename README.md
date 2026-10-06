# 技术选型多准则决策工作台（MCDA Workbench）

一个**可审计**的方案比选系统：Angular 展示指标、权重与逐步转换；FastAPI 用
NumPy/SciPy 实现加权和模型（WSM）与 TOPSIS；PostgreSQL 保存原始指标、单位、
权重来源与不可变的决策版快照。

它的设计立场是：**一个总分会掩盖三件事——指标方向有没有写反、权重代表谁的
偏好、排序对候选集变化有多脆弱。** 所以系统把这三件事全部摊开，而不是输出
一个“客观唯一最佳”。

## 快速启动

### 方式一：Docker Compose（PostgreSQL + API + 前端）

```bash
docker compose up --build
# 前端 http://localhost:4200 ， API 文档 http://localhost:8000/docs
```

### 方式二：本地开发（无 Docker 时自动回退 SQLite）

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000      # 首次启动自动建表+写入演示数据

# 前端
cd frontend
npm install
npm start                                      # http://localhost:4200 （已配置 /api 代理）
```

使用真正的 PostgreSQL：

```bash
export DATABASE_URL="postgresql+psycopg2://mcda:mcda@localhost:5432/mcda"
psql "$DATABASE_URL" -f backend/schema.sql
uvicorn app.main:app --port 8000
```

## 内置两个演示场景

1. **云平台供应商选型（vendor）**——数据里故意埋了四类问题：
   - 常量列：四家可用性都是 99.9%（不除零、不送满分，记中性 0.5，推得权重为 0）；
   - 缺失值：磐石云未提交压测（红标“缺失”，按所选策略逐格记录，绝不按满分）；
   - 重复指标：P95 延迟与 SLA 响应时长排名完全一致（同时计入=该维度权重翻倍）；
   - 极端异常值：磐石报价 240 万（稳健 z≈16.5，会独占 min/max 规范化端点）。
2. **排名逆转最小示例（reversal）**——四方案两指标等权：
   全集 TOPSIS 为 **B › C › D › A**；删掉 B 后幸存者变成 **C › A › D**——
   A、D 因一个离场方案而互换。等价地，向 {A,C,D} 新增 B 也会让 A、D 互换。
   切到“固定锚点”视角可看到 WSM 分数不随候选集合改变。

## 计算口径（每一步在 UI 中都可见）

| 指标方向 | 规范化 |
|---|---|
| 收益型 benefit（越大越好） | `(x − min) / (max − min)` |
| 成本型 cost（越小越好） | `(max − x) / (max − min)`，与收益型互为镜像 |
| 目标区间型 target | 区间 `[low, high]` 内 = 1；区间外 `1 − 到区间距离 / 最大可能距离` |

安全规则：

- **常量列**（max=min）：不做除法，观测值记中性 0.5，熵权/CRITIC 中权重为 0，附警告；
- **缺失值**：三种显式策略——中性 0.5 / 该行已知项均值 / 该格不计分且行内权重重归一；
  每格的处理都列入步骤日志，任何策略下缺失都不会变成满分；
- **固定锚点**：`fixed_min/fixed_max` 用外部参照区间作分母，增删候选不会重标定其他人；
- **权重校验**：人工权重必须覆盖全部指标、非负且和恰好为 1，否则后端 422 拒绝计算。

两种打分模型（返回所有中间矩阵，可逐格核对）：

- **WSM**：`score = Σ wⱼ·nᵢⱼ`，UI 展示每个单元格对总分的贡献；
- **TOPSIS**：向量归一 → 加权 → 理想解/反理想解 → `C = D⁻/(D⁺+D⁻)`，
  UI 展示两个距离与理想解向量；退化情形（距离和为 0、范数为 0）记中性而非除零。

## 权重：人工与数据推得严格分开

| 来源 | 含义 | 持久化要求 |
|---|---|---|
| 人工权重（manual） | 委员会的价值判断 | **必须填写来源/依据**（会议纪要等），和为 1 |
| 临时权重（adhoc） | 页面 what-if，不保存 | 不落库，结果中标记“未保存” |
| 熵权 entropy | 列信息量 1−e，常量列→0 | 可计算可保存，但标注“只反映区分度” |
| CRITIC | 对比强度 σ × 冲突性（Spearman，SciPy） | 同上 |

每次分析的响应与冻结快照中都带 `weight_provenance`（来源、方法、依据）与
`weight_sum`，前端单独成块展示。

## 排名逆转审计

后端对“逐个删除每个候选”重跑完整流水线，并分别给出：

- **动态锚点**（默认）：min/max 端点与 TOPSIS 理想解随幸存者变化，逆转逐条列出
  （删除谁、哪个模型、删除前/后完整顺序、首个互换对）；
- **固定锚点**：以全集极值为外部锚点，WSM 对增删候选免疫（测试固化此性质）。

“删除 X 后逆转”反着读就是“新增 X 后逆转”。

## 决策版（decision of record）

冻结操作把原始矩阵、规范化矩阵、权重来源、排名、分数与当时未解决的数据问题
原样写入 `decision_versions.snapshot`（JSONB，不可变）。算法排序可以被采纳，
但必须由人填写**为什么相信/不相信它**的备注——系统不把算法输出包装成最终结论。

## API 摘要

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/scenarios` | 场景与决策列表 |
| GET | `/api/decisions/{id}` | 原始矩阵（null=缺失）、单位、权重集、版本列表 |
| GET | `/api/decisions/{id}/derived-weights` | 熵权/CRITIC 预览（不落库） |
| POST | `/api/decisions/{id}/weight-sets` | 保存权重（人工必须带来源） |
| POST | `/api/decisions/{id}/analyze` | 完整分析：规范化、双模型、审计、逆转 |
| POST | `/api/decisions/{id}/versions` | 冻结决策版快照 |
| GET | `/api/versions/{id}` | 读取历史快照 |

## 测试

```bash
cd backend && python3 -m pytest -q
# 17 passed：方向镜像、区间满分/衰减、常量列、缺失值、权重校验、
# 重复指标、异常值、TOPSIS 逆转、固定锚点免疫、HTTP 全链路与快照
```

## 目录

```
backend/app/
  core/normalization.py   # 收益/成本/区间 + 常量列/缺失/锚点规则
  core/weights.py         # 人工校验、熵权、CRITIC（SciPy）
  core/scoring.py         # WSM、TOPSIS（全部中间步骤）
  core/analysis.py        # 重复指标、MAD/IQR 异常、排名逆转审计
  db/models.py            # SQLAlchemy（PostgreSQL JSONB，SQLite 回退）
  seed.py                 # 两个刻意构造的教学场景
frontend/src/app/         # 六个面板组件：原始矩阵/体检/规范化/权重/打分/逆转/版本
```
