# IEEEtran 图表格式统一指南

更新时间：2026-06-29

参考资料：

- 本地文件：`/home/ubuntu/zjx/evalTriage-paper/IEEEtran_HOWTO.pdf`
- 当前论文骨架：`/home/ubuntu/zjx/evalTriage-paper/main.tex`
- 当前章节文件：`/home/ubuntu/zjx/evalTriage-paper/sections/*.tex`
- ICSE 2027 Research Track：<https://conf.researchr.org/track/icse-2027/icse-2027-research-track>

本文档规定 EvalTriage 论文中 figure、table、subfigure、caption 和浮动体的统一写法。目标是减少排版返工，同时避免因手调 IEEE format 触发 desk-reject 风险。

## 1. 总原则

- 使用 IEEEtran 默认格式，不改 class。
- 不全局修改 margins、font size、column width、line spacing、`\textfloatsep`、`\intextsep`、`\abovecaptionskip`、`\belowcaptionskip`。
- Figure 和 table 优先放在页面或列的顶部。
- 避免把浮动体强行放在正文中间。
- 图表必须在正文首次引用后再插入。
- Figure caption 放在图下方。
- Table caption 放在表上方。
- `\label` 必须放在 `\caption` 之后，或放在 `\caption` 内部。
- 图表标题要解释 takeaway，不只写文件名或指标名。
- 所有图表都必须能黑白打印辨认。

## 2. LaTeX preamble 建议

保守 preamble：

```latex
\documentclass[10pt,conference]{IEEEtran}

\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{array}
```

如需要 subfigure，用 `subfig`，不要用 `subcaption`：

```latex
\ifCLASSOPTIONcompsoc
  \usepackage[caption=false,font=normalsize,labelfont=sf,textfont=sf]{subfig}
\else
  \usepackage[caption=false,font=footnotesize]{subfig}
\fi
```

不要加入：

```latex
\usepackage{geometry}
\usepackage{caption}
\usepackage{subcaption}
\usepackage{algorithm2e}
```

原因：这些包容易覆盖 IEEEtran 的 caption、spacing 或 float 样式。

## 3. 单栏 figure 模板

统一使用 `[!t]`，图居中，caption 在图后，label 在 caption 后：

```latex
\begin{figure}[!t]
  \centering
  \includegraphics[width=\columnwidth]{figures/evaltriage_pipeline.pdf}
  \caption{Overview of EvalTriage. The system compares baseline and current evaluation manifests, plans factor-directed replay, and produces a diagnosis report.}
  \label{fig:pipeline}
\end{figure}
```

写作规则：

- 单栏图宽优先用 `width=\columnwidth`。
- 不要用 `\begin{center}...\end{center}` 包图；用 `\centering`。
- 不要在 figure 前后手写 `\vspace`。
- 在正文里引用为 `Fig.~\ref{fig:pipeline}`。

## 4. 双栏 figure 模板

只有当图在单栏下不可读时才用 `figure*`：

```latex
\begin{figure*}[!t]
  \centering
  \includegraphics[width=\textwidth]{figures/rq1_evidence_overview.pdf}
  \caption{RQ1 evidence overview across projects, deviation symptoms, and engineering factors.}
  \label{fig:rq1-overview}
\end{figure*}
```

双栏图注意事项：

- 双栏浮动体通常不会出现在定义它的同一页，所以要提前放在 LaTeX 源码中。
- 优先使用 `[!t]`，不要依赖 `[!b]`。
- 只有在出现严重 underfull vbox 且无法通过移动 figure 解决时，才在 figure 内部局部使用极小 `\vspace*{-3pt}` 级别调整。
- 不要用能把内容放在两栏中间的包或结构。

## 5. 子图模板

推荐用于 ablation 或 pipeline 对比图。大多数情况下不要给每个子图写长 subcaption，而是在主 caption 中解释 `(a)`、`(b)`、`(c)`。

