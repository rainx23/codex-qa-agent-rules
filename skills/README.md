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

## 维护约束

- 新增或改变 Skill 路由、输入输出或门禁时同步更新本 README、根 README 和受影响测试。
- 不为每个 Skill 重复创建 README。
- 本目录不含自动生成文件。
- 确认回复处理必须保留原始任务范围；blocking 归零后由需求、用例和产物 Skill 自动续跑，不要求重复指令。
- 需求 Skill 建立条件矩阵，用例 Skill消费行为覆盖并执行多入口核心去重，产物 Skill 统一扫描 passed 正式产物。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
