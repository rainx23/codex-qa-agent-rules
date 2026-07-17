---
name: qa-api-automation
description: 用于接口自动化影响分析、新接口自动化生成和现有自动化维护，解析 Groovy、SQL、请求参数和已有用例，生成 Excel 用例导入文件与参数化文本并执行静态校验。API automation, parameterization, maintenance, Groovy, SQL, Excel case import.
---

# QA 接口自动化

固定 `content.code=0`、`content.msg=OK` 仅用于 `parameter_health`；必须明确“不代表业务响应数据已经完成校验”，本阶段不生成业务字段、指标、排序、数据库或跨系统断言。

将 Skill 根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则与交接

1. 完整读取 `../../rules/core/api-automation-rules.md`；需要 Groovy/SQL 细节时再读取 `../../rules/profiles/api-automation-groovy-sql.md`。
2. 需求输入先交给 `../qa-requirement-analysis/SKILL.md`，Diff 输入先交给 `../qa-diff-impact-analysis/SKILL.md`；在各自报告中追加接口自动化影响评估，不改变人工 XMind 层级。
3. 使用 `../../scripts/qa_contracts.py` 中的 API Automation Model 作为唯一结构化交接模型；运行 `../../scripts/generate_schemas.py` 生成 Schema，不手工维护副本。

## 执行流程

1. 识别 `new` 或 `maintenance`。确认 URL、method、body 类型、接口 code、默认有效请求和已有用例证据；缺少阻塞材料时输出 `blocked`，不猜测字段、类型、Header 或接口 code。
2. 提取请求参数、默认值、类型、必填性、单值/多值格式及证据；解析 Groovy 的条件分支、转换、空值判断、提前返回和联合条件。
3. 解析 SQL 中的参数绑定、动态 where、in、日期、分页、排序和 join 条件，只用于分支覆盖分析，不执行 SQL 或生成数据结果断言。
4. 建立参数—分支关系，按有效分支生成最小参数组合；禁止无依据笛卡尔积。默认一个接口生成一条 Excel 行。
5. 新建用例使用 `AUTO-模块-页面路径-接口功能-接口名称`；维护用例保留原名并最小修改，保留有效 body、headers、优先级和接口 code。
6. 生成 `<slug>-case.xlsx` 和 `<slug>-parameter.txt`，参数变量只使用 `$name`；不生成参数 CSV。
7. Excel 生成使用 `../../scripts/generate_api_automation_excel.py`，完成后运行 `../../scripts/validate_api_automation_artifacts.py` 与 `../../scripts/validate_schemas.py`。任一失败都不得宣称产物完成。

## 边界

不执行真实接口、SQL、登录态或数据库连接，不搭建 HTTP/报告/调度/性能框架，不修改业务 Groovy 或 SQL。默认只生成 `content.code=0` 与 `content.msg=OK` 健康检查；其他断言须有用户提供的成功协议证据。
