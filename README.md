# 散货滞期核算台

港口商务专员用船方通知、港方事件簿、合同和账单复算滞期。在 `/` 查看船港分档差额，经左侧导航复核 7 个环节，从留档页执行重跑并在签发页下载证据包。

## 启动与验收

`docker compose up --build` 后访问 `http://localhost:18460/`。本地可执行 `pip install -r requirements.txt`、`python -m flask --app app.main run --port=18460` 和 `pytest -q`。`HARBOR_DB` 控制数据库文件，Compose 用命名卷。重置演示数据用 `docker compose down --volumes`。

前五个独立预览入口接收 `{"sample":"dirty"}`、`{"sample":"clean"}` 或 `{"sources":{"events":"CSV","stops":"CSV","terms":"CSV","invoice":"CSV"}}`。留档用 `POST /api/runs`，查询用 `GET /api/runs/<run_id>`，证据审读和下载见模块表。源码位于 `app/`，航次材料位于 `sample_data/`。

跨年争议样例已核实 40 分钟超额，应计 160.00 USD（滞期），船方列账 155.00 USD，另有 15 分钟缺证仍待补。复核页给出本次方向、可确认金额与待补区间：缺证未补齐时不把未核实分钟当作确定金额，方向可能翻转时标为“方向待定”、可确认金额为 `待证`。

若核实后船方提前完成装卸，则按核实后的节省分钟计付速遣费，费率取第一档滞期费之半。船方已按滞期开票而本轮结果为速遣或平衡时，页面明示全额冲销（负数），不按零处理；方向未定时冲销暂挂。晚到停工记录可改变方向：每次运行以源文本哈希区分，旧版仍可查，同一轮重跑不重复出账。应用输出供核对与复核，签发状态取决于完整性、方向与差异。

- [模块与陷阱](docs/DEPTH.md)
- [数据定义](docs/DATA-DICTIONARY.md)
