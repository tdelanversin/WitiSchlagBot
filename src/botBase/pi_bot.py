import logging
import traceback
import html
import json
import re
import datetime
from functools import partial
from telegram import Update
from telegram.ext import ContextTypes, ApplicationBuilder, CommandHandler, Application
from telegram.constants import ParseMode
from telegram.error import NetworkError, BadRequest
from urllib3.exceptions import HTTPError

DEVELOPER_CHAT_ID = 631157495
IGNORED_ERRORS = [NetworkError, HTTPError]


def generate_logs(log_fh):
    def match_date(line):
        matchThis = ""
        matched = re.match(r"\d\d\d\d-\d\d-\d\d\ \d\d:\d\d:\d\d,\d\d\d", line)
        if matched:
            matchThis = matched.group()
        else:
            matchThis = "NONE"
        return matchThis

    currentDict = {}
    for line in log_fh:
        if line.startswith(match_date(line)):
            if currentDict:
                yield currentDict
            currentDict = {
                "date": datetime.datetime.strptime(
                    line.split("__")[0][:23], "%Y-%m-%d %H:%M:%S,%f"
                ),
                "source": line.split("-", 5)[3],
                "level": line.split("-", 5)[4][1:-1],
                "text": line.split("-", 5)[-1],
            }
        else:
            currentDict["text"] += line
    yield currentDict


async def fetch_log(
    logfile: str, update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat.id != DEVELOPER_CHAT_ID:  # type: ignore
        return

    datetime_cuttoff = datetime.datetime.now() - datetime.timedelta(days=1)
    log_level = logging.WARNING

    if context.args:
        for arg in context.args:
            try:
                if arg.startswith("-logfile="):
                    logfile = arg.split("-logfile=")[-1]
                elif arg.startswith("-datetime_cuttoff="):
                    datetime_cuttoff = datetime.datetime.strptime(
                        arg.split("-datetime_cuttoff=")[-1], "%Y-%m-%d %H:%M:%S"
                    )
                elif arg.startswith("-days="):
                    datetime_cuttoff = datetime.datetime.now() - datetime.timedelta(
                        days=int(arg.split("-days=")[-1])
                    )
                elif arg.startswith("-log_level="):
                    log_level = getattr(logging, arg.split("-log_level=")[-1])
            except Exception as e:
                logging.error(f"Error while parsing arguments: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,  # type: ignore
                    text=f"Error while parsing arguments: {e}",
                    parse_mode=ParseMode.HTML,
                )

    with open(logfile, "r") as log_fh:
        logs = generate_logs(log_fh)

        for log in logs:
            # print(log["date"], datetime_cuttoff, getattr(logging, log["level"]), log_level)
            if (
                log["date"] < datetime_cuttoff
                or getattr(logging, log["level"]) < log_level
            ):
                continue

            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,  # type: ignore
                    text=f"<b>{log['date']} - {log['source']} - {log['level']}:</b>\n{log['text']}",
                    parse_mode=ParseMode.HTML,
                )
            except BadRequest:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,  # type: ignore
                    text=f"<b>{log['date']} - {log['source']} - {log['level']}:</b>\n{log['text']}",
                )


    logging.info(
        f"Sent log for {logfile} to {update.effective_chat.title} "  # type: ignore
        f"({update.effective_chat.id})",  # type: ignore
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if type(context.error) in IGNORED_ERRORS:
        logging.warning(f"Ignoring error or type: {type(context.error).__name__}")
        return

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    logging.error(message)


def start_bot(
    bot_name: str,
    commands: list,
    log_file: str,
    token: str,
    post_init: callable, # type: ignore
    handlers: list,
):
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        filename=log_file,
        filemode="w",
    )

    logging.info(f"Starting {bot_name} bot")

    logging.info(f"Registered commands:\n{commands}")

    application = ApplicationBuilder().token(token).post_init(post_init).build()

    application.add_handler(CommandHandler("log", partial(fetch_log, log_file)))
    application.add_handlers(handlers)
    application.add_error_handler(error_handler)

    application.run_polling()
