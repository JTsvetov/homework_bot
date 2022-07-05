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
