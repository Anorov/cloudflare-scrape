import logging
import random
import re
import subprocess
import copy
import time

from requests.sessions import Session

from collections import OrderedDict

try:
    from urlparse import urlparse
    from urlparse import urlunparse
except ImportError:
    from urllib.parse import urlparse
    from urllib.parse import urlunparse

__version__ = "1.9.7"

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/65.0.3325.181 Chrome/65.0.3325.181 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; Moto G (5) Build/NPPS25.137-93-8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.137 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 7_0_4 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11B554a Safari/9537.53",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:60.0) Gecko/20100101 Firefox/60.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:59.0) Gecko/20100101 Firefox/59.0",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64; rv:57.0) Gecko/20100101 Firefox/57.0"
]

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

class CloudflareScraper(Session):
    def __init__(self, *args, **kwargs):
        self.default_delay = 8
        self.delay =  kwargs.pop("delay", self.default_delay)
        super(CloudflareScraper, self).__init__(*args, **kwargs)

        if "requests" in self.headers["User-Agent"]:
            # Set a random User-Agent if no custom User-Agent has been set
            self.headers["User-Agent"] = random.choice(DEFAULT_USER_AGENTS)

    def is_cloudflare_challenge(self, resp):
        return (
            resp.status_code == 503
            and resp.headers.get("Server", "").startswith("cloudflare")
            and b"jschl_vc" in resp.content
            and b"jschl_answer" in resp.content
        )

    def request(self, method, url, *args, **kwargs):
        self.headers = (
            OrderedDict(
                [
                    ('User-Agent', self.headers['User-Agent']),
                    ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                    ('Accept-Language', 'en-US,en;q=0.5'),
                    ('Accept-Encoding', 'gzip, deflate'),
                    ('Connection',  'close'),
                    ('Upgrade-Insecure-Requests', '1')
                ]
            )
        )

        resp = super(CloudflareScraper, self).request(method, url, *args, **kwargs)

        # Check if Cloudflare anti-bot is on
        if self.is_cloudflare_challenge(resp):
            resp = self.solve_cf_challenge(resp, **kwargs)

        return resp

    def solve_cf_challenge(self, resp, **original_kwargs):
        start_time = time.time()

        body = resp.text
        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed_url.scheme, domain)

        cloudflare_kwargs = copy.deepcopy(original_kwargs)
        params = cloudflare_kwargs.setdefault("params", {})
        headers = cloudflare_kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        try:
            params["s"] = re.search(r'name="s"\svalue="(?P<s_value>[^"]+)', body).group('s_value')
            params["jschl_vc"] = re.search(r'name="jschl_vc" value="(\w+)"', body).group(1)
            params["pass"] = re.search(r'name="pass" value="(.+?)"', body).group(1)
        except Exception as e:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            raise ValueError("Unable to parse Cloudflare anti-bots page: %s %s" % (e.message, BUG_REPORT))

        # Solve the Javascript challenge
        params["jschl_answer"] = self.solve_challenge(body, domain)

        # Check if the default delay has been overridden. If not, use the delay required by
        # cloudflare.
        if self.delay == self.default_delay:
            try:
                self.delay = float(re.search(r"submit\(\);\r?\n\s*},\s*([0-9]+)", body).group(1)) / float(1000)
            except:
                pass

        # Requests transforms any request into a GET after a redirect,
        # so the redirect has to be handled manually here to allow for
        # performing other types of requests even as the first request.
        method = resp.request.method
        cloudflare_kwargs["allow_redirects"] = False

        end_time = time.time()
         # Cloudflare requires a delay before solving the challenge
        time.sleep(self.delay - (end_time - start_time))

        redirect = self.request(method, submit_url, **cloudflare_kwargs)
        redirect_location = urlparse(redirect.headers["Location"])
        if not redirect_location.netloc:
            redirect_url = urlunparse((parsed_url.scheme, domain, redirect_location.path, redirect_location.params, redirect_location.query, redirect_location.fragment))
            return self.request(method, redirect_url, **original_kwargs)
        return self.request(method, redirect.headers["Location"], **original_kwargs)

    def solve_challenge(self, body, domain):
        try:
            js = re.search(r"setTimeout\(function\(\){\s+(var "
                        "s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value =.+?)\r?\n", body).group(1)
        except Exception:
            raise ValueError("Unable to identify Cloudflare IUAM Javascript on website. %s" % BUG_REPORT)

        js = re.sub(r"a\.value = (.+\.toFixed\(10\);).+", r"\1", js)
        # Match code that accesses the DOM and remove it, but without stripping too much.
        try:
            solution_name = re.search("s,t,o,p,b,r,e,a,k,i,n,g,f,\s*(.+)\s*=", js).groups(1)
            match = re.search("(.*};)\n\s*(t\s*=(.+))\n\s*(;%s.*)" % (solution_name), js, re.M | re.I | re.DOTALL).groups()
            js = match[0] + match[-1]
        except Exception:
            raise ValueError("Error parsing Cloudflare IUAM Javascript challenge. %s" % BUG_REPORT)
        js = js.replace("t.length", str(len(domain)))

        # Strip characters that could be used to exit the string context
        # These characters are not currently used in Cloudflare's arithmetic snippet
        js = re.sub(r"[\n\\']", "", js)

        if "toFixed" not in js:
            raise ValueError("Error parsing Cloudflare IUAM Javascript challenge. %s" % BUG_REPORT)

        # 2019-03-20: Cloudflare sometimes stores part of the challenge in a div which is later
        # added using document.getElementById(x).innerHTML, so it is necessary to simulate that
        # method and value.
        try:
            # Find the id of the div in the javascript code.
            k = re.search(r"k\s+=\s+'([^']+)';", body).group(1)
            # Find the div with that id and store its content.
            val = re.search(r'<div(.*)id="%s"(.*)>(.*)</div>' % (k), body).group(3)
        except Exception:
            # If not available, either the code has been modified again, or the old
            # style challenge is used.
            k = ''
            val = ''

        # Use vm.runInNewContext to safely evaluate code
        # The sandboxed code cannot use the Node.js standard library
        # Add the atob method which is now used by Cloudflares code, but is not available in all node versions.
        simulate_document_js = 'var document= {getElementById: function(x) { return {innerHTML:"%s"};}}' % (val)
        atob_js = 'var atob = function(str) {return Buffer.from(str, "base64").toString("binary");}'
        # t is not defined, so we have to define it and set it to the domain name.
        js = '%s;%s;var t="%s";%s' % (simulate_document_js,atob_js,domain,js)
        buffer_js = "var Buffer = require('buffer').Buffer"
        # Pass Buffer into the new context, so it is available for atob.
        js = "%s;console.log(require('vm').runInNewContext('%s', {'Buffer':Buffer,'g':String.fromCharCode}, {timeout: 5000}));" % (buffer_js, js)

        try:
            result = subprocess.check_output(["node", "-e", js]).strip()
        except OSError as e:
            if e.errno == 2:
                raise EnvironmentError("Missing Node.js runtime. Node is required and must be in the PATH (check with `node -v`). Your Node binary may be called `nodejs` rather than `node`, in which case you may need to run `apt-get install nodejs-legacy` on some Debian-based systems. (Please read the cfscrape"
                    " README's Dependencies section: https://github.com/Anorov/cloudflare-scrape#dependencies.")
            raise
        except Exception:
            logging.error("Error executing Cloudflare IUAM Javascript. %s" % BUG_REPORT)
            raise

        try:
            float(result)
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
