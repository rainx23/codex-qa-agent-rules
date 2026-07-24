# Skills

可执行 QA 工作流的目录入口。

## 目录定位

存放按任务类型路由的 Skill；每个具体 Skill 以自身 `SKILL.md` 为正式入口。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `*/SKILL.md` | 任务工作流、输入输出和门禁 | 是 |

## 使用入口

- 从根目录 `AGENTS.md` 的任务路由选择对应 `SKILL.md`。
- 本目录实际包含 6 个 QA Skills：4 个核心交付链 Skills（Requirement、Diff、Testcase、Artifact）和 2 个按需支撑型 Skills（Knowledge、API Automation）。

## 维护约束

- 新增或改变 Skill 路由、输入输出或门禁时同步更新本 README、根 README 和受影响测试。
- 不为每个 Skill 重复创建 README。
- 本目录不含自动生成文件。
- 确认回复处理必须保留原始任务范围；blocking 归零后由需求、用例和产物 Skill 自动续跑，不要求重复指令。
- 需求 Skill 建立条件矩阵，用例 Skill 消费行为覆盖并执行多入口核心去重：2 至 5 个入口逐分支设计，不少于 6 个同规则入口使用完整全局适用入口范围。
- 产物 Skill 的日常正式链最终只运行一次 `validate_task.py`，只复验当前产物和当前 Index 记录；全量 Schema、历史 Manifest、历史 testcase 与正式产物扫描只属于发布/CI 门禁。
- 正式链不得采用空模型初始化、JSON Patch 自动修复循环或重复调用同一校验脚本；确定性错误由代码处理，业务语义错误才返回模型。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
