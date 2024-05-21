import telebot
import sqlite3
import telebot_calendar
from time import sleep
from telebot import types


bot = telebot.TeleBot('BOT_TOKEN')  # Создание переменной ссылки на бота 


calendar = telebot_calendar.Calendar(language=telebot_calendar.RUSSIAN_LANGUAGE)
calendar_1_callback = telebot_calendar.CallbackData("calendar_1", "action", "year", "month", "day")


# Функция для создания кнопок выбора года рождения
def create_year_change_markup(n):
    markup = types.InlineKeyboardMarkup()
    btns = []
    for i in range(2000 + n*12, 2013 + n*12):
        btns.append(types.InlineKeyboardButton(str(i), callback_data=f'year|{i}'))
    markup.add(btns[0], btns[1], btns[2], btns[3], btns[4], btns[5],
               btns[6], btns[7], btns[8], btns[9], btns[10], btns[11])
    markup.row(types.InlineKeyboardButton('<---', callback_data=f'change_year|{n-1}'),
               types.InlineKeyboardButton('--->', callback_data=f'change_year|{n+1}'))
    return markup


# Функция которая на вход получает число и складивает все его цифры между собой пока результат не будет < 23
def casting(num):
    if num <= 22:
        return num
    res = 0
    for i in str(num):
        res += int(i)
    return res if res <= 22 else casting(res)


# Функия которая расчитывает значения "матрицы судьбы"
def matrix_calculation(dob):

    dob = dob.split('.')

    arcans = {}
    arcans['А'] = casting(int(dob[0]))
    arcans['Б'] = casting(int(dob[1]))
    arcans['В'] = casting(int(dob[2]))
    arcans['Г'] = casting(arcans['А'] + arcans['Б'] + arcans['В'])
    arcans['Д'] = casting(arcans['А'] + arcans['Б'] + arcans['В'] + arcans['Г'])
    arcans['Л'] = casting(arcans['В'] + arcans['Д'])
    arcans['ПРЕДНАЗНАЧЕНИЕ'] = casting(casting(arcans['Б'] + arcans['Г']) + casting(arcans['А'] + arcans['В']))
    arcans['Б2'] = casting(arcans['Б'] + arcans['Д'])
    return arcans


# Функция которая достает данные из БД и создает из них сообщения для бота
def matrix_decoding(arcans, sex):
    db = sqlite3.connect('data/num_info.sql')
    cur = db.cursor()

    out_messages = []
    for key, value in arcans.items():
        out_message = ''
        cur.execute(f'SELECT значение FROM лайт WHERE позиция = "{key}"')
        pos = cur.fetchone()
        cur.execute(f'SELECT "{value}" FROM лайт WHERE позиция = "{key}"')
        res = cur.fetchone()
        if pos and res:
            if pos[0].find('|') == -1:
                out_message += pos[0]+'\n\n'+res[0]
            else:
                out_message += pos[0]+'\n\n'+res[0].split('|')[0 if sex == 'fem' else 1]
        if len(out_message) > 4095:
            out_messages.append(out_message[:4095])
            out_messages.append(out_message[4095:])
        elif len(out_message) > 0:
            out_messages.append(out_message)
    db.close()
    return out_messages


# Создает кнопки для того чтобы оставить отзыв о боте прямо в нем
def create_rating_markup(rate):
    markup = types.InlineKeyboardMarkup()
    btns = []
    for i in range(1, rate+1):
        btns.append(types.InlineKeyboardButton('❤️', callback_data=f'rate|rate {i}'))
    for i in range(rate+1, 6):
        btns.append(types.InlineKeyboardButton('🖤', callback_data=f'rate|rate {i}'))
    markup.row(btns[0], btns[1], btns[2], btns[3], btns[4])
    if rate != 0:
        markup.row(types.InlineKeyboardButton('Оценить', callback_data=f'rate|coliform {rate}'))
    
    return markup


# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton('Рассчитать'))
    bot.send_message(message.chat.id, 'Этот бот рассчитает вашу Матрицу Судьбы. Матрица Судьбы - это метод\
самопознания, который показывает характер человека, как его видят другие люди, его таланты.\n\
Нажмите "Рассчитать" чтобы продолжить.', reply_markup=markup)


def select_name(message, sex, dob):
    if message.text == 'Расчитать' or message.text == 'Оценить':
        menu(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('Рассчитать', callback_data=f'enter_info|y {dob} {sex}'),
                   types.InlineKeyboardButton('Изменить', callback_data='enter_info|n'))
        bot.send_message(message.chat.id, f'Ваши данные:\nИмя: {message.text}\nПол: {"мужской" if sex == "male" else "женский"}\nДата рождения: {dob}', reply_markup=markup)


