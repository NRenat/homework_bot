import logging
import sys
from logging.handlers import RotatingFileHandler
import os
import requests
import time
from http import HTTPStatus

import telegram
from dotenv import load_dotenv

from exceptions import NoHomeworkStatus, NoHomeworks, APIGetErr, \
    FailedSendingMessage

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

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s '
                           'Функция: %(funcName)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('homework_logs.log', maxBytes=50000000,
                              backupCount=5, encoding='utf-8')
handler.setFormatter(
    logging.Formatter((
        '%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] '
        '%(message)s Функция: %(funcName)s')))
logger.addHandler(handler)


def check_tokens():
    """Проверяет требуемые токены."""
    if all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.critical('Одна или несколько переменных окружения недоступны!')
        return True
    else:
        return False


def send_message(bot, message):
    """Отправляет сообщение пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: {message}')

    except Exception as err:
        raise FailedSendingMessage(
            f'Сбой отправки сообщения: {message}. Ошибка: {err}')


def get_api_answer(timestamp):
    """Получает ответ с сервера."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params)
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            logger.error('Ошибка при получении данных с сервера')
            raise APIGetErr

    except requests.RequestException as ex:
        raise ConnectionError('ConnectionError') from ex


def check_response(response):
    """Проверяет ответ сервера."""
    if type(response) != dict:
        raise TypeError
    homeworks = response.get('homeworks')

    if homeworks is None:
        raise KeyError('homeworks not in response!')

    if type(homeworks) != list:
        raise TypeError('Получен неверный тип данных.')
    try:
        return homeworks[0]
    except IndexError:
        raise NoHomeworks('Статус работ не изменился.')


def parse_status(homework):
    """Обрабатывает ответ сервера."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise NoHomeworks('Статус работ не изменился.')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise NoHomeworkStatus('Статус работы не получен!')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_message_repeats(bot, message, last_message):
    """Проверяет, было ли отправлено идентичное сообщение перед текущим."""
    if last_message == message:
        logger.info(
            'Полученное сообщение идентично предыдущему. Пропуск сообщения!')
        return last_message

    send_message(bot, message)
    last_message = message
    return last_message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Одна или несколько переменных окружения недоступны!')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            last_message = check_message_repeats(bot, message, last_message)
            timestamp = response.get('current_date')

        except FailedSendingMessage as ex:
            logger.error(ex)

        except Exception as ex:
            exception_name = type(ex).__name__
            error_message = str(ex)
            message = str(f'{exception_name} - {error_message}')
            last_message = check_message_repeats(bot, message, last_message)
            logger.error(ex)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
