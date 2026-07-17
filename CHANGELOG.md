# 版本历史

本文档记录影响规则行为、目录结构、使用方式、脚本能力、校验结果或产物契约的版本变化。

版本号唯一来源为根目录 [RULE_VERSION](RULE_VERSION)。历史信息只能依据 Git diff、提交、tag、Release、已有版本文件或用户确认补充；无法确认时必须明确标记，不得编造。

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [2.4.0] - 2026-07-17

### Added

- 新增功能目录 README 治理规则与统一的版本历史文件。
- 新增 `scripts/validate_repository_docs.py`，校验目录 README、CHANGELOG 与 RULE_VERSION 的一致性。
- 新增对应单元测试，并将文档治理校验接入 CI 发布门禁。

### Changed

- 根 README 和 AGENTS 增加目录导航、文档影响判断及版本维护入口。
- Schema、Manifest 示例和相关 Golden 数据更新为规则版本 2.4.0。

## [2.3.0] - 日期待确认

### Baseline

- 以可验证的 2.3.0 仓库状态作为版本历史基线。
- 更早版本的具体变更缺少可验证依据，待通过 Commit、tag、Release 或用户确认补充。
