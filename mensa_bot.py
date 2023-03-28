import logging
from mensa import get_meals, get_mensa, available
from datetime import time
import telegram
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

MENSAS = [mensa.aliases[0] for mensa in available]
FAVORITE_MENSAS = {}
MEAL_FORMAT = """{label} <i>({price_student}, {price_staff}, {price_extern})</i>
<b>{meal_name}</b>
{meal_description}"""


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
        text=format_favorites(chat_id),
        parse_mode=telegram.constants.ParseMode.HTML,  # type: ignore
    )


async def favorite_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    message = format_favorites(job.chat_id)

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=message,
        parse_mode=telegram.constants.ParseMode.HTML,  # type: ignore
    )

    logging.info(f"Sent favorite mensas to chat with id {job.chat_id}")


def format_favorites(chat_id):
    message = "Favotire mensas:\n\n"

    def meal_format(meal):
        return MEAL_FORMAT.format(
            label=meal.label,
            price_student=meal.price_student,
            price_staff=meal.price_staff,
            price_extern=meal.price_extern,
            meal_name=meal.description[0],
            meal_description=" ".join(meal.description[1:]),
        )

    for mensa in FAVORITE_MENSAS[chat_id]:
        meals = get_meals(mensa)
        if len(meals) == 0:
            continue

        formated_meal = "\n\n".join([meal_format(m) for m in meals])
        message += f"          <b><i>{mensa.upper()}</i></b>:\n\n{formated_meal}\n\n"

    return message


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
        time=time(hour=10, minute=0, second=0),
        days=(1, 2, 3, 4, 5),
        chat_id=chat_id,
        name=str(chat_id),
    )
    await update.effective_message.reply_text(
        "Successfully set daily mensa job for favorite mensas!"
    )

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

    logging.info(
        f"Unset daily mensa job for {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def add_favorite_mensa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if len(context.args) == 0 or context.args[0] not in MENSAS:  # type: ignore
        await update.message.reply_text(
            "Please provide a valid mensa name. "
            + f"Valid mensas are: \n{', '.join(MENSAS)}"
        )
        return
    if update.effective_message.chat_id not in FAVORITE_MENSAS:
        await update.message.reply_text(
            "Please set a daily mensa job first with /set_daily_mensa"
        )
        return
    FAVORITE_MENSAS[update.effective_message.chat_id].add(context.args[0])  # type: ignore
    await update.message.reply_text(
        f"Successfully added {context.args[0]} to favorite mensas!"  # type: ignore
    )

    logging.info(
        f"Added {context.args[0]} to favorite mensas for {update.effective_chat.title} "  # type: ignore
        + f"with id {update.effective_chat.id}"
    )


async def remove_favorite_mensa(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if len(context.args) == 0 or context.args[0] not in MENSAS:  # type: ignore
        await update.message.reply_text(
            "Please provide a valid mensa name. "
            + f"Valid mensas are: \n{', '.join(MENSAS)}"
        )
        return
    if update.effective_message.chat_id not in FAVORITE_MENSAS:
        await update.message.reply_text(
            "Please set a daily mensa job first with /set_daily_mensa"
        )
        return
    FAVORITE_MENSAS[update.effective_message.chat_id].remove(context.args[0])  # type: ignore
    await update.message.reply_text(
        f"Successfully removed {context.args[0]} from favorite mensas!"  # type: ignore
    )

    logging.info(
        f"Removed {context.args[0]} from favorite mensas for {update.effective_chat.title} "  # type: ignore
        + f"with id {update.effective_chat.id}"
    )


async def mensa_menu(mensa, update, context):
    meals = get_meals(mensa)
    if len(meals) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I couldn't find a menu for today. " + "Please try again tomorrow.",
        )
        logging.info(
            f"Couldn't find a menu for {mensa} today "
            + f"for {update.effective_chat.title} "
            + f"with id {update.effective_chat.id}"
        )
        return

    def meal_format(meal):
        return MEAL_FORMAT.format(
            label=meal.label,
            price_student=meal.price_student,
            price_staff=meal.price_staff,
            price_extern=meal.price_extern,
            meal_name=meal.description[0],
            meal_description=" ".join(meal.description[1:]),
        )

    formated_meal = "\n\n".join([meal_format(m) for m in meals])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=formated_meal,
        parse_mode=telegram.constants.ParseMode.HTML,  # type: ignore
    )

    logging.info(
        f"Sent menu for {mensa} to {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


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
        CommandHandler("mensa", mensa),
        CommandHandler("set", set_daily_mensa),
        CommandHandler("unset", unset_daily_mensa),
        CommandHandler("add", add_favorite_mensa),
        CommandHandler("remove", remove_favorite_mensa),
        CommandHandler("favorite", mensa_favorites),
        MessageHandler(filters.COMMAND, generic_command),
    ]

    application.add_handlers(handlers)

    application.run_polling()
