import logging
from logging.handlers import RotatingFileHandler
import os
import requests
import time
from http import HTTPStatus

import telegram
from dotenv import load_dotenv

from exceptions import AvailabilityEnvironmentalVariables, NoHomeworkStatus, \
    NoHomeworks, APIGetErr, FailedSendingMessage

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


def check_tokens():
    """Проверяет требуемые токены."""
    return all(variable is None for variable in
               (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as err:
        raise FailedSendingMessage


def get_api_answer(timestamp):
    """Получает ответ с сервера."""
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS,
                            params=params)
    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        raise APIGetErr


def check_response(response):
    """Проверяет ответ сервера."""
    if not isinstance(response, dict):
        raise TypeError("Expected a dictionary")
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError("Expected a list")
    try:
        return homeworks[0]
    except IndexError:
        raise NoHomeworks("No homework found")


def parse_status(homework):
    """Обрабатывает ответ сервера."""
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
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s [%(levelname)s] %(message)s.'
                               'Функция: %(funcName)s')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler('homework_logs.log', maxBytes=50000000,
                                  backupCount=5, encoding='utf-8')
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s. Функция: %(funcName)s'))
    logger.addHandler(handler)

    if not check_tokens():
        raise AvailabilityEnvironmentalVariables(
            'Одна или несколько переменных окружения недоступны!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)

            send_message(bot, message)
            logger.info(homework)
            timestamp = response.get('current_date')
        except APIGetErr:
            logger.error('Ошибка при получении данных с сервера')
        except AvailabilityEnvironmentalVariables:
            logger.critical(
                'Одна или несколько переменных окружения недоступны!')
        except NoHomeworks:
            logger.info('Статус работ не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.info(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
