create table demo.orders (
    id bigint not null default 0 comment 'primary key',
    amount decimal(18, 2),
    tax decimal(18, 2),
    total_amount decimal(18, 2) generated always as (round(amount + tax, 2)),
    primary key (id)
)
engine=olap
distributed by hash(id) buckets 3
properties (
    "replication_num" = "1",
    "storage_medium" = "SSD"
);
