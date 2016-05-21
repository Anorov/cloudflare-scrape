import time
import re
import os
from requests.sessions import Session
import execjs

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:39.0) Gecko/20100101 Firefox/39.0"


class CloudflareScraper(Session):
    def __init__(self, *args, **kwargs):
        self.js_engine = kwargs.pop("js_engine", None)
        super(CloudflareScraper, self).__init__(*args, **kwargs)

        if "requests" in self.headers["User-Agent"]:
            # Spoof Firefox on Linux if no custom User-Agent has been set
            self.headers["User-Agent"] = DEFAULT_USER_AGENT

    def request(self, method, url, *args, **kwargs):
        resp = super(CloudflareScraper, self).request(method, url, *args, **kwargs)

        # Check if Cloudflare anti-bot is on
        if ( "URL=/cdn-cgi/" in resp.headers.get("Refresh", "") and
             resp.headers.get("Server", "") == "cloudflare-nginx" ):
            return self.solve_cf_challenge(resp, **kwargs)

        # Otherwise, no Cloudflare anti-bot detected
        return resp

    def solve_cf_challenge(self, resp, **kwargs):
        time.sleep(5)  # Cloudflare requires a delay before solving the challenge

        body = resp.text
        parsed_url = urlparse(resp.url)
        domain = urlparse(resp.url).netloc
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed_url.scheme, domain)

        params = kwargs.setdefault("params", {})
        headers = kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        try:
            params["jschl_vc"] = re.search(r'name="jschl_vc" value="(\w+)"', body).group(1)
            params["pass"] = re.search(r'name="pass" value="(.+?)"', body).group(1)

            # Extract the arithmetic operation
            js = self.extract_js(body)

        except Exception:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            print("[!] Unable to parse Cloudflare anti-bots page. "
                  "Try upgrading cloudflare-scrape, or submit a bug report "
                  "if you are running the latest version. Please read "
                  "https://github.com/Anorov/cloudflare-scrape#updates "
                  "before submitting a bug report.\n")
            raise

        # Safely evaluate the Javascript expression
        params["jschl_answer"] = str(int(execjs.exec_(js)) + len(domain))

        return self.get(submit_url, **kwargs)

    def extract_js(self, body):
        js = re.search(r"setTimeout\(function\(\){\s+(var "
                        "t,r,a,f.+?\r?\n[\s\S]+?a\.value =.+?)\r?\n", body).group(1)
        js = re.sub(r"a\.value =(.+?) \+ .+?;", r"\1", js)
        js = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", js)

        # Strip characters that could be used to exit the string context
        # These characters are not currently used in Cloudflare's arithmetic snippet
        js = re.sub(r"[\n\\']", "", js)

        if "Node" in self.js_engine:
            # Use vm.runInNewContext to safely evaluate code
            # The sandboxed code cannot use the Node.js standard library
            return "return require('vm').runInNewContext('%s');" % js

        return js.replace("parseInt", "return parseInt")

    @classmethod
    def create_scraper(cls, sess=None, js_engine=None):
        """
        Convenience function for creating a ready-to-go requests.Session (subclass) object.
        """
        if js_engine:
            os.environ["EXECJS_RUNTIME"] = js_engine

        js_engine = execjs.get().name

        if not ("Node" in js_engine or "V8" in js_engine):
            raise EnvironmentError("Your Javascript runtime '%s' is not supported due to security concerns. "
                                   "Please use Node.js or PyV8. To force a specific engine, "
                                   "such as Node, call create_scraper(js_engine=\"Node\")" % js_engine)

        scraper = cls(js_engine=js_engine)

        if sess:
            attrs = ["auth", "cert", "cookies", "headers", "hooks", "params", "proxies", "data"]
            for attr in attrs:
                val = getattr(sess, attr, None)
                if val:
                    setattr(scraper, attr, val)

        return scraper


    ## Functions for integrating cloudflare-scrape with other applications and scripts

    @classmethod
    def get_tokens(cls, url, user_agent=None, js_engine=None):
        scraper = cls.create_scraper(js_engine=js_engine)
        if user_agent:
            scraper.headers["User-Agent"] = user_agent

        try:
            resp = scraper.get(url)
            resp.raise_for_status()
        except Exception as e:
            print("'%s' returned an error. Could not collect tokens.\n" % url)
            raise

        domain = urlparse(resp.url).netloc
        cookie_domain = None

        for d in scraper.cookies.list_domains():
            if d.startswith(".") and d in ("." + domain):
                cookie_domain = d
                break
        else:
            raise ValueError("Unable to find cookies")

        return ({
                    "__cfduid": scraper.cookies.get("__cfduid", "", domain=cookie_domain),
                    "cf_clearance": scraper.cookies.get("cf_clearance", "", domain=cookie_domain)
                },
                scraper.headers["User-Agent"]
               )

    @classmethod
    def get_cookie_string(cls, url, user_agent=None, js_engine=None):
        """
        Convenience function for building a Cookie HTTP header value.
        """
        tokens, user_agent = cls.get_tokens(url, user_agent=user_agent, js_engine=None)
        return "; ".join("=".join(pair) for pair in tokens.items()), user_agent

create_scraper = CloudflareScraper.create_scraper
get_tokens = CloudflareScraper.get_tokens
get_cookie_string = CloudflareScraper.get_cookie_string
