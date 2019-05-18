# -*- coding: utf-8 -*-

import json
import logging
import random
import re
import ssl
import subprocess
import copy
import time
import os
from base64 import b64encode
from collections import OrderedDict

from requests.sessions import Session
from requests.adapters import HTTPAdapter
from requests.compat import urlparse, urlunparse
from requests.exceptions import RequestException

from urllib3.util.ssl_ import create_urllib3_context, DEFAULT_CIPHERS

__version__ = "2.0.5"

USER_AGENTS_PATH = os.path.join(os.path.dirname(__file__), "user_agents.json")

with open(USER_AGENTS_PATH) as f:
    user_agents = json.load(f)

DEFAULT_USER_AGENT = random.choice(user_agents)

DEFAULT_HEADERS = OrderedDict(
    (
        ("Host", None),
        ("Connection", "keep-alive"),
        ("Upgrade-Insecure-Requests", "1"),
        ("User-Agent", DEFAULT_USER_AGENT),
        (
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        ),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("Accept-Encoding", "gzip, deflate"),
    )
)

BUG_REPORT = """\
Cloudflare may have changed their technique, or there may be a bug in the script.

Please read https://github.com/Anorov/cloudflare-scrape#updates, then file a \
bug report at https://github.com/Anorov/cloudflare-scrape/issues."\
"""

ANSWER_ACCEPT_ERROR = """\
The challenge answer was not properly accepted by Cloudflare. This can occur if \
the target website is under heavy load, or if Cloudflare is experiencing issues. You can
potentially resolve this by increasing the challenge answer delay (default: 8 seconds). \
For example: cfscrape.create_scraper(delay=15)

If increasing the delay does not help, please open a GitHub issue at \
https://github.com/Anorov/cloudflare-scrape/issues\
"""

# Remove a few problematic TLSv1.0 ciphers from the defaults
DEFAULT_CIPHERS += ":!ECDHE+SHA:!AES128-SHA"


class CloudflareAdapter(HTTPAdapter):
    """ HTTPS adapter that creates a SSL context with custom ciphers """

    def get_connection(self, *args, **kwargs):
        conn = super(CloudflareAdapter, self).get_connection(*args, **kwargs)

        if conn.conn_kw.get("ssl_context"):
            conn.conn_kw["ssl_context"].set_ciphers(DEFAULT_CIPHERS)
        else:
            context = create_urllib3_context(ciphers=DEFAULT_CIPHERS)
            conn.conn_kw["ssl_context"] = context

        return conn


class CloudflareError(RequestException):
    pass


class CloudflareCaptchaError(CloudflareError):
    pass


