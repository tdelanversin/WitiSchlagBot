import logging
from queue import Queue
import openai

from bot_helpers import (
    load_messages_pickle,
    update_messages_pickle,
    error_handler,
    error_log,
)

from telegram import (
    Update,
    Message,
)
from telegram.constants import ParseMode
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)

DEVELOPER_CHAT_ID = 631157495
MESSAGE_BACKLOG = {}
BACKLOG_LENGTH = 500
APPROVED_CHATS = [631157495]
PRINT_LIMIT = 10


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="bot.log",
    filemode="w",
)


async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MESSAGE_BACKLOG
    if update.effective_chat.id != DEVELOPER_CHAT_ID:
        return

    MESSAGE_BACKLOG = load_messages_pickle()

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Reloaded message backlog"
    )

    logging.info("Reloaded message backlog")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id in MESSAGE_BACKLOG:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="I'm already listening to this chat."
        )
        return

    backlog_length = BACKLOG_LENGTH
    if context.args:
        backlog_length = int(context.args[0])

    MESSAGE_BACKLOG[update.effective_chat.id] = Queue(maxsize=backlog_length)
    update_messages_pickle(MESSAGE_BACKLOG)

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
    update_messages_pickle(MESSAGE_BACKLOG)

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
        else update.effective_user.name
    )
    backlog.put((user, update.effective_message.text))
    logging.info(MESSAGE_BACKLOG[update.effective_chat.id].queue)
    update_messages_pickle(MESSAGE_BACKLOG)

    logging.info(
        f"Added message to backlog of {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MESSAGE_BACKLOG[update.effective_chat.id].queue.clear()
    update_messages_pickle(MESSAGE_BACKLOG)
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Cleared backlog."
    )
    logging.info(
        f"Cleared backlog of {update.effective_chat.title}"
        + f"with id {update.effective_chat.id}"
    )


async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in APPROVED_CHATS:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are not allowed to use this command.",
        )

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

        chat = [
            {
                "role": "system",
                "content": "You are a summarizer bot. You summarize any chat conversation that you are given",
            },
            {"role": "user", "content": format_backlog(backlog)},
        ]

        # USES MORE TOKENS
        # ] + [
        #     {'role': 'user', 'content': f'{user}: {message}'}
        #     for user, message in list(backlog.queue)
        # ]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=chat,
        )

        finish_reason = response["choices"][0]["finish_reason"]  # type: ignore
        usage = response["usage"]  # type: ignore
        summary = response["choices"][0]["message"]["content"]  # type: ignore

        logging.info(
            f"Finished summarizing with reason: {finish_reason}"
            + f" and a usage of {usage}"
        )

        if finish_reason == "stop":  # type: ignore
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"<b>Here is the summary of the last <i>{backlog.qsize()}</i> messages in {update.effective_chat.title}:</b>\n\n"
                + f"{summary}",  # type: ignore
                parse_mode=ParseMode.HTML,
            )
        elif finish_reason == "length":  # type: ignore
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="I couldn't generate a summary because the chat was too long.",
            )
        elif finish_reason == "content_filter":  # type: ignore
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="I couldn't generate a summary because the chat contained sensitive content.",
            )

    await context.bot.delete_message(
        update.effective_chat.id, update.effective_message.id
    )

    logging.info(
        f"Sent summary to <{update.effective_user.name}> "
        + f"with id {update.effective_user.id}"
    )


async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(
        f"Received message from {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}, "
        + f"sent by {update.effective_user.name} "
        + f"with id {update.effective_user.id}"
    )


def format_backlog(backlog: Queue):
    return "\n".join([f"{name}: {message}" for name, message in list(backlog.queue)])


class ListeningTo(filters.MessageFilter):
    def filter(self, message: Message):
        return message.chat_id in MESSAGE_BACKLOG


listening_to_filter = ListeningTo()


if __name__ == "__main__":
    with open("TOKEN.token") as f:
        token = f.readlines()[0]
    with open("OPENAI.token") as f:
        openai.api_key = f.readlines()[0]

    application = ApplicationBuilder().token(token).build()

    commands = (
        "start - Start listening to a chat\n"
        "stop - Stop listening to a chat\n"
        "backlog - Show the backlog of a chat\n"
        "summarize - Summarize the backlog of a chat\n"
        "clear - Clear the backlog of a chat\n"
    )

    logging.info(f"Registered commands:\n{commands}")

    handlers = [
        CommandHandler("reload", reload),
        CommandHandler("log", error_log),
        CommandHandler("start", start),
        CommandHandler("stop", stop, filters=listening_to_filter),
        CommandHandler("backlog", show_backlog, filters=listening_to_filter),
        CommandHandler("summarize", summarize, filters=listening_to_filter),
        CommandHandler("clear", clear, filters=listening_to_filter),
        MessageHandler(filters.TEXT & ~(filters.COMMAND) & listening_to_filter, log),
        MessageHandler(filters.ALL, catch_all),
    ]

    application.add_handlers(handlers)
    application.add_error_handler(error_handler)

    application.run_polling()
