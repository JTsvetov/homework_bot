import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(funcName)s, %(lineno)s, %(levelname)s, %(message)s',
    handlers=[StreamHandler(stream=sys.stdout)]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в Telegram чат с TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение в Telegram чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logging.error(
            'Ошибка отправки сообщения в Telegram чат {TELEGRAM_CHAT_ID}'
        )


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса.

    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        logging.error(f'Ошибка при запросе к эндпоинту API: {error}')
        raise Exception(f'Ошибка при запросе к эндпоинту API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logging.error(f'Ошибка доступа к API, код ответа: {status_code}')
        raise Exception(f'Ошибка доступа к API, код ответа: {status_code}')
    try:
        return homework_statuses.json()
    except ValueError:
        logging.error('Ошибка при парсинге ответа из формата json')
        raise ValueError('Ошибка при парсинге ответа из формата json')


def check_response(response):
    """
    Проверка ответа API на корректность.

    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ,
    доступный в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        raise TypeError('Ответ API не словарь')
    try:
        list_works = response['homeworks']
    except KeyError:
        logging.error('Ошибка доступа по ключу homeworks в словаре')
        raise KeyError('Ошибка доступа по ключу homeworks в словаре')
    if type(list_works) is not list:
        raise TypeError('Вывод по ключу homeworks не является списком')
    return list_works


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ее статус.

    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ homework_name')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'В ответа API обнаружен недокументированный статус '
                        f'домашней работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности необходимых переменных окружения."""
    env_variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for variable in env_variables:
        if variable is None:
            logging.critical('Отсутствуют обязательные переменные окружения!')
            return False
    logging.info('Все обязательные переменные окружения обнаружены')
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise Exception('Отсутствуют обязательные переменные окружения!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.info('В ответе отсутствуют новые статусы работ')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            now_error = f'Сбой в работе программы: {error}'
            logging.error(now_error)
            if previous_error != now_error:
                previous_error = now_error
                send_message(bot, now_error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
