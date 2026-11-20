# 深度登记 · 剧场票房分账台

规模为中型。巡演票务财务以一套原分账为基准，每次核销或停演退款报表到齐后核对收款与场馆应收。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 票源导入 | 发布本批报表，复核票款和源行 | `POST /api/runs`、`GET /api/intake/{run_id}` | `app/modules/m1_intake/reader.py` `app/modules/m1_intake/service.py` | `tests/test_intake.py` |
| M2 套票权益 | 查原场次资格、票场权重及冲突 | `GET /api/rights/{run_id}` | `app/modules/m2_rights/shows.py` `app/modules/m2_rights/service.py` | `tests/test_rights.py` |
| M3 入场核销 | 查最早通过的核销与拦截依据 | `GET /api/scans/{run_id}` | `app/modules/m3_scans/service.py` | `tests/test_scans.py` |
| M4 权重分账 | 按票复核分角尾差和未分配款 | `GET /api/allocation/{run_id}` | `app/modules/m4_allocation/rules.py` `app/modules/m4_allocation/service.py` | `tests/test_allocation.py` |
| M5 退款冲正 | 逐笔核对停演冲正、限额与超领原因 | `GET /api/refunds/{run_id}` | `app/modules/m5_refunds/rules.py` `app/modules/m5_refunds/service.py` | `tests/test_refunds.py` |
| M6 场馆勾稽 | 对照双账并按票、场馆、源文件复核 | `GET /api/reconcile/{run_id}` | `app/modules/m6_reconcile/ledger.py` `app/modules/m6_reconcile/service.py` | `tests/test_reconcile.py` |
| M7 结算凭证 | 查看原因码分布与源清单，下载可重算凭证 | `GET /api/evidence/{run_id}`、`GET /api/evidence/{run_id}/export` | `app/modules/m7_evidence/bundle.py` `app/modules/m7_evidence/csv_out.py` | `tests/test_evidence.py` |

## 陷阱登记

| TRAP | 样例现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | shows.csv 使用 GB18030 | 剧名乱码 | 失败回退及记录编码 | `app/modules/m1_intake/reader.py` | `tests/test_rights.py::test_gb18030_show_titles_decode_without_corruption` |
| TRAP-02 | tickets.csv 带 BOM | 首列票码读取失败 | UTF-8 BOM 解码 | `app/modules/m1_intake/reader.py` | `tests/test_intake.py::test_bom_and_zero_prefixed_ticket_are_preserved` |
| TRAP-03 | tickets.csv 票据备注带换行 | 一张票拆成两张 | 保留两行范围但只计一个逻辑行 | `app/modules/m1_intake/reader.py` | `tests/test_intake.py::test_quoted_multiline_keeps_physical_line_range` |
| TRAP-04 | tickets.csv 分段重复表头 | 重复表头被当作坏票 | 表头和平铺记录独立计数 | `app/modules/m1_intake/reader.py` | `tests/test_intake.py::test_repeated_header_and_empty_line_are_counted` |
| TRAP-05 | tickets.csv 缺陷行尾额外逗号 | 多列静默丢弃 | 保留原值并隔离 | `app/modules/m1_intake/reader.py` | `tests/test_intake.py::test_extra_column_enters_quarantine` |
| TRAP-06 | tickets.csv 有千位分组及全角金额 | 导入失败或金额错 | 格式检查与金额归一 | `app/contracts.py` | `tests/test_intake.py::test_mixed_money_formats_are_exact` |
| TRAP-07 | tickets.csv 缺款以 N/A 表示 | 缺款成为零元票 | 必填空值隔离 | `app/contracts.py` | `tests/test_intake.py::test_missing_amount_and_conflicting_tickets_are_not_funded` |
| TRAP-08 | tickets.csv 票码 00107 | 前导零丢失 | 字符串票码 | `app/contracts.py` | `tests/test_intake.py::test_bom_and_zero_prefixed_ticket_are_preserved` |
| TRAP-10 | tickets.csv 混合小数与大额 | 金额合计丢失最小单位 | Decimal 转整数分 | `app/contracts.py` | `tests/test_intake.py::test_mixed_money_formats_are_exact` |
| TRAP-11 | scans.csv 同时刻 Z 和 +08:00 | 两个时刻参与排序 | 归一 UTC 后按编号裁决 | `app/contracts.py` | `tests/test_scans.py::test_timestamp_offsets_resolve_same_logical_scan` |
| TRAP-13 | scans.csv 较早有效记录在后 | 首条到达记录占用票码 | 按业务时间重放 | `app/modules/m3_scans/service.py` | `tests/test_scans.py::test_late_arriving_earlier_scan_wins_replay` |
| TRAP-14 | tickets.csv 同票两份不同收款 | 后写覆盖 | 冲突组全隔离 | `app/deduplicate.py` | `tests/test_intake.py::test_missing_amount_and_conflicting_tickets_are_not_funded` |
| TRAP-15 | tickets.csv 元、分混用 | 收款多计百倍 | 单位转换后累计 | `app/contracts.py` | `tests/test_intake.py::test_mixed_money_formats_are_exact` |
| TRAP-23 | scans.csv 含起点和关闭时刻 | 边界二次入账 | 半开核销窗 | `app/modules/m3_scans/service.py` | `tests/test_scans.py::test_window_start_is_inclusive_and_close_exclusive` |
| TRAP-24 | tickets.csv 的 00107 拆给相同权重 | 三场取整后少分或多分 | 最大余数与场次键裁决 | `app/modules/m4_allocation/rules.py` | `tests/test_allocation.py::test_equal_remainders_use_stable_show_key_and_conserve` |
| TRAP-26 | 以 refunds.csv 已发布样例为基准提交仅表头快照 | 原退款被旧表清除 | 校验已过账冲正都保留 | `app/modules/m5_refunds/service.py` | `tests/test_refunds.py::test_previous_approval_cannot_be_erased_by_stale_submission` |

## 对账规则

源逻辑行按采信、隔离、空行、表头解释完毕。实收分等于原分账与未分配票款之和，扣除停演退款后等于场馆应收与未结余额之和。额外覆盖逐票守恒、限额、跨场馆汇总和故障注入。