class CloudflareScraper(Session):
    def __init__(self, *args, **kwargs):
        self.delay = kwargs.pop("delay", None)
        # Use headers with a random User-Agent if no custom headers have been set
        headers = OrderedDict(kwargs.pop("headers", DEFAULT_HEADERS))

        # Set the User-Agent header if it was not provided
        headers.setdefault("User-Agent", DEFAULT_USER_AGENT)

        super(CloudflareScraper, self).__init__(*args, **kwargs)

        # Define headers to force using an OrderedDict and preserve header order
        self.headers = headers

        self.mount("https://", CloudflareAdapter())

    @staticmethod
    def is_cloudflare_iuam_challenge(resp):
        return (
            resp.status_code in (503, 429)
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"jschl_vc" in resp.content
            and b"jschl_answer" in resp.content
        )

    @staticmethod
    def is_cloudflare_captcha_challenge(resp):
        return (
            resp.status_code == 403
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"/cdn-cgi/l/chk_captcha" in resp.content
        )

    def request(self, method, url, *args, **kwargs):
        resp = super(CloudflareScraper, self).request(method, url, *args, **kwargs)

        # Check if Cloudflare captcha challenge is presented
        if self.is_cloudflare_captcha_challenge(resp):
            self.handle_captcha_challenge(resp, url)

        # Check if Cloudflare anti-bot "I'm Under Attack Mode" is enabled
        if self.is_cloudflare_iuam_challenge(resp):
            resp = self.solve_cf_challenge(resp, **kwargs)

        return resp

    def cloudflare_is_bypassed(self, url, resp=None):
        cookie_domain = ".{}".format(urlparse(url).netloc)
        return (
            self.cookies.get("cf_clearance", None, domain=cookie_domain) or
            (resp and resp.cookies.get("cf_clearance", None, domain=cookie_domain))
        )

    def handle_captcha_challenge(self, resp, url):
        error = (
            "Cloudflare captcha challenge presented for %s (cfscrape cannot solve captchas)"
            % urlparse(url).netloc
        )
        if ssl.OPENSSL_VERSION_NUMBER < 0x10101000:
            error += ". Your OpenSSL version is lower than 1.1.1. Please upgrade your OpenSSL library and recompile Python."

        raise CloudflareCaptchaError(error, response=resp)

    def solve_cf_challenge(self, resp, **original_kwargs):
        start_time = time.time()

        body = resp.text
        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed_url.scheme, domain)

        cloudflare_kwargs = copy.deepcopy(original_kwargs)

        headers = cloudflare_kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        try:
            params = cloudflare_kwargs["params"] = OrderedDict(
                re.findall(r'name="(s|jschl_vc|pass)"(?: [^<>]*)? value="(.+?)"', body)
            )

            for k in ("jschl_vc", "pass"):
                if k not in params:
                    raise ValueError("%s is missing from challenge form" % k)
        except Exception as e:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            raise ValueError(
                "Unable to parse Cloudflare anti-bot IUAM page: %s %s"
                % (e.message, BUG_REPORT)
            )

        # Solve the Javascript challenge
        answer, delay = self.solve_challenge(body, domain)
        params["jschl_answer"] = answer

        # Requests transforms any request into a GET after a redirect,
        # so the redirect has to be handled manually here to allow for
        # performing other types of requests even as the first request.
        method = resp.request.method
        cloudflare_kwargs["allow_redirects"] = False

        # Cloudflare requires a delay before solving the challenge
        time.sleep(max(delay - (time.time() - start_time), 0))

        # Send the challenge response and handle the redirect manually
        redirect = self.request(method, submit_url, **cloudflare_kwargs)
        redirect_location = urlparse(redirect.headers["Location"])

        if not redirect_location.netloc:
            redirect_url = urlunparse(
                (
                    parsed_url.scheme,
                    domain,
                    redirect_location.path,
                    redirect_location.params,
                    redirect_location.query,
                    redirect_location.fragment,
                )
            )
            return self.request(method, redirect_url, **original_kwargs)
        return self.request(method, redirect.headers["Location"], **original_kwargs)

    def solve_challenge(self, body, domain):
        try:
            challenge, ms = re.search(
                r"setTimeout\(function\(\){\s*(var "
                r"s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value\s*=.+?)\r?\n"
                r"(?:[^{<>]*},\s*(\d{4,}))?",
                body,
            ).groups()

            # The challenge requires `document.getElementById` to get this content.
            # Future proofing would require escaping newlines and double quotes
            innerHTML = re.search(r"<div(?: [^<>]*)? id=\"cf-dn.*?\">([^<>]*)", body)
            innerHTML = innerHTML.group(1) if innerHTML else ""

            # Prefix the challenge with a fake document object.
            # Interpolate the domain, div contents, and JS challenge.
            # The `a.value` to be returned is tacked onto the end.
            challenge = """
                var document = {
                    createElement: function () {
                      return { firstChild: { href: "http://%s/" } }
                    },
                    getElementById: function () {
                      return {"innerHTML": "%s"};
                    }
                  };

                %s; a.value
            """ % (
                domain,
                innerHTML,
                challenge,
            )
            # Encode the challenge for security while preserving quotes and spacing.
            challenge = b64encode(challenge.encode("utf-8")).decode("ascii")
            # Use the provided delay, parsed delay, or default to 8 secs
            delay = self.delay or (float(ms) / float(1000) if ms else 8)
        except Exception:
            raise ValueError(
                "Unable to identify Cloudflare IUAM Javascript on website. %s"
                % BUG_REPORT
            )

        # Use vm.runInNewContext to safely evaluate code
        # The sandboxed code cannot use the Node.js standard library
        js = (
            """\
            var atob = Object.setPrototypeOf(function (str) {\
                try {\
                    return Buffer.from("" + str, "base64").toString("binary");\
                } catch (e) {}\
            }, null);\
            var challenge = atob("%s");\
            var context = Object.setPrototypeOf({ atob: atob }, null);\
            var options = {\
                filename: "iuam-challenge.js",\
                contextOrigin: "cloudflare:iuam-challenge.js",\
                contextCodeGeneration: { strings: true, wasm: false },\
                timeout: 5000\
            };\
            process.stdout.write(String(\
                require("vm").runInNewContext(challenge, context, options)\
            ));\
        """
            % challenge
        )

        try:
            result = subprocess.check_output(
                ["node", "-e", js], stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except OSError as e:
            if e.errno == 2:
                raise EnvironmentError(
                    "Missing Node.js runtime. Node is required and must be in the PATH (check with `node -v`). Your Node binary may be called `nodejs` rather than `node`, in which case you may need to run `apt-get install nodejs-legacy` on some Debian-based systems. (Please read the cfscrape"
                    " README's Dependencies section: https://github.com/Anorov/cloudflare-scrape#dependencies."
                )
            raise
        except Exception:
            logging.error("Error executing Cloudflare IUAM Javascript. %s" % BUG_REPORT)
            raise

        try:
            float(result)
        except Exception:
            raise ValueError(
                "Cloudflare IUAM challenge returned unexpected answer. %s" % BUG_REPORT
            )

        return result, delay

    @classmethod
    def create_scraper(cls, sess=None, **kwargs):
        """
        Convenience function for creating a ready-to-go CloudflareScraper object.
        """
        scraper = cls(**kwargs)

        if sess:
            attrs = [
                "auth",
                "cert",
                "cookies",
                "headers",
                "hooks",
                "params",
                "proxies",
                "data",
            ]
            for attr in attrs:
                val = getattr(sess, attr, None)
                if val:
                    setattr(scraper, attr, val)

        return scraper

    # Functions for integrating cloudflare-scrape with other applications and scripts

    @classmethod
    def get_tokens(cls, url, user_agent=None, **kwargs):
        scraper = cls.create_scraper()
        if user_agent:
            scraper.headers["User-Agent"] = user_agent

        try:
            resp = scraper.get(url, **kwargs)
            resp.raise_for_status()
        except Exception:
            logging.error("'%s' returned an error. Could not collect tokens." % url)
            raise

        domain = urlparse(resp.url).netloc
        cookie_domain = None

        for d in scraper.cookies.list_domains():
            if d.startswith(".") and d in ("." + domain):
                cookie_domain = d
                break
        else:
            raise ValueError(
                'Unable to find Cloudflare cookies. Does the site actually have Cloudflare IUAM ("I\'m Under Attack Mode") enabled?'
            )

        return (
            {
                "__cfduid": scraper.cookies.get("__cfduid", "", domain=cookie_domain),
                "cf_clearance": scraper.cookies.get(
                    "cf_clearance", "", domain=cookie_domain
                ),
            },
            scraper.headers["User-Agent"],
        )

    @classmethod
    def get_cookie_string(cls, url, user_agent=None, **kwargs):
        """
        Convenience function for building a Cookie HTTP header value.
        """
        tokens, user_agent = cls.get_tokens(url, user_agent=user_agent, **kwargs)
        return "; ".join("=".join(pair) for pair in tokens.items()), user_agent


create_scraper = CloudflareScraper.create_scraper
get_tokens = CloudflareScraper.get_tokens
get_cookie_string = CloudflareScraper.get_cookie_string
