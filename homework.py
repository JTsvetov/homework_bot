import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler
from typing import Dict, List, Union, Callable

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s, %(funcName)s, %(lineno)s, %(levelname)s, %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Псевдонимы типа
DictHomework = Dict[str, Union[int, str]]
DictHomeworks = List[DictHomework]
DictResponse = Dict[str, Union[DictHomeworks, int]]


class RequestAPIError(Exception):
    """Ошибка при запросе к эндпоинту API."""

    pass


class HTTPStatusError(Exception):
    """Ошибка доступа к API, код ответа не 200."""

    pass


class JSONParseError(Exception):
    """Ошибка при парсинге ответа из формата json."""

    pass


class ResponseAPIError(Exception):
    """Ошибка в ответе от сервера."""

    pass


class ResponseApiStatusUndocumented(Exception):
    """Недокументированный статус ответа от API."""

    pass


def send_message(bot, message: Callable[[DictHomework], str]) -> str:
    """Отправка сообщения в Telegram чат с TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в Telegram чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception as error:
        raise telegram.error.TelegramError(f'Ошибка при отправке сообщения в'
                                           f'Telegram чат, {error}')


def get_api_answer(current_timestamp: float) -> DictResponse:
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
    except requests.exceptions.RequestException as error:
        raise RequestAPIError(f'Ошибка при запросе к эндпоинту API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        raise HTTPStatusError(f'Ошибка доступа к API, код ответа:'
                              f'{status_code}')
    try:
        return homework_statuses.json()
    except JSONParseError as error:
        raise JSONParseError(f'Ошибка при парсинге ответа из формата json:'
                             f'{error}')


def check_response(response: Callable[[float], DictResponse]) -> DictHomeworks:
    """
    Проверка ответа API на корректность.

    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ,
    доступный в ответе API по ключу 'homeworks'.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    try:
        list_works = response['homeworks']
    except ResponseAPIError:
        raise ResponseAPIError('Ошибка доступа.'
                               'В ответе отсутствует ключ homeworks')
    if type(list_works) is not list:
        raise TypeError('Вывод по ключу homeworks не является списком')
    return list_works


def parse_status(homework: DictHomework) -> str:
    """Извлекает из информации о конкретной домашней работе ее статус.

    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря VERDICTS.
    """
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ homework_name')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in VERDICTS:
        raise ResponseApiStatusUndocumented(f'В ответа API обнаружен'
                                            f'недокументированный статус'
                                            f'работы: {homework_status}')
    verdict = VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверка доступности необходимых переменных окружения."""
    env_variables = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(env_variables):
        logger.info('Все обязательные переменные окружения обнаружены')
        return True
    logger.critical('Отсутствуют обязательные переменные окружения!')
    return False


def main() -> None:
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
                logger.info('В ответе отсутствуют новые статусы работ')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            now_error = f'Сбой в работе программы: {error}'
            logger.error(now_error)
            if previous_error != now_error:
                previous_error = now_error
                send_message(bot, now_error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
