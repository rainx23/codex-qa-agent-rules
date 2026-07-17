# 验证 SQL 编写规范

SQL author 唯一来源为 `rules-repository.json.sql_defaults.author`，时区和方言同样读取 `sql_defaults`；规则、脚本和样例不得写死个人姓名。SQL 样式通过仅证明静态格式与只读安全，不代表 SQL 业务口径正确，报告必须明确 SQL 未执行。

本文件是验证 SQL 的唯一正式样式来源。其他规则和 Skills 只引用本文件，不复制完整正文。

## 顶部注释

正式 SQL 必须以星号块开头，并包含：

```sql
/************************************************************************************************
** sql
** author: ${rules-repository.json.sql_defaults.author}
** create time: yyyy-MM-dd HH:mm:ss
** description: 根据当前需求生成具体描述
** comment: SELECT * FROM database.tablename WHERE id=${id} AND address='${address}';
************************************************************************************************/
```

`author` 从 `rules-repository.json.sql_defaults.author` 读取，`create time` 使用配置时区并精确到秒。配置缺失或非法时校验失败，不能静默使用其他姓名。

integrated 业务仓库缺少 `sql_defaults.author` 时必须输出明确迁移错误并停止；不得继续使用旧硬编码姓名、操作系统用户名或任何静默回退。公共规则仓库默认配置为 `Rainx`，但校验器不自动修改业务仓库配置，除非用户明确授权。

## 排版与方言

- 正文关键字使用小写；查询列、CTE、分组项和排序项使用逗号前置，函数参数逗号后保留一个空格。
- CTE 使用 `v_` 前缀；首个 CTE 注释放在 `with` 前一行，后续 CTE 注释放在逗号前一行；CTE 之间不强制增加空行。
- 默认优先 Doris/StarRocks，主要兼容 StarRocks 5.1.0；JSON 炸开使用 `, lateral json_each(parse_json(col))`，不把其他方言机械转换。
- 不擅自修改表名、字段名、数据源或业务别名。默认不使用 `select *` 和 `limit`，只返回验证所需字段。
- 简短表达式保持单行，复杂表达式按语义换行；不为了对齐制造无意义纵向布局。

## 安全边界

默认只允许 `select` 或 `with ... select`。禁止 insert、update、delete、merge、alter、drop、truncate、create、grant、revoke、账号、密码、Token、JDBC URL 和私钥。框架只生成和静态校验 SQL，绝不连接或执行数据库。
