create table if not exists "%s"
(
    date_and_time      TEXT not null,
    usage_type         TEXT not null,
    charge_type        TEXT not null,
    destination_number TEXT,
    unit               TEXT not null,
    charged_units      REAL not null,
    amount             REAL not null
);