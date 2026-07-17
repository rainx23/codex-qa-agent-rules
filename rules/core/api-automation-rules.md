# 接口自动化分析与用例生成规则

当前接口自动化只支持 `assertion_scope=parameter_health`，固定健康检查为 `content.code=0` 与 `content.msg=OK`。健康性断言只证明参数组合能够成功传递并触发有效分支，健康性断言 ≠ 业务数据断言；不得据此宣称业务返回数据、指标、排序、跨接口一致性、数据库结果或页面对账正确。`business_assertion_status` 当前固定为 `not_implemented`，缺少业务响应字段断言不构成 blocked。

本文件是接口自动化通用规则的唯一正文来源。Skill 只规定加载、交接和输出，不复制本文件。

## 定位与证据

本仓库只分析接口契约、参数、有效 Groovy/SQL 分支和已有自动化覆盖，并生成平台可导入的 `.xlsx` 与 UTF-8 参数文本；不执行接口、SQL、数据库、登录态或调度，不修改业务代码。参数类型、默认值、必填性、URL、Header、接口 code 和分支必须有来源证据，不能按变量名臆测。

## 动作判定

`create` 适用于新接口、无已有自动化、明确要求新建或新增长期回归核心接口；`update` 适用于请求参数/类型/默认值/必填性/单值多值、URL/method/header/body、Groovy 分支、SQL 动态条件、分页排序或现有组合覆盖变化；纯样式、文案、注释、日志或不改变契约的内部重构通常为 `none`；缺少接口、默认有效请求、成功协议、完整代码或维护用例为 `blocked`。

## 分析与参数化

- Groovy 至少识别 `params.xxx`、`request.xxx`、JSON/Map 字段、类型转换、`split`、列表/日期转换、默认值、null/空串/空集合、if/else、switch、三元、Elvis、提前 return 和联合条件。
- SQL 至少识别 `${param}`、`:param`、`#{param}`、动态 where、in、空值查全部、日期范围、分页、排序、join 和绑定字段变化。SQL 不用于生成数据结果、行数、排序、金额、指标或对数断言。
- 参数组合覆盖需求明确规则、有效代码分支、SQL 动态条件、单值/多值差异、参数依赖和默认路径；每个有效分支至少一组代表数据，不做无依据笛卡尔积。
- 默认一个接口一条 Excel 用例。只有 URL、method、body 结构、Header/鉴权、成功标准或业务动作真正不同才拆行。
- 单参数文本使用一维数组；关联参数名用英文逗号连接，值使用二维组合数组。平台变量固定为 `$parameterName`，禁止 `{{name}}`。

## Excel 与断言

列名和顺序固定为：`序号, 用例名称, method, url, body类型, body, headers, 校验, 优先级, 接口code`。method 小写，URL 完整，body/headers/校验为紧凑合法 JSON，body 变量使用 `$name`。新建用例名为 `AUTO-模块-页面路径-接口功能-接口名称`；维护保留原名。

公司平台自动处理鉴权；只保留用户、已有用例或代码明确提供的 Header，不新增 Authorization、Cookie、token 或身份 Header。健康检查固定为 `content.code` 等于整数 `0`、`content.msg` 等于字符串 `OK`。本仓库当前固定协议不支持自定义；接口不符合该协议时必须标记为不适用或 pending。

## 输出与门禁

输出影响结论、参数变化表、分支覆盖表、`.xlsx`、`<slug>-parameter.txt` 和 API Automation Model。模型必须通过 `scripts/validate_schemas.py`；Excel 与参数文本必须通过 `scripts/validate_api_automation_artifacts.py`。发现无证据参数、未定义 `$` 变量、非法 JSON、重复接口行或维度不一致时失败，不降级校验强度。
