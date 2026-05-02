-- staging — сырые данные, core — нормализованная модель, mart — аналитические витрины, meta — служебная информация.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS meta;
