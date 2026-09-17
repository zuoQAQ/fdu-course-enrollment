# 复旦大学研究生抢课脚本

多线程并发抢课，支持多门课程备选、csrfToken 预获取、自动重试。

## 代码小白？
 
如果你不懂代码，找一个 AI Agent（如 Claude Code、Cursor、MiMo 等，不是网页聊天窗口），把本仓库路径发给它，说：
 
 > 帮我配置并运行这个抢课脚本，我要抢的课是 xxx
 
AI Agent 能直接帮你改文件、跑脚本，你只需要提供 Cookie 就行。
 
## 使用方法

1. 修改 `course.py` 中的课程配置
2. 运行脚本：
   ```bash
   python course.py
   ```
3. 按提示粘贴 Cookie（或设置环境变量 `QIANGKE_COOKIE`）

## Cookie 获取步骤

1. 浏览器登录 http://yjsxk.fudan.edu.cn
2. F12 → Application → Cookies → yjsxk.fudan.edu.cn
3. 复制 `_WEU`、`GS_SESSIONID`、`JSESSIONID`、`route` 四个值
4. 拼成 `_WEU=xxx; GS_SESSIONID=xxx; JSESSIONID=xxx; route=xxx`

## 配置说明

```python
# 课程配置：[分类名, 课程ID1, 课程ID2, ...]，同组内按优先级排序
classification_and_course_ids = [
    ["政治理论课", "2026202701GEIP40015.07"],
    ["公共选修课", "2026202701GEEC10294.01", "2026202701GEEC10296.01"]
]

# 抢课时间
START_HOUR = 12
START_MINUTE = 59
START_SECOND = 55

# 结束时间
END_HOUR = 13
END_MINUTE = 1
END_SECOND = 57
```

## 后台运行

```powershell
Start-Process -FilePath "python" -ArgumentList "-u course.py" -RedirectStandardOutput "run.log" -RedirectStandardError "run_err.log" -NoNewWindow -PassThru | Select-Object Id
```

## 特性

- 多线程并发，每组课程独立线程
- 提前 2 分钟预获取 csrfToken，每秒刷新
- 遇到"缓存中"自动重试，不退出
- 遇到"页面过期"立刻刷新 token
- 遇到"已满"/"冲突"/"不在可选范围"自动跳过下一门
- 到结束时间自动停止
