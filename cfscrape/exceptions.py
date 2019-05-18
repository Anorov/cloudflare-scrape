# -*- coding: utf-8 -*-

from requests.exceptions import RequestException


class CloudflareError(RequestException):
    pass


class CloudflareCaptchaError(CloudflareError):
    pass
