# -*- coding: utf-8 -*-

import logging
import ssl
import subprocess
import copy
import time

from collections import OrderedDict

from requests.sessions import Session
from requests.compat import urlparse, urlunparse

from .adapters import CloudflareAdapter
from .exceptions import CloudflareCaptchaError
from .challenges import CloudflareChallenge

from .utils import DEFAULT_HEADERS, DEFAULT_USER_AGENT, BUG_REPORT


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

        iuam_challenge = CloudflareChallenge(resp, delay=self.delay)

        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed_url.scheme, domain)

        cloudflare_kwargs = copy.deepcopy(original_kwargs)

        headers = cloudflare_kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        params = iuam_challenge.form
        params["jschl_answer"] = self.eval_challenge(iuam_challenge)
        cloudflare_kwargs["params"] = params

        # Requests transforms any request into a GET after a redirect,
        # so the redirect has to be handled manually here to allow for
        # performing other types of requests even as the first request.
        method = resp.request.method
        cloudflare_kwargs["allow_redirects"] = False

        # Cloudflare requires a delay before solving the challenge
        time.sleep(max(iuam_challenge.delay - (time.time() - start_time), 0))

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

    @staticmethod
    def eval_js(js):
        try:
            return subprocess.check_output(
                ["node", "-e", js], stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except OSError as e:
            if e.errno == 2:
                raise EnvironmentError(
                    "Missing Node.js runtime. Node is required and must be in the PATH (check with `node -v`). Your Node binary may be called `nodejs` rather than `node`, in which case you may need to run `apt-get install nodejs-legacy` on some Debian-based systems. (Please read the cfscrape"
                    " README's Dependencies section: https://github.com/Anorov/cloudflare-scrape#dependencies."
                )
            raise

    @classmethod
    def eval_challenge(cls, iuam_challenge):
        # Use vm.runInNewContext to safely evaluate code
        # The sandboxed code cannot use the Node.js standard library
        js = """\
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

        js = js % iuam_challenge.to_base64()

        try:
            result = cls.eval_js(js)
        except Exception:
            logging.error("Error executing Cloudflare IUAM Javascript. %s" % BUG_REPORT)
            raise

        try:
            float(result)
        except Exception:
            raise ValueError(
                "Cloudflare IUAM challenge returned unexpected answer. %s" % BUG_REPORT
            )

        return result

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
