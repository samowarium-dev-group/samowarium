#!/bin/python3

import logging.handlers
from telegram_bot import TelegramBot
from prometheus_client import start_http_server
import asyncio

import logging
import signal

from metrics import GATHER_METRIC_DELAY_SEC, clients_amount_metric, log_metric
from const import DB_FOLDER_PATH, DB_PATH, LOGGER_FOLDER_PATH, LOGGER_PATH
from database import Database
import env
import util


class Application:
    async def start(self) -> None:
        self.db = Database(DB_PATH)
        self.bot = TelegramBot(self.db)
        await self.bot.start_bot()
        self.gathering_metric_task = asyncio.create_task(
            self.gather_clients_amount_metric()
        )
        self.setupShutdown(asyncio.get_event_loop())

    def setupShutdown(self, event_loop: asyncio.AbstractEventLoop):
        async def shutdown(signal) -> None:
            logging.info(f"received exit signal {signal}")
            logging.info("closing db connection")
            self.db.close()
            self.gathering_metric_task.cancel()
            await self.bot.stop_bot()
            logging.info("application has stopped successfully")

        for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            event_loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s))
            )

    async def gather_clients_amount_metric(self):
        try:
            while self.db.is_open():
                clients = self.db.get_all_clients_stat()
                for pswd, autoread in (
                    (x, y) for x in (True, False) for y in (True, False)
                ):
                    clients_amount_metric.labels(pswd=pswd, autoread=autoread).set(
                        len(
                            list(
                                filter(
                                    lambda x: x[2] == pswd and x[3] == autoread, clients
                                )
                            )
                        )
                    )
                await asyncio.sleep(GATHER_METRIC_DELAY_SEC)
        except:
            pass


def setup_logger():
    LOGGER_LEVEL = logging.INFO
    if env.is_debug():
        LOGGER_LEVEL = logging.DEBUG
    util.make_dir_if_not_exist(LOGGER_FOLDER_PATH)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=LOGGER_PATH,
        encoding="utf-8",
        level=LOGGER_LEVEL,
    )
    logging.getLogger("httpx").setLevel(logging.WARN)
    if env.is_prod_profile():
        logging.getLogger("telegram.ext.Updater").setLevel(logging.CRITICAL)

    class MetricsHandler(logging.Handler):
        def emit(self, record):
            log_metric.labels(level=record.levelname).inc()

    logging.getLogger("root").addHandler(MetricsHandler())


async def main() -> None:
    setup_logger()
    util.make_dir_if_not_exist(DB_FOLDER_PATH)
    if env.is_prometheus_metrics_server_enabled():
        port = env.get_prometheus_metrics_server_port()
        logging.info(f"starting the metrics server on {port} port...")
        start_http_server(int(port))
    logging.info("starting the application...")
    app = Application()
    await app.start()
    await asyncio.gather(
        *[task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    )


if __name__ == "__main__":
    asyncio.run(main())