def add_comment(message, rate):
    db = sqlite3.connect('data/rating.sql')
    cur = db.cursor()
    cur.execute(f'SELECT rate FROM rating WHERE telegram_id={message.chat.id}')
    if cur.fetchone() is None:
        cur.execute('INSERT INTO rating VALUES (?, ?, ?)', (message.chat.id, rate, message.text))
    else:
        cur.execute(f'UPDATE rating SET rate="{rate}", comment="{message.text}" WHERE telegram_id={message.chat.id}')
    db.commit()
    bot.send_message(message.chat.id, 'Отзыв сохранен, что бы его изменить можете снова нажать на кнопку "Оценить"')
    bot.send_message(5077725912, f'КОММЕНТАРИЙ {rate}/5\n{message.text}')
    cur.close()
    db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith('sex'))
def change_sex(call):
    params = call.data.split('|')[1].split()
    msg = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Введите имя.')
    bot.register_next_step_handler(msg, select_name, params[0], params[1])


@bot.callback_query_handler(func=lambda call: call.data.startswith('enter_info'))
def enter_info(call):
    params = call.data.split('|')[1].split()  # y/n, dob, sex
    if params[0] == 'y':
        arcans = matrix_calculation(params[1])
        out_messages = matrix_decoding(arcans, params[2])
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup.add(types.KeyboardButton('Рассчитать'), types.KeyboardButton('Оценить'))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Результаты:')
        for out_message in out_messages:
            bot.send_message(call.message.chat.id, str(out_message), parse_mode='HTML', reply_markup=markup)
            sleep(3)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text='Выберите дату рождения', reply_markup=create_year_change_markup(0))


# Несколько callback функций отвечающих за создание календаря
@bot.callback_query_handler(func=lambda call: call.data.startswith('change_year'))
def change_year(call):
    mod = call.data.split('|')[1]
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text='Выберите дату рождения', reply_markup=create_year_change_markup(int(mod)))


@bot.callback_query_handler(func=lambda call: call.data.startswith('year'))
def change_month(call):
    year = call.data.split('|')[1]
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton('Январь', callback_data=f'month|{year} 1'),
        types.InlineKeyboardButton('Февраль', callback_data=f'month|{year} 2'),
        types.InlineKeyboardButton('Март', callback_data=f'month|{year} 3'),
        types.InlineKeyboardButton('Апрель', callback_data=f'month|{year} 4'),
        types.InlineKeyboardButton('Май', callback_data=f'month|{year} 5'),
        types.InlineKeyboardButton('Июнь', callback_data=f'month|{year} 6'),
        types.InlineKeyboardButton('Июль', callback_data=f'month|{year} 7'),
        types.InlineKeyboardButton('Август', callback_data=f'month|{year} 8'),
        types.InlineKeyboardButton('Сентябрь', callback_data=f'month|{year} 9'),
        types.InlineKeyboardButton('Октябрь', callback_data=f'month|{year} 10'),
        types.InlineKeyboardButton('Ноябрь', callback_data=f'month|{year} 11'),
        types.InlineKeyboardButton('Декабрь', callback_data=f'month|{year} 12')
    )
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text='Выберите дату рождения', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('month'))
def change_day(call):
    date = call.data.split('|')[1]
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text='Выберите дату рождения', reply_markup=calendar.create_calendar(
                                                                                        name=calendar_1_callback.prefix,
                                                                                        year=int(date.split()[0]),
                                                                                        month=int(date.split()[1])))


# Обработка логики самого календаря
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(calendar_1_callback.prefix)
)
def calendar_f(call):

    # At this point, we are sure that this calendar is ours. So we cut the line by the separator of our calendar
    name, action, year, month, day = call.data.split(calendar_1_callback.sep)
    # Processing the calendar. Get either the date or None if the buttons are of a different type
    date = calendar.calendar_query_handler(
        bot=bot, call=call, name=name, action=action, year=year, month=month, day=day
    )
    # There are additional steps. Let's say if the date DAY is selected, you can execute your code. I sent a message.
    if action == "DAY":
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('Девушка', callback_data=f'sex|fem {date.strftime("%d.%m.%Y")}'),
                   types.InlineKeyboardButton('Мужчина', callback_data=f'sex|male {date.strftime("%d.%m.%Y")}'))
        bot.send_message(call.from_user.id, 'Выберите пол', reply_markup=markup)
    elif action == "CANCEL":
        bot.send_message(
            chat_id=call.from_user.id,
            text="Cancellation",
            reply_markup=types.ReplyKeyboardRemove(),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('rate'))
def rate(call):
    params = call.data.split('|')[1].split()
    if params[0] == 'rate':
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Оцените бота по шкале от 1 до 5', reply_markup=create_rating_markup(int(params[1])))
    if params[0] == 'coliform':
        msg = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Введите комментарий')
        bot.register_next_step_handler(msg, add_comment, params[1])


@bot.message_handler()
def menu(message):
    if message.text == 'Рассчитать':
        bot.send_message(message.chat.id, 'Выберите дату рождения', reply_markup=create_year_change_markup(0))
    elif message.text == 'Оценить':
        bot.send_message(message.chat.id, 'Оцените бота по шкале от 1 до 5', reply_markup=create_rating_markup(0))


bot.polling(none_stop=True)  # Запуск бота
