# 执行包版本

- Package: `AI客服-UAT-Copilot内网执行包`
- Version: `1.1.0`
- Date: `2026-07-11`
- Design source: `AI客服-UAT测试方案-增强版.md`
- Primary generator: `Claude Opus 4.8`
- Independent reviewer / blind generator: `GPT-5.5`
- Scoring authority: `AI客服-UAT-执行模板.xlsx` 中的确定性公式

版本规则：

- 固定指令、字段或判分口径变化：升级主版本或次版本。
- 仅修正文案、不改变数据契约：升级修订版本。
- 公司内执行时另行记录知识库版本、Prompt 版本、测试集版本和执行批次。

变更记录：

- `1.1.0`（2026-07-11）：判分公式精确化（EXACT/FIND，区分大小写、无通配符，NBSP 标准化）；
  新增 BLOCKED/CASE_NOT_FOUND 守卫与 FALLBACK_TEXT_MISMATCH 分类；一致性检查限定同一执行批次；
  P0 公式补齐审批硬门（`freeze_gate`）与安全类不稳定两条规则；新增 `03b_Review_Results` 工作表；
  case_id 纳入 generator_run_id 防冲突；各生成类 Prompt 升级至 v1.1；文档口径同步。
- `1.0.0`（2026-07-11）：首版。
