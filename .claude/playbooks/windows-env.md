# 问题域：Windows 终端环境

## 含中文 / ¥ 的输出不在终端 print（GBK 报错），改写 UTF-8 文件再 Read
- **问题域**: WindowsGBK
- **症状**: 在 Windows 终端 `print` 含中文或 `¥` 等非 ASCII 字符的内容时，触发 `UnicodeEncodeError`（GBK 编码无法表示），脚本中断或输出乱码。
- **根因**: Windows 终端默认编码为 GBK，Python `print` 走终端编码，中文 / `¥` 等字符在 GBK 下编码失败。
- **解决方案**: **含中文 / `¥` 的内容不在终端 print**，改为写入 **UTF-8 文件**，再用 Read 工具读出查看：
  - 写：`open(path, "w", encoding="utf-8").write(text)`（或 Write 工具，默认 UTF-8）。
  - 看：用 Read 工具读该文件，避免经过终端 GBK 编码。
  - 排查 / 调试输出（采集结果、断言明细、解码内容等）一律走「UTF-8 文件 + Read」，不在终端直接打印中文。
- **适用 agent**: 所有需 print 中文的 agent（selector-debug / gio-tracking / code-engineer / session-recap / ...）
- **最近验证日期**: 2026-06-09
