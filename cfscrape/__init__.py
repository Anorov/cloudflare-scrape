import logging
import random
import re
import subprocess
from copy import deepcopy
from time import sleep

from requests.sessions import Session

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

__version__ = "1.9.4"

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:41.0) Gecko/20100101 Firefox/41.0"
]

DEFAULT_USER_AGENT = random.choice(DEFAULT_USER_AGENTS)

BUG_REPORT = """\
Cloudflare may have changed their technique, or there may be a bug in the script.

Please read https://github.com/Anorov/cloudflare-scrape#updates, then file a \
bug report at https://github.com/Anorov/cloudflare-scrape/issues."\
"""

ANSWER_ACCEPT_ERROR = """\
The challenge answer was not properly accepted by Cloudflare. This can occur if \
the target website is under heavy load, or if Cloudflare is experiencing issues. You can
potentially resolve this by increasing the challenge answer delay (default: 5 seconds). \
For example: cfscrape.create_scraper(delay=10)

If increasing the delay does not help, please open a GitHub issue at \
https://github.com/Anorov/cloudflare-scrape/issues\
"""

class CloudflareScraper(Session):
    def __init__(self, *args, **kwargs):
        self.delay = kwargs.pop("delay", 5)
        super(CloudflareScraper, self).__init__(*args, **kwargs)

        if "requests" in self.headers["User-Agent"]:
            # Set a random User-Agent if no custom User-Agent has been set
            self.headers["User-Agent"] = DEFAULT_USER_AGENT

    def is_cloudflare_challenge(self, resp):
        return (
            resp.status_code == 503
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"jschl_vc" in resp.content
            and b"jschl_answer" in resp.content
        )

    def request(self, method, url, *args, **kwargs):
        resp = super(CloudflareScraper, self).request(method, url, *args, **kwargs)

        # Check if Cloudflare anti-bot is on
        if self.is_cloudflare_challenge(resp):
            resp = self.solve_cf_challenge(resp, **kwargs)
            if self.is_cloudflare_challenge(resp):
                raise ValueError(ANSWER_ACCEPT_ERROR)

        return resp

    def solve_cf_challenge(self, resp, **original_kwargs):
        sleep(self.delay)  # Cloudflare requires a delay before solving the challenge

        body = resp.text
        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed_url.scheme, domain)

        cloudflare_kwargs = deepcopy(original_kwargs)
        params = cloudflare_kwargs.setdefault("params", {})
        headers = cloudflare_kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        try:
            params["jschl_vc"] = re.search(r'name="jschl_vc" value="(\w+)"', body).group(1)
            params["pass"] = re.search(r'name="pass" value="(.+?)"', body).group(1)

        except Exception as e:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            raise ValueError("Unable to parse Cloudflare anti-bots page: %s %s" % (e.message, BUG_REPORT))

        # Solve the Javascript challenge
        params["jschl_answer"] = str(self.solve_challenge(body) + len(domain))

        # Requests transforms any request into a GET after a redirect,
        # so the redirect has to be handled manually here to allow for
        # performing other types of requests even as the first request.
        method = resp.request.method
        cloudflare_kwargs["allow_redirects"] = False
        redirect = self.request(method, submit_url, **cloudflare_kwargs)

        redirect_location = urlparse(redirect.headers["Location"])
        if not redirect_location.netloc:
            redirect_url = "%s://%s%s" % (parsed_url.scheme, domain, redirect_location.path)
            return self.request(method, redirect_url, **original_kwargs)
        return self.request(method, redirect.headers["Location"], **original_kwargs)

    def solve_challenge(self, body):
        try:
            js = re.search(r"setTimeout\(function\(\){\s+(var "
                        "s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value =.+?)\r?\n", body).group(1)
        except Exception:
            raise ValueError("Unable to identify Cloudflare IUAM Javascript on website. %s" % BUG_REPORT)

        js = re.sub(r"a\.value = (parseInt\(.+?\)).+", r"\1", js)
        js = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", js)

        # Strip characters that could be used to exit the string context
        # These characters are not currently used in Cloudflare's arithmetic snippet
        js = re.sub(r"[\n\\']", "", js)

        if "parseInt" not in js:
            raise ValueError("Error parsing Cloudflare IUAM Javascript challenge. %s" % BUG_REPORT)

        # Use vm.runInNewContext to safely evaluate code
        # The sandboxed code cannot use the Node.js standard library
        js = "console.log(require('vm').runInNewContext('%s', Object.create(null), {timeout: 5000}));" % js

        try:
            result = subprocess.check_output(["node", "-e", js]).strip()
        except OSError as e:
            if e.errno == 2:
                raise EnvironmentError("Missing Node.js runtime. Node is required. Please read the cfscrape"
                    " README's Dependencies section: https://github.com/Anorov/cloudflare-scrape#dependencies.")
            raise
        except Exception:
            logging.error("Error executing Cloudflare IUAM Javascript. %s" % BUG_REPORT)
            raise

        try:
            result = int(result)
        except Exception:
            raise ValueError("Cloudflare IUAM challenge returned unexpected answer. %s" % BUG_REPORT)

        return result

    @classmethod
    def create_scraper(cls, sess=None, **kwargs):
        """
        Convenience function for creating a ready-to-go CloudflareScraper object.
        """
        scraper = cls(**kwargs)

        if sess:
            attrs = ["auth", "cert", "cookies", "headers", "hooks", "params", "proxies", "data"]
            for attr in attrs:
                val = getattr(sess, attr, None)
                if val:
                    setattr(scraper, attr, val)

        return scraper


    ## Functions for integrating cloudflare-scrape with other applications and scripts

    @classmethod
    def get_tokens(cls, url, user_agent=None, **kwargs):
        scraper = cls.create_scraper()
        if user_agent:
            scraper.headers["User-Agent"] = user_agent

        try:
            resp = scraper.get(url, **kwargs)
            resp.raise_for_status()
        except Exception as e:
            logging.error("'%s' returned an error. Could not collect tokens." % url)
            raise

        domain = urlparse(resp.url).netloc
        cookie_domain = None

        for d in scraper.cookies.list_domains():
            if d.startswith(".") and d in ("." + domain):
                cookie_domain = d
                break
        else:
            raise ValueError("Unable to find Cloudflare cookies. Does the site actually have Cloudflare IUAM (\"I'm Under Attack Mode\") enabled?")

        return ({
                    "__cfduid": scraper.cookies.get("__cfduid", "", domain=cookie_domain),
                    "cf_clearance": scraper.cookies.get("cf_clearance", "", domain=cookie_domain)
                },
                scraper.headers["User-Agent"]
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