```latex
\begin{figure*}[!t]
  \centering
  \subfloat[]{%
    \includegraphics[width=0.32\textwidth]{figures/rq3_main.pdf}
    \label{fig:rq3-main}
  }\hfil
  \subfloat[]{%
    \includegraphics[width=0.32\textwidth]{figures/rq3_ablation.pdf}
    \label{fig:rq3-ablation}
  }\hfil
  \subfloat[]{%
    \includegraphics[width=0.32\textwidth]{figures/rq3_negative.pdf}
    \label{fig:rq3-negative}
  }
  \caption{Factor attribution results. (a) EvalTriage full. (b) Ablated variants. (c) Negative calibration cases.}
  \label{fig:rq3-summary}
\end{figure*}
```

规则：

- 所有子图宽度总和必须小于 `\textwidth`。
- 子图之间使用 `\hfil` 做均匀间隔。
- 如不需要子图 caption，仍保留 `\subfloat[]` 的空可选参数，用于生成 `(a)`、`(b)` 标签。

## 6. 单栏 table 模板

Table caption 在表上方。表内默认 footnotesize，优先用 `booktabs`，避免竖线。

```latex
\begin{table}[!t]
  \caption{Paper-only Diagnosis Results}
  \label{tab:paper-only-results}
  \centering
  \renewcommand{\arraystretch}{1.12}
  \begin{tabular}{lrrrr}
    \toprule
    Bucket & Cases & Detected & Top-1 & All-case \\
    \midrule
    Completed rollout & 16 & 12 & 12/12 & 12/16 \\
    Failed run & 4 & 4 & 4/4 & 4/4 \\
    Combined & 20 & 16 & 16/16 & 16/20 \\
    \bottomrule
  \end{tabular}
\end{table}
```

规则：

- Caption 使用 Title Case。
- 单栏表不要超过 `\columnwidth`。
- 数字列右对齐；文本列左对齐。
- 表内只保留必要小数位，例如 `0.782` 或 `78.2\%`，不要堆满长浮点数。
- 不用竖线，除非表结构实在需要。
- 若表太宽，先删列、缩短列名或拆表；不要直接 `\resizebox{\columnwidth}{!}{...}` 作为首选。

## 7. 双栏 table 模板

用于 factor matrix 或 robustness appendix：

```latex
\begin{table*}[!t]
  \caption{Combined Robustness Results by Factor}
  \label{tab:robustness-factor}
  \centering
  \renewcommand{\arraystretch}{1.10}
  \begin{tabular}{lrrrrl}
    \toprule
    Factor & Cases & Detected & Top-1 & Negative & Notes \\
    \midrule
    Action/controller & 5 & 5 & 5/5 & 0 & completed-rollout \\
    Checkpoint/config & 8 & 8 & 8/8 & 0 & rollout + failed-run \\
    Dependency/runtime & 8 & 4 & 4/4 & 4 & failure-supported + negative calibration \\
    Seed/randomness & 8 & 0 & -- & 8 & no false attribution \\
    \bottomrule
  \end{tabular}
\end{table*}
```

规则：

- 双栏表优先放 appendix 或 Results 开头。
- 不要让表跨页；跨页表在 conference paper 中很难控制。
- 如果表超过一页宽，拆成 main table + appendix detail。

## 8. 表格 footnote

简单说明优先放 caption 或正文，不要滥用 footnote。必须放表下注释时，用 `threeparttable`，但只在确有需要时引入：

```latex
\usepackage{threeparttable}
```

```latex
\begin{table}[!t]
  \caption{Ablation Results}
  \label{tab:ablation}
  \centering
  \begin{threeparttable}
  \begin{tabular}{lrr}
    \toprule
    Method & Top-1 & N/A \\
    \midrule
    EvalTriage full & 43/43 & 0 \\
    No episode evidence & 20/31 & 12 \\
    \bottomrule
  \end{tabular}
  \begin{tablenotes}
    \footnotesize
    \item N/A indicates cases where the method has no applicable evidence source.
  \end{tablenotes}
  \end{threeparttable}
\end{table}
```

