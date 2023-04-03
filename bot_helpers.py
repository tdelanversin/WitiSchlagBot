import numpy as np
import traceback
import html
import json
import logging
import pickle
from queue import Queue
from mensa import get_mensa, ETHMensa
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import NetworkError


DEVELOPER_CHAT_ID = 631157495
REACTION_EMOJIS = np.array([
    '🔥', '👍', '👎', '💩', '🥰', '😍', '❤️',  '😭', '🫡', '🤮', '❤️‍🔥', '🌭', 
    '😁', '🎉', '🐳', '🤯', '👏', '🤔', '🤬', '😱', '🤩', '😢', '🙏', '🕊', 
    '🤡', '🥱', '🥴', '🌚', '💯', '😂', '⚡️',  '🍌', '🏆', '💔', '🤨', '😐', 
    '🍓', '🍾', '💋', '🖕', '😈', '😴', '🤓', '👻', '👨‍💻', '👀', '🎃', '🙈', 
    '😇', '😨', '🤝', '✍️',  '🤗', '🎅', '🎄', '☃️',  '💅', '🤪', '🗿', '🆒', 
    '💘', '🙉', '🦄', '😘', '💊', '🙊', '😎', '👾', '🤷', '🤷‍♀️', '🤷‍♂️', '😡', 
])
IGNORED_ERRORS = [NetworkError]
ERRORS_TO_LOG = []


def meal_format(meal):
    return (
        f"{meal.label} "
        + f"<i>({meal.price_student}, "
        + f"{meal.price_staff}, "
        + f"{meal.price_extern})</i>\n"
        + f"<b>{meal.description[0]}</b>\n"
        + f"{' '.join(meal.description[1:])}"
    )

def mensa_format(mensa, meals):
    times = f" <i>{mensa.opening}-{mensa.closing}</i>" if isinstance(mensa, ETHMensa) else ""
    return (
        f"<b>{mensa.name}</b>{times}\n\n"
        + '\n\n'.join([meal_format(m) for m in meals])
    )


def format_favorites(chat_id, favorite_mensas):
    message = "Favorite mensas:\n\n"

    mensa_emojis = np.random.permutation(REACTION_EMOJIS)[:len(favorite_mensas[chat_id])]

    for emoji, mensa in zip(mensa_emojis, favorite_mensas[chat_id]):
        mensa = get_mensa(mensa)
        meals = mensa.get_meals()
        if len(meals) == 0:
            continue

        message += f"{emoji}{mensa_format(mensa, meals)}\n\n"

    return message


async def mensa_menu(mensa, update, context):
    mensa = get_mensa(mensa)
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
        text=mensa_format(mensa, meals), 
        parse_mode=ParseMode.HTML,
    )

    logging.info(
        f"Sent menu for {mensa} to {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
    )




async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    global ERRORS_TO_LOG

    if type(context.error) in IGNORED_ERRORS:
        logging.warning(f"Ignoring error or type: {type(context.error).__name__}")
        ERRORS_TO_LOG.append(f"Ignored error of type: {type(context.error).__name__}")
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


async def error_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != DEVELOPER_CHAT_ID:
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="The following errors occured:\n\n" + "\n".join(ERRORS_TO_LOG),
    )


def update_favorite_pickle(favorite_mensas):
    # pickle the favorite mensas
    with open("favorite_mensas.pickle", "wb") as f:
        pickle.dump(favorite_mensas, f)

def load_favorite_pickle():
    try:
        with open("favorite_mensas.pickle", "rb") as f:
            favorite_mensas = pickle.load(f)
        return favorite_mensas
    except (FileNotFoundError, EOFError):
        return {}
    

def update_messages_pickle(message_backlog):
    modified_message_backlog = {
        user: list(messages.queue) for user, messages in message_backlog.items()
    }
    with open("message_backlog.pickle", "wb") as f:
        pickle.dump(modified_message_backlog, f)


def load_messages_pickle(queue_size=100):
    try:
        with open("message_backlog.pickle", "rb") as f:
            modified_message_backlog = pickle.load(f)
        message_backlog = {
            user: Queue(maxsize=queue_size) for user in modified_message_backlog
        }
        [
            message_backlog[user].put(message) 
            for user, messages in modified_message_backlog.items()
            for _, message in zip(range(queue_size), messages)
        ]
        return message_backlog
    except (FileNotFoundError, EOFError):
        return {}
