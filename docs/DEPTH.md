# 深度登记 散货滞期核算台

- 规模：中型
- 核心规则：通知裁决后按合同优先级切片并集，复算滞期并逐档核账。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 公证装卸事件采信 | 检查原件与隔离原因 | POST /api/intake | `app/modules/intake/service.py` `app/modules/intake/reader.py` | `tests/test_intake.py` |
| M2 准备通知裁决 | 复核通知与合同选版 | POST /api/notice | `app/modules/notice/service.py` | `tests/test_notice.py` |
| M3 例外区间切片 | 查看重叠停工依据 | POST /api/exceptions | `app/modules/exceptions/service.py` | `tests/test_exceptions.py` |
| M4 免计边界复算 | 复核分段占额 | POST /api/clock | `app/modules/clock/service.py` | `tests/test_clock.py` |
| M5 滞期费与账单对照 | 核对到账分钟和金额 | POST /api/ledger | `app/modules/ledger/service.py` | `tests/test_ledger.py` |
| M6 批次留档复跑 | 固化计算并重跑 | POST /api/runs | `app/modules/runs/storage.py` | `tests/test_runs.py` |
| M7 证据包签发 | 查验资格、下载证据 | GET /api/evidence/<run_id> | `app/modules/evidence/service.py` | `tests/test_evidence.py` |

## 陷阱登记

| TRAP | 现象 | 朴素错误 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | 航次首列 BOM | 找不到事件键 | 去首 BOM | `app/modules/intake/reader.py` | `tests/test_intake.py::test_bom_and_repeated_header` |
| TRAP-04 | 分段表头 | 误计事件 | 单独登记分段 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_bom_and_repeated_header` |
| TRAP-05 | E10 多一列 | 列错位 | 隔离原行 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_column_count_isolated` |
| TRAP-07 | E09 空值哨兵 | 计入时钟 | 记录哨兵原值 | `app/modules/intake/values.py` | `tests/test_intake.py::test_sentinel_kept_as_evidence` |
| TRAP-11 | E03 两种偏移 | 双重通知 | UTC 时间去重 | `app/modules/intake/values.py` | `tests/test_intake.py::test_offsets_dedupe_by_instant` |
| TRAP-14 | E11 同键异时 | 后写覆盖 | 全组隔离 | `app/modules/intake/service.py` | `tests/test_intake.py::test_conflicting_key_is_withdrawn` |
| TRAP-19 | S01/S02 重叠 | 双免或随行序 | 明确优先级并列依据 | `app/modules/exceptions/precedence.py` | `tests/test_exceptions.py::test_precedence_permutation` |
| TRAP-23 | S04/S05 贴窗 | 交界重算 | 半开并裁边 | `app/modules/exceptions/service.py` | `tests/test_exceptions.py::test_touching_window_is_outside` |
| TRAP-25 | R1/R2 同时有效 | 随顺序定档 | 以最高优先级裁决 | `app/modules/notice/versions.py` | `tests/test_notice.py::test_notice_picks_active_priority` |
| TRAP-31 | 缺证未补齐即报速遣 | 把未核实时段当确定金额 | 缺证能改变方向时报方向待定、可确认金额 `null`，只给区间 | `app/modules/ledger/service.py` | `tests/test_ledger.py::test_direction_undetermined_when_gap_can_flip` |
| TRAP-33 | 速遣按全额费率 | 误用滞期第一档费率 | 费率取第一档滞期费之半 | `app/modules/ledger/rates.py` | `tests/test_ledger.py::test_despatch_uses_half_of_first_tier` |
| TRAP-35 | 船方已按滞期开票却算成速遣 | 把冲销当零 | 反向结果全额冲销，单列负数而非 0 | `app/modules/ledger/service.py` | `tests/test_ledger.py::test_despatch_reverses_ship_invoice_not_zero` |
| TRAP-37 | 晚到停工记录改变方向 | 覆盖旧版或重复出账 | 运行 ID 含源文本哈希，旧版仍可查，同轮重跑不重复 | `app/modules/runs/storage.py` | `tests/test_runs.py::test_late_stop_flips_direction_and_old_version_survives` |

## 对账规则

- 每源正文行数 = 采信 + 隔离 + 空行 + 重复表头。
- 150 min = 75 min 合同计时 + 60 min 免计 + 15 min 缺证。75−35=40 min 超额。
- 应计 20×3 + 20×5 = 160.00 USD，船方 60+95=155.00 USD，相差 5.00 USD。
- 方向按核实分钟判定：即使不计缺证也已超额 → 滞期；即使计满缺证仍未超额 → 速遣/平衡；否则 → 方向待定。
- 未核实（GAP）分钟可计可免，凡与之挂钩的金额只给区间，不进入可确认金额；方向待定时可确认金额为 `null`。
- 速遣费率 = 第一档滞期费 ÷ 2，按核实后的节省分钟计付。
- 船方按滞期开票后若本轮结果为速遣/平衡，按全额冲销（负数）列示，不按零处理；方向待定时冲销暂挂。

按航次整窗计算，输入须提供确定偏移，未实现 IANA 时区名称、装卸多舱并行额度、非美元计价或电子签章。
