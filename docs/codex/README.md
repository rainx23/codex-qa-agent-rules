# Codex 文档

面向 Codex 使用和发布验证的兼容文档入口。

## 目录定位
保存使用说明、模板和发布验收清单，不替代 `rules/` 中的正式规则。

## 主要内容

- `rule-validation-checklist.md`：发布前必跑命令。
- `*-rules.md`、`*-templates.md`：兼容文档和使用说明。

## 使用入口
- 发布前执行 `rule-validation-checklist.md` 的完整校验。

## 维护约束
- 正式规则变更时只更新必要引用，不复制完整规则正文；发布命令变更时同步更新 CI、脚本 README 和测试。

完整版本历史见 [CHANGELOG.md](../../CHANGELOG.md)。
