/**
 * spine.local.js 模板 —— 真实数据的本地承载文件
 *
 * 用法：
 *   1. 复制本文件为同目录下的 spine.local.js（该文件名已被 .gitignore 排除，永不进入 Git）
 *   2. 参照 spine.js 的结构，把真实的旅程参数 / 工单场景 / 对话数据填进去
 *   3. 各页面在加载 spine.js 之后会加载 spine.local.js，本文件的赋值将整体覆盖演示数据
 *
 * ⚠ 纪律：
 *   - 对话数据写入前必须脱敏（姓名 / 手机号 / 证件号 / 银行卡号）
 *   - 本文件永远不要 commit、不要截图、不要通过 IM 传输原文件
 *   - 校验是否生效：打开门户 index.html，页头「数据脊柱」应显示你在下方填写的 version
 */
window.JOURNEY_SPINE = {
  version: 'local · 填写你的版本标识',

  journey: {
    stages: ['申请发送', '开始操作', '提交申请', '还款卡验证', '签署电子合同', '提交放款', '合同激活'],
    conv: [0.74, 0.68, 0.72, 0.52, 0.90, 0.95],
    regions: ['华东', '华南', '华北', '华中', '西南', '西北'],
    regionWeights: [1.35, 1.15, 1.0, 0.85, 0.7, 0.45],
    baseDaily: 620
  },

  workorders: {
    slaHours: 24,
    scenarios: [
      // { id: 'WO-01', name: '场景名', station: 3, weight: 0.30 }
    ]
  },

  sessions: [
    // { id: 'S001', title: '会话标题', turns: [{ role: 'customer'|'ai', text: '…', intent: '…', sentiment: -2..2, issue: '…' }] }
  ]
};
