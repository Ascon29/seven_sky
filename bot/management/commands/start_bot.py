import os
from telegram import InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, ChatMemberHandler, ConversationHandler
from telegram.ext import MessageHandler, Filters, InlineQueryHandler
from django.core.management import BaseCommand

RATE, HOURS, SALES = range(3)


class Command(BaseCommand):
    help = 'Начинает работу телеграм бота'

    user_rate = 0
    user_hours = 0
    user_sales = 0

    def handle(self, *args, **kwargs):
        updater = Updater(os.getenv('TG_BOT_TOKEN'), use_context=True)
        dispatcher = updater.dispatcher

        def start(update, _):
            user = update.message.from_user
            reply_keyboard = [['Официант', 'Старший официант']]
            markup_key = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
            update.message.reply_text(f'Привет {user.first_name}.\nКто ты? (от ответа зависит почасовая ставка)',
                                      reply_markup=markup_key, )
            return RATE

        def rate(update, _):
            user_job_title = update.message.text
            self.user_rate = 90 if user_job_title == 'Официант' else 100
            update.message.reply_text('Сколько часов ты отработал?',
                                      reply_markup=ReplyKeyboardRemove())
            return HOURS

        def hours(update, _):
            self.user_hours = int(update.message.text)
            update.message.reply_text('Сколько у тебя продаж?')
            return SALES

        def sales(update, _):
            self.user_sales = int(update.message.text)
            sales_percent = 0.03 if self.user_sales >= 450000 else 0.02
            total = round(self.user_rate * self.user_hours + self.user_sales * sales_percent)
            if total < 40000:
                reaction = 'Ну, не расстраивайся, ты все равно умничка❤️'
            elif total >= 50000:
                reaction = 'Отличная работа!💪'

            text = f'Твоя зарплата без учета общего процента и вычетов:\n{str(total)} рублей.\n{reaction}'
            update.message.reply_text(text)
            return ConversationHandler.END

        def cancel(update, _):
            update.message.reply_text(
                'Мое дело предложить - Ваше отказаться'
                ' Будет скучно - пиши.',
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        def echo(update, context):
            user = update.message.from_user.username
            request = update.message.text
            if 'терпила' in request.lower():
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f"@{user} Уволен!")

        # функция обработки встроенного запроса
        def inline_echo(update, context):
            query = update.inline_query.query
            if not query:
                return
            results = list()
            results.append(
                InlineQueryResultArticle(
                    id=query,
                    title='Посчитать зарплату',
                    input_message_content=InputTextMessageContent(query)
                )
            )
            context.bot.answer_inline_query(update.inline_query.id, results)

        # функция входа пользователя в чат
        def welcome(update, context):
            new_member = update.message.new_chat_members
            for member in new_member:
                update.message.reply_text(f"Приветствуем нового терпилу @{member.first_name}!")

        # функция выхода пользователя из чата
        def goodbye(update, context):
            left_member = update.message.left_chat_member
            update.message.reply_text(f"@{left_member.first_name} больше не терпила(((")

        # функция обработки не распознанных команд
        def unknown(update, context):
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Я не знаю такую команду :(")

        # обработчик входа пользователя в чат
        welcome_handler = MessageHandler(Filters.status_update.new_chat_members, welcome)
        dispatcher.add_handler(welcome_handler)

        # обработчик выхода пользователя из чата
        goodbye_handler = MessageHandler(Filters.status_update.left_chat_member, goodbye)
        dispatcher.add_handler(goodbye_handler)

        # обработчик команды '/start'. Начинает диалог
        conv_handler = ConversationHandler(entry_points=[CommandHandler('start', start, Filters.chat_type.private)],
                                           states={
                                               RATE: [MessageHandler(Filters.regex('^(Официант|Старший официант)$'),
                                                                     rate)],
                                               HOURS: [MessageHandler(Filters.text & ~Filters.command, hours)],
                                               SALES: [MessageHandler(Filters.text & ~Filters.command, sales)]
                                           },
                                           fallbacks=[CommandHandler('cancel', cancel)])
        dispatcher.add_handler(conv_handler)

        # обработчик текстовых сообщений
        echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
        dispatcher.add_handler(echo_handler)

        # обработчик встроенных запросов
        inline_echo_handler = InlineQueryHandler(inline_echo)
        dispatcher.add_handler(inline_echo_handler)

        # обработчик не распознанных команд
        unknown_handler = MessageHandler(Filters.command, unknown)
        dispatcher.add_handler(unknown_handler)

        # запуск прослушивания сообщений
        updater.start_polling()
        # обработчик нажатия Ctrl+C
        updater.idle()
