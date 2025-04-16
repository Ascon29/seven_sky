import logging
import random
from datetime import datetime, timedelta

from django.core.management import BaseCommand
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

from config import settings
from static import word_lists

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

tomorrow = datetime.today() + timedelta(days=1)
RATE, HOURS, SALES_OF, SALES_BAR, SALES_ADMIN, BAR_ZP = range(6)


class Command(BaseCommand):
    help = "Начинает работу телеграм бота"

    user_name = ''
    user_job_title = ""
    user_rate = 0
    user_hours = 0
    user_sales = 0
    admin_sales_percent = 0.003
    barmen_sales_percent = 0.015
    barmen_count = 0

    def handle(self, *args, **kwargs):
        updater = Updater(settings.TG_BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        jq = updater.job_queue

        def start(update, _):
            self.user_name = update.message.from_user.username
            logger.info("%s - Начал разговор", self.user_name)
            inline_keyboard = [
                [
                    InlineKeyboardButton("Официант", callback_data="официант 90"),
                    InlineKeyboardButton("Старший официант", callback_data="старший_официант 100"),
                ],
                [
                    InlineKeyboardButton("Бармен", callback_data="бармен 100"),
                    InlineKeyboardButton("Администратор", callback_data="админ 150"),
                ],
            ]
            markup_key = InlineKeyboardMarkup(inline_keyboard, one_time_keyboard=True)
            update.message.reply_text(
                f"Привет {self.user_name}, меня зовут Ая.\nЯ могу посчитать твою зарплату.\nДля начала выбери свою должность.\n\nДля отмены введи /cancel",
                reply_markup=markup_key,
            )
            return RATE

        # функция сохранения почасовой ставки
        def rate(update, _):
            query = update.callback_query
            query.answer()
            result = query.data.split(" ")
            self.user_job_title = result[0]
            self.user_rate = int(result[1])
            logger.info("%s - Должность: %s, Ставка: %s", self.user_name, self.user_job_title, self.user_rate)
            query.message.reply_text("Сколько часов ты отработал?")
            return HOURS

        # функция сохранения отработанных часов
        def hours(update, _):
            self.user_hours = int(update.message.text)
            logger.info("%s - Часы: %s", self.user_name, self.user_hours)
            if self.user_job_title == "бармен":
                update.message.reply_text("Сколько общая выручка заведения?")
                return SALES_BAR
            elif self.user_job_title == "официант" or self.user_job_title == "старший_официант":
                update.message.reply_text("Сколько у тебя продаж?")
                return SALES_OF
            elif self.user_job_title == "админ" or self.user_job_title:
                update.message.reply_text("Сколько общая выручка заведения?")
                return SALES_ADMIN

        # функция сохранения продаж и окончательного подсчета зарплаты официанта
        def sales_of(update, _):
            self.user_sales = int(update.message.text)
            sales_percent = 0.03 if self.user_sales >= 450000 else 0.02
            total = round(self.user_rate * self.user_hours + self.user_sales * sales_percent)
            logger.info("%s - Продажи: %s, Зарплата: %s", self.user_name, self.user_sales, total)
            if total < 40000:
                reaction = "Ну, не расстраивайся, ты все равно умничка❤️"
            elif total >= 50000:
                reaction = "Отличная работа!💪"
            else:
                reaction = "Надеюсь, ты доволен🥰"
            text = f"Твоя зарплата без учета общего процента и вычетов:\n{str(total)} рублей.\n{reaction}"

            update.message.reply_text(text)
            return ConversationHandler.END

        # функция сохранения продаж и окончательного подсчета зарплаты админа
        def sales_admin(update, _):
            self.user_sales = int(update.message.text)
            total = round(self.user_rate * self.user_hours + self.user_sales * self.admin_sales_percent)
            logger.info("%s - Продажи: %s, Зарплата: %s", self.user_name, self.user_sales, total)
            text = f"К сожалению, я пока не знаю точную формулу подсчета у администратора, поэтому могу сказать только примерную сумму. Прошу меня простить😔\nТвоя зарплата без учета вычетов:\n{str(total)} рублей."
            update.message.reply_text(text)
            return ConversationHandler.END

        # функция сохранения продаж
        def sales_bar(update, _):
            self.user_sales = int(update.message.text)
            logger.info("%s - Бармены в штате: %s", self.user_name, self.user_sales)
            update.message.reply_text("Сколько барменов в штате?")
            return BAR_ZP

        # функция сохранения количества барменов в штате и окончательного подсчета зарплаты бармена
        def bar_zp(update, _):
            self.barmen_count = int(update.message.text)
            total = round(
                self.user_rate * self.user_hours + (self.user_sales * self.barmen_sales_percent) / self.barmen_count
            )
            logger.info("%s - Продажи: %s, Зарплата: %s", self.user_name, self.user_sales, total)
            text = f"К сожалению, я пока не знаю точную формулу подсчета у бармена, поэтому могу сказать только примерную сумму. Прошу меня простить😔\nТвоя зарплата без учета вычетов:\n{str(total)} рублей."
            update.message.reply_text(text)
            return ConversationHandler.END

        # функция остановки диалога
        def cancel(update, _):
            logger.info("%s - Отменил разговор", self.user_name)
            update.message.reply_text("Мое дело предложить - Ваше отказаться" " Будет скучно - пиши.")
            return ConversationHandler.END

        # функция обработки текстового запроса
        def echo(update, context):
            user = update.message.from_user.username
            text_request = update.message.text
            for word in word_lists.triggered_words:
                if word in text_request.lower():
                    context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user} Уволен!")
                    break

            for abusive in word_lists.abusive_words:
                if abusive in text_request.lower():
                    logger.info("Матершинник: %s", user)
                    context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{user}, фу, матершинник!")
                    break

        # функция обработки запроса с изображением
        def get_photo(update, context):
            # file_id = update.message.photo[-1].file_id
            # new_file = context.bot.get_file(file_id)
            # new_file.download()
            pass

        # функция обработки запроса с кружочками
        def video_note(update, context):
            text = random.choice(word_lists.replicas)
            update.message.reply_text(text)

        # функция входа пользователя в чат
        def welcome(update, _):
            new_member = update.message.new_chat_members
            for member in new_member:
                update.message.reply_text(f"Приветствуем нового терпилу @{member.first_name}!")

        # функция выхода пользователя из чата
        def goodbye(update, _):
            left_member = update.message.left_chat_member
            update.message.reply_text(f"@{left_member.first_name} больше не терпила(((")

        # функция отложенной ежедневной задачи
        def callback_daily(context: CallbackContext):
            text = random.choice(word_lists.hello)
            context.bot.send_message(chat_id=settings.TG_CHAT_ID, text=text)

        jq.run_daily(callback_daily, time=datetime(tomorrow.year, tomorrow.month, 15, 6, 13))

        # функция обработки не распознанных команд
        def unknown(update, context):
            context.bot.send_message(chat_id=update.effective_chat.id, text="Я не знаю такую команду :(")

        # обработчик входа пользователя в чат
        welcome_handler = MessageHandler(Filters.status_update.new_chat_members, welcome)
        dispatcher.add_handler(welcome_handler)

        # обработчик выхода пользователя из чата
        goodbye_handler = MessageHandler(Filters.status_update.left_chat_member, goodbye)
        dispatcher.add_handler(goodbye_handler)

        # обработчик команды '/start'. Начинает диалог
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start, Filters.chat_type.private)],
            states={
                RATE: [CallbackQueryHandler(rate)],
                HOURS: [MessageHandler(Filters.regex("^\d{1,3}$") & ~Filters.command, hours)],
                SALES_OF: [MessageHandler(Filters.regex("^\d{1,7}$") & ~Filters.command, sales_of)],
                SALES_BAR: [MessageHandler(Filters.regex("^\d{1,8}$") & ~Filters.command, sales_bar)],
                SALES_ADMIN: [MessageHandler(Filters.regex("^\d{1,8}$") & ~Filters.command, sales_admin)],
                BAR_ZP: [MessageHandler(Filters.regex("^\d{1,2}$") & ~Filters.command, bar_zp)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        dispatcher.add_handler(conv_handler)

        # обработчик текстовых сообщений
        echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
        dispatcher.add_handler(echo_handler)

        # обработчик сообщений с изображением
        photo_handler = MessageHandler(Filters.photo & (~Filters.command), get_photo)
        dispatcher.add_handler(photo_handler)

        # обработчик сообщений с кружочками
        video_note_handler = MessageHandler(Filters.video_note & (~Filters.command), video_note)
        dispatcher.add_handler(video_note_handler)

        # обработчик не распознанных команд
        unknown_handler = MessageHandler(Filters.command, unknown)
        dispatcher.add_handler(unknown_handler)

        # запуск прослушивания сообщений
        updater.start_polling()
        # обработчик нажатия Ctrl+C
        updater.idle()
