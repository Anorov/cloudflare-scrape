import time
import re
import requests
from requests.adapters import HTTPAdapter
import execjs

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:39.0) Gecko/20100101 Firefox/39.0"

class JSEngineNames(object):
    nashorn = 'Nashorn'
    node = 'Node'
    phantomjs = 'PhantomJS'
    pyv8 = 'PyV8'
    slimerjs = 'SlimerJS'
    v8 = 'V8'

class CloudflareAdapter(HTTPAdapter):
    _supported_js_engine_names = [
            JSEngineNames.node, JSEngineNames.v8, JSEngineNames.pyv8]
    _js_engine = None
    # this exists to support per-engine quirks without depending on the 'name' field in
    # the engine object, which may change
    _js_engine_name = ''

    def _choose_js_engine(self):
        for name in self._supported_js_engine_names:
            try:
                engine = execjs.get(name)
                return name, engine
            except execjs.RuntimeUnavailable:
                pass

        available_engines = sorted(execjs.available_runtimes().keys())
        # no options left
        raise EnvironmentError("cloudflare-scrape supports these JS engines: \n{supported}, and PyExecJS only detected these: {available}. Please install a supported engine.".format(supported=self._supported_js_engine_names, available=available_engines))

    def send(self, request, **kwargs):
        if self._js_engine is None:
            self._js_engine_name, self._js_engine = self._choose_js_engine()

        domain = request.url.split("/")[2]
        resp = super(CloudflareAdapter, self).send(request, **kwargs)

        # Check if we already solved a challenge
        if request._cookies.get("cf_clearance", domain="." + domain):
            return resp

        # Check if Cloudflare anti-bot is on
        if ( "URL=/cdn-cgi/" in resp.headers.get("Refresh", "") and
             resp.headers.get("Server", "") == "cloudflare-nginx" ):
            return self.solve_cf_challenge(resp, request.headers, resp.cookies, **kwargs)

        # Otherwise, no Cloudflare anti-bot detected
        return resp

    def add_headers(self, request):
        # Spoof Chrome on Linux if no custom User-Agent has been set
        if "requests" in request.headers["User-Agent"]:
            request.headers["User-Agent"] = DEFAULT_USER_AGENT

    def format_js(self, js):
        js = re.sub(r"[\n\\']", "", js)
        if self._js_engine_name == JSEngineNames.node:
            return "return require('vm').runInNewContext('%s');" % js
        return js.replace("parseInt", "return parseInt")

    def solve_cf_challenge(self, resp, headers, cookies, **kwargs):
        time.sleep(5) # Cloudflare requires a delay before solving the challenge

        headers = headers.copy()
        url = resp.url
        parsed = urlparse(url)
        domain = parsed.netloc
        page = resp.text
        kwargs.pop("params", None) # Don't pass on params
        try:
            challenge = re.search(r'name="jschl_vc" value="(\w+)"', page).group(1)
            challenge_pass = re.search(r'name="pass" value="(.+?)"', page).group(1)

            # Extract the arithmetic operation
            builder = re.search(r"setTimeout\(function\(\){\s+(var t,r,a,f.+?\r?\n[\s\S]+?a\.value =.+?)\r?\n", page).group(1)
            builder = re.sub(r"a\.value =(.+?) \+ .+?;", r"\1", builder)
            builder = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", builder)

        except Exception:
            # Something is wrong with the page. This may indicate Cloudflare has changed their
            # anti-bot technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            print ("[!] Unable to parse Cloudflare anti-bots page. Try upgrading cloudflare-scrape, or submit "
                   "a bug report if you are running the latest version. Please read "
                   "https://github.com/Anorov/cloudflare-scrape#updates before submitting a bug report.\n")
            raise

        # Safely evaluate the Javascript expression
        js = self.format_js(builder)
        answer = str(int(self._js_engine.exec_(js)) + len(domain))

        params = {"jschl_vc": challenge, "jschl_answer": answer, "pass": challenge_pass}
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed.scheme, domain)
        headers["Referer"] = url

        resp = requests.get(submit_url, params=params, headers=headers, cookies=cookies, **kwargs)
        resp.cookies.set("__cfduid", cookies.get("__cfduid"))
        return resp


def create_scraper(session=None):
    """
    Convenience function for creating a ready-to-go requests.Session object.
    You may optionally pass in an existing Session to mount the CloudflareAdapter to it.
    """
    sess = session or requests.session()
    adapter = CloudflareAdapter()
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    return sess

def get_tokens(url, user_agent=None):
    scraper = create_scraper()
    user_agent = user_agent or DEFAULT_USER_AGENT
    scraper.headers["User-Agent"] = user_agent

    try:
        resp = scraper.get(url)
        resp.raise_for_status()
    except Exception:
        print("'%s' returned error %d, could not collect tokens.\n" % (url, resp.status_code))
        raise

    return ( {
                 "__cfduid": resp.cookies.get("__cfduid", ""),
                 "cf_clearance": scraper.cookies.get("cf_clearance", "")
             },
             user_agent
           )

def get_cookie_string(url, user_agent=None):
    tokens, user_agent = get_tokens(url, user_agent=user_agent)
    return "; ".join("=".join(pair) for pair in tokens.items()), user_agent
