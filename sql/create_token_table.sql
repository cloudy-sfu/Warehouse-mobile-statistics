create table if not exists tokens
(
    username integer not null
        constraint username
            primary key,
    password TEXT    not null
);