from http.cookies import SimpleCookie
import logging as log
from encryption import Encrypter
from samoware_api import SamowarePollingContext
from context import Context
import migrations
from psycopg_pool import AsyncConnectionPool
import env


def make_context(telegram_id: int, row: tuple) -> Context:
    cookies = SimpleCookie()
    cookies.load(row[1])
    return Context(
        telegram_id=telegram_id,
        samoware_login=row[0],
        polling_context=SamowarePollingContext(
            cookies=cookies,
            session=row[2],
            ack_seq=row[3],
            request_id=row[4],
            command_id=row[5],
            rand=row[6],
        ),
        last_revalidation=row[7],
    )


def make_connection_pool() -> AsyncConnectionPool:
    connections_count = env.get_postgres_connections_count()
    connection_string = env.get_postgres_connection_string()
    log.debug(f"Creating connection pool with {connections_count} connections")
    return AsyncConnectionPool(
        connection_string,
        min_size=connections_count,
        max_size=connections_count,
        open=False
    )


class Database:
    def __init__(self, encrypter: Encrypter) -> None:
        log.debug("initializing db...")
        self.pool = make_connection_pool()
        self.encrypter = encrypter
        migrations.apply()
        log.info("db has initialized")

    async def open(self):
        await self.pool.open()
        log.info("db has opened")

    def is_open(self) -> bool:
        log.debug(f"check db is open = {not self.pool.closed}")
        return not self.pool.closed

    async def close(self) -> None:
        await self.pool.close()
        log.info("db was closed")

    async def add_user(self, telegram_id: int, ctx: Context) -> None:
        pctx = ctx.polling_context
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO users \
                 (telegram_id, samoware_login, samoware_password, samoware_cookies, samoware_session, samoware_ack_seq, samoware_request_id, samoware_command_id, samoware_rand, last_revalidation, autoread) VALUES \
                 (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (telegram_id, ctx.samoware_login, None, pctx.cookies.output(header=""), pctx.session, pctx.ack_seq, pctx.request_id, pctx.command_id, pctx.rand, ctx.last_revalidation, False)
            )
            await conn.commit()
            log.debug(f"user {telegram_id} has inserted")

    async def set_password(self, telegram_id: int, password: str) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE users SET samoware_password=%s WHERE telegram_id=%s",
                (self.encrypter.encrypt(password), telegram_id)
            )
            await conn.commit()
            log.debug(f"set password for the user {telegram_id}")

    async def set_handler_context(self, ctx: Context) -> None:
        pctx = ctx.polling_context
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE users \
                 SET samoware_cookies=%s, samoware_session=%s, samoware_ack_seq=%s, samoware_request_id=%s, samoware_command_id=%s, samoware_rand=%s, last_revalidation=%s \
                 WHERE telegram_id=%s",
                (pctx.cookies.output(header=""), pctx.session, pctx.ack_seq, pctx.request_id, pctx.command_id, pctx.rand, ctx.last_revalidation, ctx.telegram_id),
            )
            await conn.commit()
            log.debug(f"samoware context for the user {ctx.telegram_id} has inserted")

    async def get_samoware_context(self, telegram_id: int) -> Context | None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT samoware_login, samoware_cookies, samoware_session, samoware_ack_seq, samoware_request_id, samoware_command_id, samoware_rand, last_revalidation \
                 FROM users \
                 WHERE telegram_id=%s",
                (telegram_id,),
            )).fetchone()
            await conn.commit()
            if row is None:
                log.warning(
                    f"trying to fetch context for {telegram_id}, but context does not exist"
                )
                return None
            log.debug(f"requested samoware context for the user {telegram_id}")
            return make_context(telegram_id, row)

    async def get_password(self, telegram_id: int) -> str | None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT samoware_password FROM users WHERE telegram_id=%s", (telegram_id,)
            )).fetchone()
            await conn.commit()
            log.debug(f"requested password for the user {telegram_id}")
            return (
                self.encrypter.decrypt(row[0])
                if row is not None and row[0] is not None
                else None
            )

    async def is_user_active(self, telegram_id: int) -> bool:
        async with self.pool.connection() as conn:
            is_active = (
                (await (await conn.execute(
                    "SELECT COUNT(*) FROM users WHERE telegram_id = %s", (int(telegram_id),)
                )).fetchone())[0]
                != 0
            )
            await conn.commit()
            log.debug(f"user {telegram_id} is active: {is_active}")
            return is_active

    async def get_all_users(self) -> list[Context]:
        def mapper(row):
            return make_context(
                telegram_id=row[0],
                row=row[1:]
            )

        async with self.pool.connection() as conn:
            users = list(
                map(
                    mapper,
                    await (await conn.execute(
                        "SELECT telegram_id, samoware_login, samoware_cookies, samoware_session, samoware_ack_seq, samoware_request_id, samoware_command_id, samoware_rand, last_revalidation \
                         FROM users"
                    )).fetchall(),
                )
            )
            await conn.commit()
            log.debug(
                f"fetching all users from database, an amount of the users {len(users)}"
            )
            return users

    async def get_all_users_stat(self) -> list[tuple[bool, bool]]:
        def mapper(row):
            (password, autoread) = row
            return (
                password is not None,
                bool(autoread),
            )

        async with self.pool.connection() as conn:
            users = list(
                map(
                    mapper,
                    await (await conn.execute(
                        "SELECT samoware_password, autoread FROM users"
                    )).fetchall(),
                )
            )
            await conn.commit()
            log.debug(
                f"fetching all users from database for gathering statistics, an amount of the users {len(users)}"
            )
            return users

    async def remove_user(self, telegram_id: int) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "DELETE FROM users WHERE telegram_id=%s", (telegram_id,)
            )
            await conn.commit()
            log.debug(f"user {telegram_id} was removed")

    async def set_autoread(self, telegram_id: int, enabled: bool) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE users SET autoread=%s WHERE telegram_id=%s",
                (
                    enabled,
                    telegram_id,
                ),
            )
            await conn.commit()
            log.debug(f"autoread for {telegram_id} was set to {enabled}")

    async def get_autoread(self, telegram_id: int) -> bool:
        async with self.pool.connection() as conn:
            enabled = (await (await conn.execute(
                "SELECT autoread FROM users WHERE telegram_id=%s", (telegram_id,)
            )).fetchone())[0]
            await conn.commit()
            log.debug(f"autoread for {telegram_id} is set to {enabled}")
            return enabled
