# B站弹幕与评论统计工具

从 Bilibili 视频、多 P 视频、合集和番剧中获取弹幕及评论，使用 SQLite 保存明细和抓取进度，并导出分集报表与全局 Excel 汇总。

## 功能

- 自动识别 BV 号、视频 URL、合集 URL、番剧 `ep`/`ss` 输入
- 使用 protobuf 结构化解析弹幕，保留英文、表情和重复文本
- 按弹幕 ID、评论 `rpid` 去重，避免断点续传产生重复数据
- 顺序获取主评论游标页，并获取每条主评论下可访问的子评论页
- 并发获取弹幕分段和不同主评论的子评论
- 遇到 `412`、`429` 或服务端错误时自动降低并发和请求速率
- 使用 SQLite 保存弹幕、评论及分页进度，支持中断后自动续传
- 为每个分集生成明细和统计表，同时生成全局汇总表

程序只能获取当前账号通过 Bilibili 接口有权访问的数据，不会绕过登录、会员、地区或风控限制。

## 环境与安装

- Python 3.8+
- `requests`、`pandas`、`openpyxl`、`protobuf`、`tqdm`

```bash
python3 -m pip install -r requirements.txt
```

如需根据 `dm.proto` 重新生成 protobuf 绑定：

```bash
python3 -m pip install -r requirements-dev.txt
```

## 快速开始

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC \
  --cookie-file cookie.txt \
  --concurrency 6
```

程序默认将数据库保存到 `Results/<视频名>/bilibili_stats.sqlite3`，与全局 Excel 报表位于同一作品目录。运行中按 `Ctrl+C` 后，再次执行相同命令即可从已提交的游标继续。

## 支持的输入

### BV 号

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt
```

### 普通或多 P 视频 URL

```bash
python3 bilibili_stats.py \
  'https://www.bilibili.com/video/BV1Q9Vh6CEcC?p=2' \
  --cookie-file cookie.txt
```

程序会解析该视频的全部分 P，不只处理 URL 中指定的 `p`。

### 合集 URL

```bash
python3 bilibili_stats.py \
  'https://space.bilibili.com/用户MID/lists/合集ID?type=season' \
  --cookie-file cookie.txt
```

### 番剧单集或季度

```bash
python3 bilibili_stats.py ep123456 --cookie-file cookie.txt
python3 bilibili_stats.py ss654321 --cookie-file cookie.txt
python3 bilibili_stats.py \
  'https://www.bilibili.com/bangumi/play/ep123456' \
  --cookie-file cookie.txt
```

`ep` 输入会解析其所属季度，并处理接口返回的季度分集。

## 命令行参数

```text
python3 bilibili_stats.py INPUT
  [--cookie COOKIE | --cookie-file FILE]
  [--database PATH]
  [--output-dir PATH]
  [--restart | --export-only]
  [--max-attempts N]
  [--request-delay SECONDS]
  [--concurrency N]
  [--no-progress]
```

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `INPUT` | 必填 | BV 号、视频 URL、合集 URL、`ep` 或 `ss` 输入 |
| `--cookie COOKIE` | 无 | 直接传入 Cookie，不推荐写入 Shell 历史 |
| `--cookie-file FILE` | 无 | 从 UTF-8 文本文件读取 Cookie，推荐方式 |
| `--database PATH` | 自动 | 手动指定 SQLite 路径；指定后关闭自动定位和迁移 |
| `--output-dir PATH` | `Results` | Excel 输出根目录 |
| `--restart` | 关闭 | 删除当前解析任务的数据后重新抓取 |
| `--export-only` | 关闭 | 不访问网络，仅从现有数据库重新导出 |
| `--max-attempts N` | `5` | 单次请求的最大尝试次数 |
| `--request-delay SECONDS` | `0.05` | 共享限流器的初始最小请求间隔 |
| `--concurrency N` | `6` | 弹幕分段和子评论任务的初始并发数 |
| `--no-progress` | 关闭 | 关闭动态进度条；重定向输出时仍打印阶段开始和完成日志 |

```bash
python3 bilibili_stats.py --help
```

## Cookie 配置

支持三种方式，优先级为 `--cookie`、`--cookie-file`、环境变量 `BILIBILI_COOKIE`。

