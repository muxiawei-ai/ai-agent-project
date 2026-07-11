# AI 客服 UAT 固定指令

本目录用于金融 AI 客服 UAT。任何 Copilot 会话、模型和代理都必须遵守以下规则。

1. 不得修改、缩写、润色或补写知识库答案原文。
2. 模型只生成候选，不得填写人工审批字段，不得批准新增或修改答案。
3. 没有合适知识库答案时，不得强行选择最相近问答；必须使用规定的 `coverage_decision`。
4. `business_decision`、`approved_route`、`approved_qa_id`、`review_note` 由人工填写。
5. `business_approval` 初始值为 `PENDING`；合规敏感项的 `compliance_approval` 初始值为 `PENDING`，其他项为 `NOT_REQUIRED`。
6. 工作集和盲测集不得混淆；盲测不得复制或轻微改写工作集。
7. 所有结构化输出必须严格遵守字段名和枚举；不确定项必须填写 `needs_review_reason`。
8. 最终 `PASS/FAIL` 由确定性规则计算；模型不得修改已判分结果。
9. 不得输出真实个人信息；示例只能使用明显虚构的数据。
10. 每次输出必须记录模型、Prompt 版本和生成批次。
11. 未定义的多意图、澄清或转人工规则必须标记 `PRODUCT_RULE_GAP`，不得临时指定“主要意图”。
12. 模型建议答案只能写入 `suggested_answer_draft`，不得写入 `expected_answer_text`。
13. 任何 P0 或合规不确定项必须醒目标记，不得在汇总时省略或平均稀释。
