#!/bin/python3

# скрипт миграции sqlite -> postgres

import sqlite3
import psycopg2
import json

import env

# telegram_id             text PRIMARY KEY,

# samoware_login          text NOT NULL,
# samoware_password       text,
# samoware_cookies        text NOT NULL,
# samoware_session        text NOT NULL,
# samoware_ack_seq        int NOT NULL,
# samoware_request_id     int NOT NULL,
# samoware_command_id     int NOT NULL,
# samoware_rand           int NOT NULL,

# last_revalidation       timestamp with time zone NOT NULL,
# autoread                boolean NOT NULL DEFAULT false


def save_data(users):
    host, port = env.get_postgres_host().split(":")
    connection = psycopg2.connect(
        dbname=env.get_postgres_db(),
        host=host,
        port=port,
        user=env.get_postgres_user(),
        password=env.get_postgres_password(),
    )
    cursor = connection.cursor()

    if len(users) == 0:
        print("no users to migrate")
        return

    query = (
        "truncate users; insert into users (telegram_id, samoware_login, samoware_password, samoware_cookies, samoware_session, samoware_ack_seq, samoware_request_id,samoware_command_id,samoware_rand,last_revalidation,autoread) values \n"
        + ",\n".join(f"({(', '.join(str(x) for x in user))})" for user in users)
        + ";"
    )
    print(query)

    cursor.execute(query)
    connection.commit()


def map_user(user):
    d = json.loads(user[1])

    def wrapped(x):
        return "'" + x + "'"

    telegram_id = wrapped(str(user[0]))

    samoware_login = wrapped(d["login"])
    if user[2] is not None:
        samoware_password = wrapped("\\x" + user[2].hex()) + "::bytea"
    else:
        samoware_password = "null"
    samoware_cookies = wrapped(d["cookies"])
    samoware_session = wrapped(d["session"])
    samoware_ack_seq = d["ack_seq"]
    samoware_request_id = d["request_id"]
    samoware_command_id = d["command_id"]
    samoware_rand = d["rand"]

    last_revalidation = wrapped(str(d["last_revalidate"]).replace("T", " "))
    autoread = bool(int(user[3]))

    return (
        telegram_id,
        samoware_login,
        samoware_password,
        samoware_cookies,
        samoware_session,
        samoware_ack_seq,
        samoware_request_id,
        samoware_command_id,
        samoware_rand,
        last_revalidation,
        autoread,
    )


def load_data():
    connection = sqlite3.connect("./db/database.db", check_same_thread=False)
    users = connection.execute(
        """
        select * from clients;
    """
    ).fetchall()

    return [map_user(user) for user in users]


# users = [
#     ("\'12314\'", "\'zvk22u464\'", "\'\\x0\'::bytea", "\'bbb\'", "\'ccc\'", 0, 1, 2, 3, "now()", False),
#     # ("\'12315\'", "\'zvk22u464\'", "\'aaa\'", "\'bbb\'", "\'ccc\'", 0, 1, 2, 3, "now()", True),
# ]
users = load_data()

save_data(users)

print(f"\nmigrated {len(users)} users")
