# -*- coding: utf-8 -*-

from .adapters import CloudflareAdapter, DEFAULT_CIPHERS  # noqa
from .exceptions import CloudflareError, CloudflareCaptchaError  # noqa
from .api import request, get, head, post, patch, put, delete, options  # noqa

from .scraper import CloudflareScraper
from .utils import user_agents, DEFAULT_USER_AGENT, DEFAULT_HEADERS  # noqa

__version__ = "2.0.5"

create_scraper = CloudflareScraper.create_scraper
get_tokens = CloudflareScraper.get_tokens
get_cookie_string = CloudflareScraper.get_cookie_string