推荐方式：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt
```

环境变量方式：

```bash
export BILIBILI_COOKIE='你的完整 Cookie'
python3 bilibili_stats.py BV1Q9Vh6CEcC
```

Cookie 是登录凭证，不要提交到 Git、复制到日志或发送给他人。`cookie.txt` 已被 `.gitignore` 排除，程序不会主动打印 Cookie 内容。

## 运行进度

在交互式终端运行时，程序会显示以下阶段进度：

- 弹幕：按接口返回的分段总数推进；断点续传时从已完成分段开始显示。
- 主评论：由于总页数未知，显示已完成页数和当前累计评论数。
- 子评论：按待补全的主评论根数推进。
- Excel 导出：按需要生成的工作簿总数推进。

输出被重定向到文件、日志系统或非交互终端时，不绘制动态进度条，只打印阶段开始、完成数量和耗时。使用 `--no-progress` 可手动关闭动态进度条：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt --no-progress
```

## 并发与风控

- 弹幕分段使用线程池并发下载。
- 主评论依赖上一页游标，因此保持顺序获取。
- 不同主评论的子评论可以并发；同一主评论内部仍按页顺序获取。
- 收到 HTTP/API `412`、`429` 或重复服务端错误时，并发数减半并增加请求间隔。
- 连续成功达到阈值后，并发数和速度逐步恢复。

网络稳定时可尝试：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC \
  --cookie-file cookie.txt \
  --concurrency 8 \
  --request-delay 0.05
```

更高并发不一定更快；触发风控后总耗时通常反而增加。

## 断点续传

每个已完成的弹幕分段、主评论游标和子评论页都会写入作品目录内的 `bilibili_stats.sqlite3`。重复执行同一输入时：

- 弹幕按平台弹幕 ID 去重。
- 评论按 `rpid` 去重。
- 弹幕从首个未连续完成的分段继续。
- 主评论从已保存的游标继续。
- 未完成子评论从各自页码继续。

指定数据库和输出目录：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC \
  --cookie-file cookie.txt \
  --database data/genshin.sqlite3 \
  --output-dir reports
```

清除当前作品的数据并重新抓取：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt --restart
```

仅从已有数据库重新导出：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --export-only
```

默认情况下，`--export-only` 会扫描 `Results/*/bilibili_stats.sqlite3` 并按作品键定位数据库。显式使用 `--database` 时则直接使用该文件。番剧离线导出应使用 `ss` 输入，因为仅凭 `ep` 无法在无网络情况下确定季度数据库键。

## 旧数据库自动迁移

如果存在旧版总数据库 `Results/bilibili_stats.sqlite3`，且本次没有显式传入 `--database`，程序会在启动时：

1. 读取总库中的全部作品。
2. 将每个作品的数据复制到 `Results/<视频名>/bilibili_stats.sqlite3`。
3. 核对作品、分集、弹幕、评论、游标和失败记录的行数。
4. 仅在所有作品验证成功后删除旧总库及其 `-wal`、`-shm` 文件。

迁移可重复执行，若中途失败会保留旧总数据库。显式指定 `--database PATH` 时不执行自动迁移。

## 输出结构

```text
输出根目录/
└── 作品标题/
    ├── bilibili_stats.sqlite3
    ├── 01-分集或分P标题/
    │   ├── 弹幕明细.xlsx
    │   ├── 弹幕统计.xlsx
    │   ├── 弹幕用户排行.xlsx
    │   ├── 完整评论.xlsx
    │   └── 评论用户统计.xlsx
    ├── 02-分集或分P标题/
    │   └── ...
    ├── 全局弹幕统计.xlsx
    ├── 全局弹幕用户排行.xlsx
    ├── 全局评论统计.xlsx
    ├── 评论用户排行.xlsx
    └── 分集概览.xlsx
```

- `弹幕明细.xlsx`：弹幕 ID、内容、时间、视频进度、模式、字号、颜色、发送者哈希等。
- `弹幕统计.xlsx`：按文本统计出现次数；相同文本的不同弹幕会正确累计。
- `弹幕用户排行.xlsx`：按 `sender_hash` 统计发送次数并降序排列，增加 `发送者标识` 列以保持和评论排行类似；由于弹幕接口只提供哈希值，这一列当前填入同一发送者标识，所有弹幕内容在同一单元格内按行列出。
- `完整评论.xlsx`：评论 `rpid`、用户、内容、根/父评论关系、时间和点赞数。
- `评论用户统计.xlsx`：按用户名统计评论次数。
- `全局弹幕统计.xlsx`：所有分集或分 P 的弹幕文本汇总。
- `全局弹幕用户排行.xlsx`：作品范围内按发送者哈希汇总弹幕次数和内容。
- `全局评论统计.xlsx`：当前作品已获取评论的用户汇总。
- `评论用户排行.xlsx`：按用户 MID 聚合，显示最新评论对应的用户名、评论次数及逐行评论内容。
- `分集概览.xlsx`：分集顺序、标题、BVID、CID 和弹幕条数。

