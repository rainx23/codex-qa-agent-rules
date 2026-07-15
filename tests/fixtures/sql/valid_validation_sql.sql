/************************************************************************************************
** sql
** author: 卢更鑫
** create time: 2026-07-15 00:00:00
** description: 验证脱敏订单金额汇总
** comment: SELECT * FROM database.tablename WHERE id=${id} AND address='${address}';
************************************************************************************************/
/*参数处理*/
with v_param as (
    select '${trade_date}' as trade_date
)
/*订单明细*/
, v_order as (
    select
        order_id
        , trade_date
        , amount
        , status
    from demo.orders
    where trade_date = (select trade_date from v_param)
)
select
    trade_date
    , sum(amount) as order_amount
from v_order
where status = '已确认'
group by trade_date;
