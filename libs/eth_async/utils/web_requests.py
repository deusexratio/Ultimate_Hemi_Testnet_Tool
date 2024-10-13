from curl_cffi.requests import AsyncSession
from libs.eth_async import exceptions


def aiohttp_params(params: dict[str, ...] | None) -> dict[str, str | int | float] | None:
    """
    Convert requests params to aiohttp params.

    Args:
        params (Optional[Dict[str, Any]]): requests params.

    Returns:
        Optional[Dict[str, Union[str, int, float]]]: aiohttp params.

    """
    new_params = params.copy()
    if not params:
        return

    for key, value in params.items():
        if value is None:
            del new_params[key]

        if isinstance(value, bool):
            new_params[key] = str(value).lower()

        elif isinstance(value, bytes):
            # print(value.hex())
            # new_params[key] = value.decode('utf-8')
            new_params[key] = value.hex()

    return new_params


async def async_get(url: str, headers: dict | None = None, **kwargs) -> dict | None:
    """
    Make a GET request and check if it was successful.

    Args:
        url (str): a URL.
        headers (Optional[dict]): the headers. (None)
        **kwargs: arguments for a GET request, e.g. 'params', 'headers', 'data' or 'json'.

    Returns:
        Optional[dict]: received dictionary in response.

    """
    try:
        async with AsyncSession() as session:
            response = await session.get(
                url=url,
                headers=headers,
                **kwargs,
                # params=params,
                # proxy=proxy_url
            )
            # print(response)
            status_code = response.status_code
            response = response.json()
            if status_code <= 201:
                return response
    except exceptions.HTTPException(response=response, status_code=status_code) as e:
        return e


async def async_post(url: str,
                     data: dict | str,
                     headers: dict | None = None,
                     proxy: str | None = None,
                     # params: dict | None = None,
                     **kwargs) -> dict | None:
    """
    Make a POST request and check if it was successful.

    Args:
        data: payload
        url (str): a URL.
        headers (Optional[dict]): the headers. (None)
        **kwargs: arguments for a GET request, e.g. 'params', 'headers', 'data' or 'json'.
        # params: params for request

    Returns:
        Optional[dict]: received dictionary in response.

    """
    # aio_params = aiohttp_params(params=params)
    # print(data)
    # print(type(data))
    async with AsyncSession() as session:
        if type(data) == str:
            response = await session.post(
                url=url,
                headers=headers,
                data=data,
                proxy=proxy,
                # params=aio_params,
                **kwargs

            )
        if type(data) == dict:
            response = await session.post(
                url=url,
                headers=headers,
                json=data,
                proxy=proxy,
                # params=aio_params,
                **kwargs
            )

        status_code = response.status_code
        response = response.json()
        # print(status_code, response)
        if status_code <= 201:
            return response
        raise exceptions.HTTPException(response=response, status_code=status_code)
