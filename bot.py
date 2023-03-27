import logging
from queue import Queue
import pyMensa
from datetime import time, timedelta
import telegram
from telegram import (
    Update,
    Message,
)
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)

SIMPLIFY = True

if not SIMPLIFY:
    from transformers import pipeline  # type: ignore

    summarizer = pipeline("summarization", model="philschmid/bart-large-cnn-samsum")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

MESSAGE_BACKLOG = {}
BACKLOG_LENGTH = 100
PRINT_LIMIT = 10
MENSAS = {
    "poly",
    "foodlab",
    "clausius",
    "polysnack",
    "foodtrailer",
    "bellavista",
    "fusion",
    "gess",
    "tanne",
    "dozentenfoyer",
    "platte",
    "raemi",
    "mercato",
    "uni",
    "lichthof",
    "irchel",
    "atrium",
    "binzmuehle",
    "cityport",
    "zahnmedizin",
    "tierspital",
    "botanischergarten",
}
FAVORITE_MENSAS = {
    "poly",
    "clausius",
    "uni",
}
MEAL_FORMAT = """{label} <i>({price_student}, {price_staff}, {price_extern})</i>
<b>{meal_name}</b>
{meal_description}"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SIMPLIFY:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I'm sorry, but I'm not working right now. "
            + "I'm currently being rewritten to be simpler and more efficient. "
            + "I'll be back soon!",
        )
        return

    if update.effective_chat.id in MESSAGE_BACKLOG:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="I'm already listening to this chat."
        )
        return

    backlog_length = BACKLOG_LENGTH
    if context.args:
        backlog_length = int(context.args[0])

    MESSAGE_BACKLOG[update.effective_chat.id] = Queue(maxsize=backlog_length)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I will now start listening to this chat. "
        + f"I will save the last {backlog_length} "
        + "messages and will summarize them to you if you ask me to.",
    )

    logging.info(
        f"Started listening to <{update.effective_chat.title}> "
        + f"with id {update.effective_chat.id} "
        + f"and backlog length {backlog_length}"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MESSAGE_BACKLOG.pop(update.effective_chat.id)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="I will no longer listen to this chat."
    )

    logging.info(
        f"Stopped listening to <{update.effective_chat.title}> "
        + f"with id {update.effective_chat.id}"
    )


async def show_backlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    backlog = MESSAGE_BACKLOG[update.effective_chat.id]
    if backlog.empty():
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="I haven't seen any messages yet."
        )
    elif backlog.qsize() < PRINT_LIMIT:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Here's what I've seen so far:\n{format_backlog(backlog)}",
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Here's what I've seen so far:\n...\n{format_backlog(backlog[-PRINT_LIMIT:])}",
        )

    logging.info(
        f"Sent backlog to {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    backlog = MESSAGE_BACKLOG[update.effective_chat.id]
    if backlog.full():
        backlog.get()

    user = (
        update.effective_message.forward_from.name
        if update.effective_message.forward_from is not None
        else update.effective_user
    )
    backlog.put((user, update.effective_message.text))

    logging.info(
        f"Added message to backlog of {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MESSAGE_BACKLOG[update.effective_chat.id].queue.clear()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Cleared backlog."
    )
    logging.info(
        f"Cleared backlog of {update.effective_chat.title}"
        + f"with id {update.effective_chat.id}"
    )


async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):


    backlog = MESSAGE_BACKLOG[update.effective_chat.id]
    logging.info(
        f"Summarizing {update.effective_chat.title}"
        + f"with id {update.effective_chat.id}"
    )

    if backlog.empty():
        await context.bot.send_message(
            chat_id=update.effective_user.id, text="I haven't seen any messages yet."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id, text="Generating summary..."
        )

        input_text = format_backlog(backlog)
        summary = summarizer(input_text, max_length=142, min_length=20, do_sample=False)

        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=f"Here is the summary of the last {len(backlog)} messages in {update.effective_chat.title}:\n"
            + f"{summary[0]['summary_text']}",  # type: ignore
        )

    await context.bot.delete_message(
        update.effective_chat.id, update.effective_message.id
    )

    logging.info(
        f"Sent summary to <{update.effective_user.name}> "
        + f"with id {update.effective_user.id}"
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
    if update.effective_message.text[1:] in MENSAS:  # type: ignore
        await mensa_menu(update.effective_message.text[1:], update, context)
        return
    logging.info(
        f"Received command {update.effective_message.text} "
        + f"from {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


async def favorite_mensa(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    message = "Favotire mensas:\n\n"
    for mensa in FAVORITE_MENSAS:
        meals = pyMensa.get_meals(mensa)
        if len(meals) == 0:
            continue
            
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
        message += f"          <b><i>{mensa.upper()}</i></b>:\n\n{formated_meal}\n\n"

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=message,
        parse_mode=telegram.constants.ParseMode.HTML,  # type: ignore
    )

    logging.info(f"Sent favorite mensas to chat with id {job.chat_id}")


async def set_dayly_mensa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_message.chat_id
    if context.job_queue.get_jobs_by_name(str(chat_id)):
        await update.effective_message.reply_text(
            "You already have an active dayly mensa job!"
        )
        return

    context.job_queue.run_daily(
        favorite_mensa,
        time=time(10),
        days=(1, 2, 3, 4, 5),
        chat_id=chat_id,
        name=str(chat_id),
    )
    await update.effective_message.reply_text("Successfully set dayly mensa job for favorite mensas!")

    logging.info(
        f"Set dayly mensa job for {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def unset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not current_jobs:
        await update.message.reply_text("You have no active dayly mensa job!")
        return
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("Successfully unset dayly mensa job!")

    logging.info(
        f"Unset dayly mensa job for {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def mensa_menu(mensa, update, context):
    meals = pyMensa.get_meals(mensa)
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


async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(
        f"Received message from {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}, "
        + f"sent by {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


def format_backlog(backlog: Queue):
    return "\n".join(
        [f"{name.name}: {message}" for name, message in list(backlog.queue)]
    )


class ListeningTo(filters.MessageFilter):
    def filter(self, message: Message):
        return message.chat_id in MESSAGE_BACKLOG


listening_to_filter = ListeningTo()


if __name__ == "__main__":
    with open("TOKEN.token") as f:
        token = f.readlines()[0]
    application = ApplicationBuilder().token(token).build()

    handlers = [
        CommandHandler("start", start),
        CommandHandler("stop", stop, filters=listening_to_filter),
        CommandHandler("backlog", show_backlog, filters=listening_to_filter),
        CommandHandler("summarize", summarize, filters=listening_to_filter),
        CommandHandler("clear", clear, filters=listening_to_filter),
        CommandHandler("mensa", mensa),
        CommandHandler("set", set_dayly_mensa),
        CommandHandler("unset", unset),
        MessageHandler(filters.COMMAND, generic_command),
        MessageHandler(filters.TEXT & ~(filters.COMMAND) & listening_to_filter, log),
        MessageHandler(filters.ALL, catch_all),
    ]

    application.add_handlers(handlers)

    application.run_polling()
