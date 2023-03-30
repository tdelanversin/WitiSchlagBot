import logging
import traceback
import html
import json
from datetime import time

from mensa import get_mensa, available
from mensa_helper import (
    format_favorites,
    mensa_menu,
    update_favorite_pickle,
    load_favorite_pickle,
)

from telegram.constants import ParseMode
from telegram.error import NetworkError
from telegram import (
    Update,
)
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="mensa_bot.log",
)

DEVELOPER_CHAT_ID = 631157495
IGNORED_ERRORS = [NetworkError]
ERRORS_TO_LOG = []
MENSAS = [mensa.aliases[0] for mensa in available]
FAVORITE_MENSAS = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FAVORITE_MENSAS
    if update.effective_chat.id != DEVELOPER_CHAT_ID:
        return

    FAVORITE_MENSAS = load_favorite_pickle()

    for chat_id in FAVORITE_MENSAS:
        context.job_queue.run_daily(
            favorite_job,
            time=time(10, 00),
            days=(1, 2, 3, 4, 5),
            chat_id=chat_id,
            name=str(chat_id),
        )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm back online!",
    )

    logging.info(
        f"Started bot with id {context.bot.id} "
        + f"and name {context.bot.name} "
        + f"by {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


async def error_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != DEVELOPER_CHAT_ID:
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="The following errors occured:\n"
        + "\n".join(ERRORS_TO_LOG),
    )


async def mensa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0 or context.args[0] not in MENSAS:  # type: ignore
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please provide a valid mensa name. "
            + f"Valid mensas are: \n{', '.join(MENSAS)}",
        )

        logging.info(
            f"Invalid mensa name provided by {update.effective_user.name} "
            + f"with id {update.effective_user.id}"
        )
        return
    else:
        await mensa_menu(context.args[0], update, context)  # type: ignore


async def generic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.effective_message.text[1:].split("@")[0]
    if command in MENSAS:  # type: ignore
        await mensa_menu(command, update, context)
        return

    logging.info(
        f"Received command {update.effective_message.text} "
        + f"from {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


async def mensa_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in FAVORITE_MENSAS:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You can only use this command with an active daily menu job.",
        )
        return
    if len(FAVORITE_MENSAS[chat_id]) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You don't have any favorite mensas yet. "
            + "Use /add to add a mensa to your favorites.",
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=format_favorites(chat_id, FAVORITE_MENSAS),
        parse_mode=ParseMode.HTML,
    )


async def favorite_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    message = format_favorites(job.chat_id, FAVORITE_MENSAS)

    await context.bot.send_message(
        chat_id=job.chat_id, text=message, parse_mode=ParseMode.HTML
    )

    logging.info(f"Sent favorite mensas to chat with id {job.chat_id}")


async def set_daily_mensa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_message.chat_id
    if context.job_queue.get_jobs_by_name(str(chat_id)):
        await update.effective_message.reply_text(
            "You already have an active daily mensa job!"
        )
        return

    FAVORITE_MENSAS[chat_id] = set()
    context.job_queue.run_daily(
        favorite_job,
        time=time(10, 00),
        days=(1, 2, 3, 4, 5),
        chat_id=chat_id,
        name=str(chat_id),
    )
    await update.effective_message.reply_text(
        "Successfully set daily mensa job for favorite mensas!"
    )

    update_favorite_pickle(FAVORITE_MENSAS)

    logging.info(
        f"Set daily mensa job for {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def unset_daily_mensa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not current_jobs:
        await update.message.reply_text("You have no active daily mensa job!")
        return
    FAVORITE_MENSAS.pop(chat_id)
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("Successfully unset daily mensa job!")

    update_favorite_pickle(FAVORITE_MENSAS)

    logging.info(
        f"Unset daily mensa job for {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def add_favorite_mensa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_message.chat_id not in FAVORITE_MENSAS:
        await update.message.reply_text(
            "Please set a daily mensa job first with /set_daily_mensa"
        )
        return

    success = []
    for arg in context.args:  # type: ignore
        if arg not in MENSAS:
            await update.message.reply_text(
                f"{arg} is not a valid mensa name. "
                + f"Valid mensas are: \n{', '.join(MENSAS)}"
            )
            continue

        FAVORITE_MENSAS[update.effective_message.chat_id].add(arg)  # type: ignore
        success.append(arg)

    success[-1] = "and " + success[-1]

    await update.message.reply_text(
        f"Successfully added {', '.join(success)} to favorite mensas!"  # type: ignore
    )

    update_favorite_pickle(FAVORITE_MENSAS)

    logging.info(
        f"Added {', '.join(success)} to favorite mensas for {update.effective_chat.title} "  # type: ignore
        + f"with id {update.effective_chat.id}"
    )


async def remove_favorite_mensa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_message.chat_id not in FAVORITE_MENSAS:
        await update.message.reply_text(
            "Please set a daily mensa job first with /set_daily_mensa"
        )
        return

    success = []
    for arg in context.args:  # type: ignore
        if arg not in MENSAS:
            await update.message.reply_text(
                f"{arg} is not a valid mensa name. "
                + f"Valid mensas are: \n{', '.join(MENSAS)}"
            )
            continue

        FAVORITE_MENSAS[update.effective_message.chat_id].remove(arg)  # type: ignore
        success.append(arg)

    success[-1] = "and " + success[-1]

    await update.message.reply_text(
        f"Successfully removed {', '.join(success)} from favorite mensas!"  # type: ignore
    )

    update_favorite_pickle(FAVORITE_MENSAS)

    logging.info(
        f"Removed {', '.join(success)} from favorite mensas for {update.effective_chat.title} "  # type: ignore
        + f"with id {update.effective_chat.id}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    if any([type(context.error) == err for err in IGNORED_ERRORS]):
        logging.warning(f"Ignoring error or type: {type(context.error).__name__}")
        logging.debug(f"Error: {context.error}")
        await context.bot.send_message(
            chat_id=DEVELOPER_CHAT_ID,
            text=f"Ignoring error or type: {type(context.error).__name__}",
        )
        return

    logging.error("Exception while handling an update:", exc_info=context.error)
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

    ERRORS_TO_LOG.append(message)


if __name__ == "__main__":
    with open("GRAILLE.token") as f:
        token = f.readlines()[0]
    application = ApplicationBuilder().token(token).build()

    commands = (
        "mensa - Get the menu for a mensa\n"
        "set - Set a daily mensa job for your favorite mensas\n"
        "unset - Unset a daily mensa job\n"
        "add - Add a mensa to your favorite mensas\n"
        "remove - Remove a mensa from your favorite mensas\n"
        "favorite - Get the menu for your favorite mensas. Only Works if you have a daily mensa job set\n"
    )

    commands += "\n".join(
        [f"{mensa} - Get the menu for {get_mensa(mensa).name}" for mensa in MENSAS]
    )

    logging.info(f"Registered commands:\n{commands}")

    handlers = [
        CommandHandler("start", start),
        CommandHandler("log", error_log),
        CommandHandler("mensa", mensa),
        CommandHandler("set", set_daily_mensa),
        CommandHandler("unset", unset_daily_mensa),
        CommandHandler("add", add_favorite_mensa),
        CommandHandler("remove", remove_favorite_mensa),
        CommandHandler("favorite", mensa_favorites),
        MessageHandler(filters.COMMAND, generic_command),
    ]

    application.add_handlers(handlers)
    application.add_error_handler(error_handler)

    application.run_polling()
