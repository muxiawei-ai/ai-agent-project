# Atlas Style · 可复制样式块

新页面从这里起步：把下面的 CSS 变量块原样拷入 `<style>` 开头（根类名可换），
组件片段按需取用。所有值都来自已验证的 `docs/贷款申请客户旅程看板.html`。

## 1. CSS 变量与基础

```css
:root { color-scheme: light; }
* { margin: 0; padding: 0; box-sizing: border-box; }

.atlas {
  --page: #f3efe2;         /* 页面底（米灰） */
  --paper: #fbf8ef;        /* 图面纸色 */
  --panel: #e9eef0;        /* 侧栏冷灰蓝 */
  --ink: #24272e;          /* 主墨色 */
  --ink-2: #565a63;        /* 次级墨 */
  --muted: #8b8574;        /* 弱化（暖灰） */
  --hairline: #d9d2bf;     /* 细线 */
  --blue: #38699f;         /* 主色（石板蓝） */
  --blue-wash: rgba(56,105,159,0.22);
  --accent: #b5502f;       /* 砖红 · 强调/警示 */
  --ai: #e0a000;           /* 琥珀金 · 第二维度 */
  --serif: Georgia, "Times New Roman", "Songti SC", "STSong", "SimSun", serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, "Courier New", monospace;

  font-family: var(--serif);
  background: var(--page);
  color: var(--ink);
  min-height: 100vh;
  padding: 30px 22px 56px;
}
.wrap { max-width: 1240px; margin: 0 auto; }
```

## 2. 页头与眉标

```css
.eyebrow {
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
  color: var(--ink-2); text-transform: uppercase;
}
.eyebrow .no { color: var(--accent); }
header h1 { font-size: 30px; font-weight: 700; letter-spacing: 0.02em; }
header .rule { border: none; border-top: 1.5px solid var(--ink); margin: 14px 0 10px; }
header .sub {
  display: flex; flex-wrap: wrap; gap: 6px 22px; align-items: baseline;
  font-family: var(--mono); font-size: 11.5px; color: var(--ink-2);
}
```

```html
<header>
  <div class="eyebrow"><span class="no">01</span> · PROJECT · DOCUMENT TYPE</div>
  <h1>衬线大标题：一句话说清这页是什么</h1>
  <hr class="rule">
  <div class="sub"><span>元信息 A</span><span>元信息 B</span></div>
</header>
```

## 3. 卡片与图注

```css
.fig {
  background: var(--paper); border: 1px solid var(--hairline); border-radius: 3px;
  padding: 20px 22px 16px;
}
.figcap {
  font-family: var(--serif); font-style: italic; font-size: 12.5px; color: var(--ink-2);
  margin-top: 10px; line-height: 1.6;
}
.figcap b { font-style: normal; }
```

图注格式：`<div class="figcap"><b>图 1</b> · 说明文字，彩色关键词内联充当图例，
如 <span style="color:var(--accent)">红色标记</span>为异常项。</div>`

## 4. 点阵纹理（SVG pattern）

```js
// 大图纸面点阵网格
var pat = el('pattern', { id: 'dotgrid', width: 26, height: 26, patternUnits: 'userSpaceOnUse' });
pat.appendChild(el('circle', { cx: 1, cy: 1, r: 0.9, fill: 'rgba(36,39,46,0.055)' }));
// 数据面积 stipple 填充
var sp = el('pattern', { id: 'stipple', width: 7, height: 7, patternUnits: 'userSpaceOnUse' });
sp.appendChild(el('circle', { cx: 1.5, cy: 1.5, r: 1.15, fill: '#38699f', opacity: 0.4 }));
```

## 5. 悬停提示框

```css
.tip {
  position: fixed; z-index: 30; pointer-events: none; display: none;
  background: #fffef9; border: 1px solid var(--ink); border-radius: 2px;
  padding: 9px 12px; font-size: 12px; box-shadow: 3px 3px 0 rgba(36,39,46,0.12);
  max-width: 270px; font-family: var(--serif);
}
.tip .tt { font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; color: var(--ink-2); margin-bottom: 5px; }
.tip .tval { font-weight: 700; font-variant-numeric: tabular-nums; }
.tip .tlab { color: var(--ink-2); font-size: 11.5px; }
```

## 6. 控件（筛选/按钮）

```css
.seg button, .btn {
  appearance: none; cursor: pointer; background: var(--paper);
  border: 1px solid var(--hairline); border-radius: 2px;
  font-family: var(--mono); font-size: 12px; color: var(--ink-2);
  padding: 6px 13px;
}
.seg button:hover, .btn:hover { border-color: var(--ink-2); }
.seg button[aria-pressed="true"] {
  border: 1.5px solid var(--ink); color: var(--ink); font-weight: 700; background: #fff;
}
.flabel { font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.18em; color: var(--muted); }
```

## 7. 表格

```css
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
thead th {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; font-weight: 500;
  color: var(--ink-2); border-top: 1.5px solid var(--ink); border-bottom: 1px solid var(--hairline);
}
th, td { text-align: right; padding: 7px 10px; white-space: nowrap; }
tbody td { border-bottom: 1px dotted var(--hairline); font-family: var(--mono); font-size: 11.5px; color: var(--ink-2); }
tbody tr:last-child td { border-bottom: 1.5px solid var(--ink); }
th:first-child, td:first-child { text-align: left; }
tbody td:first-child { font-family: var(--serif); font-size: 13px; color: var(--ink); }
```

## 8. 侧栏面板与统计块

```css
.panel {
  background: var(--panel); border: 1px solid var(--hairline); border-radius: 3px;
  padding: 18px; display: flex; flex-direction: column; gap: 14px;
  position: sticky; top: 14px;   /* 长内容页让侧栏跟随 */
}
.sbox { background: #fdfcf7; border: 1px solid var(--hairline); padding: 11px 12px 9px; }
.sbox .v { font-family: var(--serif); font-size: 25px; font-weight: 700; line-height: 1.05; }
.sbox .l { font-family: var(--mono); font-size: 10px; color: var(--ink-2); margin-top: 5px; line-height: 1.5; }
.sbox.ai-box { border-top: 2.5px solid var(--ai); }   /* 用色条标记维度归属，数字保持墨色 */
.note {   /* 斜体批注块 */
  border: 1px solid var(--hairline); background: #fdfcf7; padding: 10px 12px;
  font-style: italic; font-size: 12.5px; line-height: 1.65;
}
```

## 9. 无障碍检查清单

- 三色组合 `#38699f / #b5502f / #e0a000` 在 `#fbf8ef` 纸面上已通过
  dataviz validate_palette（最差色对 CVD ΔE 20.1，均 ≥3:1 对比）——换色必须重跑
- 交互 SVG：容器 `role="group"`，可点元素 `role="button"` + `tabindex="0"` +
  完整中文 `aria-label`；重渲染后 `.focus()` 归还焦点；focus 与 hover 同样触发提示框
- 9–10px 等宽小字只做装饰性标注，关键数值不允许只以小字出现（表格/提示框兜底）
