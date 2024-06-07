import asyncio
import logging as log
from datetime import datetime, timedelta
import re
from typing import Self

from aiohttp import ClientSession, ClientTimeout
from context import Context

from const import (
    HTML_FORMAT,
    HTTP_CONNECT_LONGPOLL_TIMEOUT_SEC,
    HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC,
    LONGPOLL_RETRY_DELAY_SEC,
    MARKDOWN_FORMAT,
)
from database import Database
import samoware_api
from samoware_api import (
    Mail,
    UnauthorizedError,
)
from util import MessageSender

REVALIDATE_INTERVAL = timedelta(hours=5)
SESSION_TOKEN_PATTERN = re.compile("^[0-9]{6}-[a-zA-Z0-9]{20}$")

SUCCESSFUL_LOGIN = "Доступ выдан. Все новые письма будут пересылаться в этот чат."
CAN_NOT_REVALIDATE_PROMPT = "Невозможно продлить сессию из-за внутренней ошибки. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_"
SESSION_EXPIRED_PROMPT = "Сессия доступа к почте истекла. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_"
WRONG_CREDS_PROMPT = "Неверный логин или пароль."
HANDLER_IS_ALREADY_WORKED = "Доступ уже был выдан."
HANDLER_IS_ALREADY_SHUTTED_DOWN = "Доступ уже был отозван."


class ClientHandler:
    def __init__(
        self,
        message_sender: MessageSender,
        db: Database,
        context: Context,
    ):
        self.message_sender = message_sender
        self.db = db
        self.context = context

    async def make_new(
        telegram_id: int,
        samoware_login: str,
        samoware_password: str,
        message_sender: MessageSender,
        db: Database,
    ) -> Self | None:
        if db.is_client_active(telegram_id):
            await message_sender(
                telegram_id, HANDLER_IS_ALREADY_WORKED, MARKDOWN_FORMAT
            )
            return None
        polling_context = samoware_api.login(samoware_login, samoware_password)
        if polling_context is None:
            await message_sender(telegram_id, WRONG_CREDS_PROMPT, MARKDOWN_FORMAT)
            return None
        polling_context = samoware_api.set_session_info(polling_context)
        polling_context = samoware_api.open_inbox(polling_context)
        context = Context(telegram_id, samoware_login, polling_context)
        db.add_client(telegram_id, context)
        await message_sender(telegram_id, SUCCESSFUL_LOGIN, MARKDOWN_FORMAT)
        return ClientHandler(message_sender, db, context)

    async def make_from_context(
        context: Context, message_sender: MessageSender, db: Database
    ) -> Self | None:
        return ClientHandler(message_sender, db, context)

    async def start_handling(self) -> asyncio.Task:
        self.polling_task = asyncio.create_task(self.polling())
        return self.polling_task

    def get_polling_task(self) -> asyncio.Task:
        return self.polling_task

    async def stop_handling(self) -> None:
        if not (self.polling_task.cancelled() or self.polling_task.done()):
            self.polling_task.cancel()
        await asyncio.wait([self.polling_task])

    async def polling(self) -> None:
        http_session = ClientSession(
            timeout=ClientTimeout(
                connect=HTTP_CONNECT_LONGPOLL_TIMEOUT_SEC,
                total=HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC,
            )
        )

        retry_count = 0
        polling_context = self.context.polling_context
        log.info(f"longpolling for {self.context.samoware_login} is started")

        while self.db.is_client_active(self.context.telegram_id):
            try:
                self.db.set_handler_context(self.context)
                (polling_result, polling_context) = await samoware_api.longpoll_updates(
                    polling_context, http_session
                )
                if samoware_api.has_updates(polling_result):
                    (mails, polling_context) = samoware_api.get_new_mails(
                        polling_context
                    )
                    for mail_header in mails:
                        log.info(f"new mail for {self.context.telegram_id}")
                        log.debug(f"email flags: {mail_header.flags}")
                        mail_body = samoware_api.get_mail_body_by_id(
                            polling_context, mail_header.uid
                        )
                        await self.forward_mail(Mail(mail_header, mail_body))
                if self.context.last_revalidate + REVALIDATE_INTERVAL < datetime.now():
                    new_context = samoware_api.revalidate(polling_context)
                    if new_context is None:
                        log.warning(
                            f"can not revalidate session for user {self.context.telegram_id} {self.context.samoware_login}"
                        )
                        await self.can_not_revalidate()
                        break
                    polling_context = new_context
                    polling_context = samoware_api.set_session_info(polling_context)
                    polling_context = samoware_api.open_inbox(polling_context)
                    self.context.last_revalidate = datetime.now()
                retry_count = 0
                self.context.polling_context = polling_context
            except asyncio.CancelledError:
                break
            except UnauthorizedError:
                log.info(f"session for {self.context.samoware_login} expired")
                await self.session_has_expired()
                self.db.remove_client(self.context.telegram_id)
                break
            except Exception as error:
                log.exception("exception in client_handler: " + str(error))
                log.info(
                    f"retry_count={retry_count}. Retrying longpolling for {self.context.samoware_login} in {LONGPOLL_RETRY_DELAY_SEC} seconds..."
                )
                retry_count += 1
                await asyncio.sleep(LONGPOLL_RETRY_DELAY_SEC)

        await http_session.close()
        log.info(f"longpolling for {self.context.samoware_login} stopped")

    async def can_not_revalidate(self):
        await self.message_sender(
            self.context.telegram_id,
            CAN_NOT_REVALIDATE_PROMPT,
            MARKDOWN_FORMAT,
        )

    async def session_has_expired(self):
        await self.message_sender(
            self.context.telegram_id,
            SESSION_EXPIRED_PROMPT,
            MARKDOWN_FORMAT,
        )

    async def forward_mail(self, mail: Mail):
        from_str = f'<a href="copy-this-mail.example/{mail.header.from_mail}">{mail.header.from_name}</a>'
        to_str = ", ".join(
            f'<a href="copy-this-mail.example/{recipient[0]}">{recipient[1]}</a>'
            for recipient in mail.header.recipients
        )

        mail_text = f'{mail.header.local_time.strftime("%d.%m.%Y %H:%M")}\n\nОт кого: {from_str}\n\nКому: {to_str}\n\n<b>{mail.header.subject}</b>\n\n{mail.body.text}'

        await self.message_sender(
            self.context.telegram_id,
            mail_text,
            HTML_FORMAT,
            mail.body.attachments if len(mail.body.attachments) > 0 else None,
        )