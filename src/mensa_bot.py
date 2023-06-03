import logging
from datetime import time
import pytz
import pickle
import numpy as np

from botBase import pi_bot, mensa_helpers, reaction_emojis

from telegram.constants import ParseMode
from telegram import (
    Update,
)
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    Application,
)


LOG_FILE = "WitiGrailleBotFiles/bot.log"
BOT_TOKEN_FILE = "WitiGrailleBotFiles/TOKEN.token"
FAVORITES_FILE = "WitiGrailleBotFiles/favorite_mensas.pickle"
DEVELOPER_CHAT_ID = 631157495
ERRORS_TO_LOG = []
MENSAS = [mensa.aliases[0] for mensa in mensa_helpers.available]
FAVORITE_MENSAS = {}
FAVORITE_TIME = time(9, 00, tzinfo=pytz.timezone("Europe/Zurich"))
TIMES = ["11:30", "11:45", "12:00", "12:15", "12:30", "12:45", "13:00"]


def update_favorite_pickle():
    global FAVORITE_MENSAS
    with open(FAVORITES_FILE, "wb") as f:
        pickle.dump(FAVORITE_MENSAS, f)


def load_favorite_pickle():
    global FAVORITE_MENSAS
    try:
        with open(FAVORITES_FILE, "rb") as f:
            FAVORITE_MENSAS = pickle.load(f)
    except (FileNotFoundError, EOFError):
        pass


async def mensa_menu(mensa, update, context):
    mensa = mensa_helpers.get_mensa(mensa)
    meals = mensa.get_meals()
    if len(meals) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I couldn't find a menu for today. Please try again tomorrow.",
        )
        logging.info(
            f"Couldn't find a menu for {mensa.name} today "
            + f"for {update.effective_chat.title} "
            + f"with id {update.effective_chat.id}"
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=mensa_helpers.mensa_format(mensa, meals),
        parse_mode=ParseMode.HTML,
    )

    logging.info(
        f"Sent menu for {mensa} to {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


def format_favorites(chat_id):
    message = "Favorite mensas:\n\n"

    mensa_emojis = np.random.permutation(reaction_emojis.REACTION_EMOJIS)[
        : len(FAVORITE_MENSAS[chat_id])
    ]

    for emoji, mensa in zip(mensa_emojis, FAVORITE_MENSAS[chat_id]):
        mensa = mensa_helpers.get_mensa(mensa)
        meals = mensa.get_meals()
        if len(meals) == 0:
            continue

        message += f"{emoji}{mensa_helpers.mensa_format(mensa, meals)}\n\n"

    return message


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


async def post_init(application: Application):
    global FAVORITE_MENSAS
    load_favorite_pickle()

    for chat_id in FAVORITE_MENSAS:
        application.job_queue.run_daily(
            favorite_job,
            time=FAVORITE_TIME,
            days=(1, 2, 3, 4, 5),
            chat_id=chat_id,
            name=str(chat_id),
        )

    await application.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID,
        text="Bot started!",
    )
    logging.info(
        f"Started bot with id {application.bot.id} "
        + f"and name {application.bot.name}"
    )


async def generic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.effective_message.text[1:].split("@")[0]
    if command in MENSAS:  # type: ignore
        await mensa_helpers.mensa_menu(command, update, context)
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
        logging.info(
            f"Received favorite command with no active menu job "
            + f"from {update.effective_user.name} "
            + f"with id {update.effective_user.id}"
        )
        return
    
    if len(FAVORITE_MENSAS[chat_id]) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You don't have any favorite mensas yet. "
            + "Use /add to add a mensa to your favorites.",
        )
        logging.info(
            f"Received favorite command with no favorite mensa "
            + f"from {update.effective_user.name} "
            + f"with id {update.effective_user.id}"
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=format_favorites(chat_id),
        parse_mode=ParseMode.HTML,
    )
    logging.info(
        f"Sent favorite mensa "
        + f"to {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


async def make_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await context.bot.send_poll(
        chat_id=chat_id,
        question="What time do you want to eat at today?",
        options=TIMES,
        type="regular",
        allows_multiple_answers=True,
        is_anonymous=False,
    )

    await context.bot.send_poll(
        chat_id=chat_id,
        question="Which mensa do you want to eat at today?",
        options=[
            mensa_helpers.get_mensa(mensa).name for mensa in FAVORITE_MENSAS[chat_id]
        ],
        type="regular",
        allows_multiple_answers=True,
        is_anonymous=False,
    )


async def favorite_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    message = format_favorites(job.chat_id)

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
        time=FAVORITE_TIME,
        days=(1, 2, 3, 4, 5),
        chat_id=chat_id,
        name=str(chat_id),
    )
    await update.effective_message.reply_text(
        "Successfully set daily mensa job for favorite mensas!"
    )

    update_favorite_pickle()

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

    update_favorite_pickle()

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

    update_favorite_pickle()

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

    update_favorite_pickle()

    logging.info(
        f"Removed {', '.join(success)} from favorite mensas for {update.effective_chat.title} "  # type: ignore
        + f"with id {update.effective_chat.id}"
    )


if __name__ == "__main__":
    with open(BOT_TOKEN_FILE) as f:
        token = f.readlines()[0]
    application = ApplicationBuilder().token(token).build()

    commands = (
        "mensa - Get the menu for a mensa\n"
        "set - Set a daily mensa job for your favorite mensas\n"
        "unset - Unset a daily mensa job\n"
        "add - Add a mensa to your favorite mensas\n"
        "remove - Remove a mensa from your favorite mensas\n"
        "favorite - Get the menu for your favorite mensas. Only Works if you have a daily mensa job set\n"
        "poll - Create a poll for the menu of a mensa\n"
    )

    commands += "\n".join(
        [
            f"{mensa} - Get the menu for {mensa_helpers.get_mensa(mensa).name}"
            for mensa in MENSAS
        ]
    )

    handlers = [
        CommandHandler("mensa", mensa),
        CommandHandler("set", set_daily_mensa),
        CommandHandler("unset", unset_daily_mensa),
        CommandHandler("add", add_favorite_mensa),
        CommandHandler("remove", remove_favorite_mensa),
        CommandHandler("favorite", mensa_favorites),
        CommandHandler("poll", make_poll),
        MessageHandler(filters.COMMAND, generic_command),
    ]

    pi_bot.start_bot("mensa", commands, LOG_FILE, token, post_init, handlers)
