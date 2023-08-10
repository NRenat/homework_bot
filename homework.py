import logging
import os
import requests
import time

import telegram
from dotenv import load_dotenv

from exceptions import AvailabilityEnvironmentalVariables, NoHomeworkStatus, \
    NoHomeworks, APIGetErr

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

ENV_VARIABLES = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

current_status = ''

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s')


def check_tokens():
    """Проверяет требуемые токены."""
    if (TELEGRAM_TOKEN or TELEGRAM_CHAT_ID or PRACTICUM_TOKEN) is None:
        logging.critical('Одна или несколько переменных окружения недоступны!')
        raise AvailabilityEnvironmentalVariables(
            'Одна или несколько переменных окружения недоступны!')


def send_message(bot, message):
    """Отправляет сообщение пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except Exception as err:
        logging.error(f'Сбой отправки сообщения: {message}. Ошибка: {err}')


def get_api_answer(timestamp):
    """Получает ответ с сервера."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise APIGetErr

    except requests.RequestException as ex:
        logging.error(ex)


def check_response(response):
    """Проверяет ответ сервера."""
    if type(response) != dict:
        raise TypeError
    homeworks = response.get('homeworks')
    if type(homeworks) != list:
        raise TypeError
    try:
        return homeworks[0]
    except IndexError:
        raise NoHomeworks


def parse_status(homework):
    """Обрабатывает ответ сервера."""
    global current_status
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise NoHomeworks
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise NoHomeworkStatus
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            logging.info(homework)
            timestamp = response.get('current_date')
        except APIGetErr:
            logging.error('Ошибка при получении данных с сервера')
        except AvailabilityEnvironmentalVariables:
            logging.critical(
                'Одна или несколько переменных окружения недоступны!')
        except NoHomeworks:
            logging.info('Статус работ не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.info(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
