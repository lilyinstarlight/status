import json

import httpx


__all__ = ['check']


status_map = {
    'ok': 'up',
    'pending': 'up',
    'alerting': 'down',
    'paused': 'maintenance',
    'no_data': 'unknown',
}


class BearerAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        request.headers['Authorization'] = f'Bearer {self.token}'
        yield request


def check(api_base, api_key, services):
    statuses = {}

    for service, info in services.items():
        try:
            statuses[service] = status_map[httpx.get(f'{api_base}/alerts/{info["id"]}', auth=BearerAuth(api_key)).json()['State']]
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            statuses[service] = 'unknown'

    return statuses