## 9. 图片文件格式

优先级：

1. PDF vector：流程图、bar chart、line chart、heatmap、taxonomy 图。
2. PNG：截图、渲染结果、无法矢量化的 bitmap。
3. JPEG：照片类图片，一般本论文不需要。

EvalTriage 推荐：

- RQ1 overview：PDF。
- Pipeline：PDF 或 TikZ/矢量图。
- Metric charts：PDF。
- Screenshots / videos frame：PNG，至少 300 dpi 等效清晰度。

不要：

- 用低分辨率 PNG 表示线图。
- 把矢量图导出成 bitmap 后再转回 PDF。
- 在图里用太小的字体。
- 用红绿作为唯一编码；必须有 marker、hatch、label 或灰度差异。

## 10. Caption 写法

Figure caption 句式：

```text
Fig. X. What the reader should learn from the visual, not merely what file it is.
```

Table caption 句式：

```text
TABLE X
SHORT TITLE THAT DESCRIBES THE RESULT
```

LaTeX 中只写内容，IEEEtran 会处理编号和样式：

```latex
\caption{Combined Robustness Results}
```

EvalTriage caption 应该包含：

- benchmark / split，例如 paper-only、combined robustness。
- denominator，例如 detected/applicable 或 all-case。
- 主要 takeaway，例如 no false attribution on negative calibration。

避免：

- “Results”
- “Ablation”
- “RQ3 table”
- 太长、塞满所有数字的 caption。

## 11. 正文引用规范

统一写法：

- Figure：`Fig.~\ref{fig:pipeline}`
- Table：`Table~\ref{tab:paper-only-results}`
- Section：`Section~\ref{sec:approach}`
- RQ：`RQ1`、`RQ2`

不要硬编码：

```latex
Fig. 1
Table II
```

## 12. EvalTriage 正文图表建议

10 页正文建议最多放：

| 位置 | 图表 | 宽度 | 目的 |
|---|---|---|---|
| Introduction / Approach | Fig. pipeline | 双栏或单栏 | 解释系统数据流 |
| Empirical Study | Fig. RQ1 overview | 双栏 | 展示 473 evidence 的 taxonomy |
| Evaluation | Table paper-only results | 单栏 | 主实验结果 |
| Evaluation | Table ablation | 单栏或双栏 | 证明 replay 和 episode evidence 必要 |
| Evaluation | Table cost | 单栏 | RQ4 成本 |

Appendix / supplement：

- 55-case combined robustness factor matrix。
- Failed-run details。
- Negative calibration table。
- RQ2 true/flaky 补充结果。

## 13. 排版不要做的事

- 不要为了省半页改 `\baselinestretch`。
- 不要改 `\oddsidemargin`、`\textwidth`、`\textheight`。
- 不要全局调小 caption font。
- 不要全局压缩 `\textfloatsep`。
- 不要用 `\vspace{-10pt}` 到处硬压。
- 不要用 `H` 强制浮动体固定位置。
- 不要把算法放进 `algorithm2e` 浮动体；如果需要算法展示，用 figure 或普通 text/pseudocode。
- 不要把未引用的图表放进正文。

## 14. 最终检查清单

- [ ] 每个 figure 使用 `\centering`。
- [ ] Figure caption 在图下方。
- [ ] Table caption 在表上方。
- [ ] 每个 `\label` 在 `\caption` 之后或内部。
- [ ] 单栏图宽不超过 `\columnwidth`。
- [ ] 双栏图宽不超过 `\textwidth`。
- [ ] 表格没有溢出列宽。
- [ ] 表格数字列对齐，小数位统一。
- [ ] 图中文字在双栏打印后仍可读。
- [ ] 图表在正文中先引用后出现。
- [ ] 没有全局 spacing / margin hacks。
- [ ] 所有图表都服务一个明确 RQ 或 takeaway。
