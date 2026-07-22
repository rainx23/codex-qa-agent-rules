source_record_id: kydoc:8d7990ebf9a144aaa2a2a350a257faad
document_title: 3S轮询兼容新增/删除数据行方案
retrieved_via: mcp__kydoc__kydocDetailSearchByGuid
captured_at: 2026-07-20 00:00:00
captured_timezone: Asia/Shanghai

# 一、背景

3秒轮询T0股弹窗的汇总条和股票列表统计范围不同导致数据对不上；T0股弹窗只是其中一个例子，目前3S轮询方案都存在该情况。
汇总条全局统计更新，盯盘过程有新成交的股票也会统计进去。
股票列表局部更新：点击查询时加载股票列表并定版，后续只轮询定版股票，盯盘过程有新交易的股票不会自动统计。

# 二、整改要点

开启轮询条件：查询交易日期条件的开始和结束必须都是当天。
不调整指标逻辑口径；日期只要是当天且能查询出数据就可以轮询，底仓等特殊数据来源不影响正常轮询。
增删页面需要更新当前页数据、全局序号、分页条数和分页数。
PC当前页不是最后一页，或者最后一页没有被删完时：新增数据插入全局分页末尾；删除数据后由后续数据向前移动补全。
最后一页被删除完时，自动回退到上一个最近有数据的分页，前端不需要请求获取最新全量rowKey。
已知异常场景：假设原有100页且当前在第100页，被删除两页后，点击上一页时数据会为空。

# 三、接口参数说明

轮询标识为 `$.params.roundRobin=true`。
PC端 `$.pageSize` 传实际 pageSize，`$.page` 按实际页码传参。
轮询全量 key 为有序的 `$.params.roundRobinRowKey`，使用逗号拼接。
可视范围开始位置为 `$.params.visibleStartIdx`，从0开始，位置基于 roundRobinRowKey。
可视范围结束位置为 `$.params.visibleEndIdx`，位置基于 roundRobinRowKey。
`$.params.rowKey` 只用于通过 rowKey 查询数据，不能与 roundRobinRowKey 一起使用。

# 四、接口返回与分页规则

返回行位于 `$.data.rows`，每行包含 `$.data.rowKeyType`。
rowKeyType枚举：0表示可视范围有效，1表示数据补全，2表示新增，3表示删除。
如果由0和1类型组成的有效数据不满一页，按照 pageSize 补全；新增和删除行不参与补全数量计算。
最后一页数据全部删除时返回最近一个分页的数据，前端不需要请求获取最新全量rowKey。
如果请求 page 大于实际总页数，返回 page 重置为实际总页数。
返回分页信息包含 rowTotal、pageTotal、page、pageSize。

# 五、后端校验与兼容

rowKey 和 roundRobinRowKey 同时非空时抛出异常。
roundRobin=true 时 rowKey 非空则抛出异常。
roundRobin=false 或 null 时 roundRobinRowKey 非空则抛出异常。
轮询时由于会动态新增数据，动态列调整为返回所有字段；非轮询继续兼容动态列参数。

# 六、处理与监控

轮询模式下 StarRocks 查询内部 pageSize 设置为1500、page设置为1并不执行 count，Groovy 重新计算 rowTotal、pageTotal、page、pageSize 并给 rows 标记 rowKeyType。
通过 StarRocks 审计表统计3S轮询请求返回数据量是否超过1200条；灰度环境每日执行一次，对超过阈值的接口告警并同步到巡检群。