评论属于视频 `aid`，不是分 P 的 `cid`。当前导出器会在各分集目录写入该作品数据库中的评论集，因此多 P 视频的分集评论表可能相同；抓取阶段不会对同一个 `aid` 重复获取评论。

## 代码结构

```text
Bili/
├── bilibili_stats.py          # CLI、任务编排和 Excel 导出入口
├── bili_stats/
│   ├── input.py               # 输入识别与规范化
│   ├── models.py              # 领域数据模型
│   ├── resolver.py            # 视频、合集和番剧解析
│   ├── client.py              # HTTP、WBI、重试和自适应限流
│   ├── checkpoint.py          # SQLite、去重和断点状态
│   ├── danmaku.py             # protobuf 弹幕解析与并发获取
│   ├── comments.py            # 主评论和完整子评论分页
│   ├── exporter.py            # 用户排行聚合和 Excel 导出
│   ├── database_paths.py      # 作品数据库路径和离线发现
│   ├── migration.py           # 旧总数据库分作品迁移
│   ├── progress.py            # TTY 进度条和非交互阶段日志
│   └── proto/
│       ├── dm.proto           # protobuf 结构定义
│       └── dm_pb2.py          # Python protobuf 绑定
├── tests/                     # 离线单元测试
├── requirements.txt           # 运行依赖
└── requirements-dev.txt       # 开发依赖
```

### 核心组件

- `Resolver`：把不同输入统一转换为作品及有序分集列表。
- `BilibiliClient`：管理请求头、Cookie、WBI 签名、重试和 API 错误。
- `AdaptiveLimiter`：控制共享并发数和请求间隔。
- `DanmakuCollector`：读取分段总数，并发下载及结构化解析弹幕。
- `CommentCollector`：顺序获取主评论，并发获取不同根评论的子回复。
- `Repository`：事务写入 SQLite，维护唯一约束和续传游标。
- `export()`：位于 `bili_stats/exporter.py`，生成分集、全局及用户排行 Excel。

## 测试

后续真实接口测试统一使用 `BV1Q9Vh6CEcC`，并使用默认的 `Results/` 数据库和输出路径：

```bash
python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt
```


```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q bili_stats bilibili_stats.py tests
```

离线测试覆盖输入识别、数据模型、SQLite 去重和任务重启、WBI 签名、自适应并发、用户排行分组排序和 Excel 长文本截断。Bilibili 接口可能变化，升级后建议先使用临时数据库做短时真实验证。

## 常见问题

### 什么是“写入挂起”

“写入挂起”表示进程正在等待文件系统或 SQLite 完成写入，常见于共享磁盘空间紧张、元数据服务繁忙或其他进程长时间占用数据库写锁。先确认磁盘空间，避免同时运行多个写入同一 `bilibili_stats.sqlite3` 的实例；等待后仍无进展时可按 `Ctrl+C` 安全中断，再执行相同命令从已提交进度续传。不要直接删除 SQLite 的 `-wal` 或 `-shm` 文件。

### 抓取速度仍然较慢

主评论使用游标分页，无法安全并发请求尚未得到的后续游标。速度提升主要来自弹幕分段和不同根评论子回复的并发。可适当提高 `--concurrency`，但触发风控后程序会自动降速。

### 中断后为什么仍会显示全部分集名称

程序会重新解析作品元数据并调度分集，但数据库会从未完成位置继续，稳定 ID 和唯一约束可避免重复写入。

### 为什么返回退出码 2

至少一个弹幕或评论任务失败，但成功获取的数据仍保存在 SQLite 中并会尝试导出。再次运行相同命令可重试未完成部分。

### 如何完全重新开始

使用 `--restart`。它只删除当前解析作品的数据，不删除同一数据库中的其他作品。

### 为什么部分评论无法获取

可能由账号权限、评论审核、已删除内容、地区限制、Cookie 失效或平台风控导致。程序只保存接口实际返回且当前账号有权访问的数据。

## 安全与限制

- 不要公开 Cookie 或包含用户数据的 SQLite/Excel 文件。
- 合理设置并发，避免对平台造成不必要负载。
- Bilibili 接口可能调整，接口变化时需要同步更新解析逻辑。
- 本工具仅供学习和个人数据分析，请遵守 Bilibili 服务条款及适用法律。
