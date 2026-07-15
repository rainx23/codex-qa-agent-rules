create table demo.orders (
    order_id bigint not null comment '脱敏订单标识'
    , trade_date date not null
    , amount decimal(18, 2) null
    , status varchar(16) null
    , primary key (order_id)
)
engine=olap
duplicate key(order_id)
distributed by hash(order_id) buckets 3
properties ('replication_num' = '1');
