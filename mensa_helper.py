import logging
import pickle
from mensa import get_meals
from telegram.constants import ParseMode


def meal_format(meal):
    return (
        f"{meal.label} "
        + f"<i>({meal.price_student}, "
        + f"{meal.price_staff}, "
        + f"{meal.price_extern})</i>\n"
        + f"<b>{meal.description[0]}</b>\n"
        + f"{' '.join(meal.description[1:])}"
    )


def format_favorites(chat_id, favorite_mensas):
    message = "Favorite mensas:\n\n"

    for mensa in favorite_mensas[chat_id]:
        meals = get_meals(mensa)
        if len(meals) == 0:
            continue

        formated_meal = "\n\n".join([meal_format(m) for m in meals])
        message += f"          <b><i>{mensa.upper()}</i></b>:\n\n{formated_meal}\n\n"

    return message


async def mensa_menu(mensa, update, context):
    meals = get_meals(mensa)
    if len(meals) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I couldn't find a menu for today. Please try again tomorrow.",
        )
        logging.info(
            f"Couldn't find a menu for {mensa} today "
            + f"for {update.effective_chat.title} "
            + f"with id {update.effective_chat.id}"
        )
        return

    formated_meal = "\n\n".join([meal_format(m) for m in meals])

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=formated_meal, parse_mode=ParseMode.HTML
    )

    logging.info(
        f"Sent menu for {mensa} to {update.effective_chat.title} "
        + f"with id {update.effective_chat.id}"
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
    except FileNotFoundError:
        return {}