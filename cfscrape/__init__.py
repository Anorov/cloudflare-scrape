import time
import re
import requests
from requests.adapters import HTTPAdapter
import execjs

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

DEFAULT_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Ubuntu Chromium/34.0.1847.116 Chrome/34.0.1847.116 Safari/537.36")

JS_ENGINE = execjs.get().name

if not ("Node" in JS_ENGINE or "V8" in JS_ENGINE):
    raise EnvironmentError("Your Javascript runtime '%s' is not supported due to security concerns. "
                           "Please use Node.js, V8, or PyV8." % JS_ENGINE)

class CloudflareAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
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
        js = js.replace("\n", "").replace("'", "")
        if "Node" in JS_ENGINE:
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

        except Exception as e:
            # Something is wrong with the page. This may indicate Cloudflare has changed their
            # anti-bot technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            print ("[!] Unable to parse Cloudflare anti-bots page. Try upgrading cloudflare-scrape, or submit "
                   "a bug report if you are running the latest version. Please read "
                   "https://github.com/Anorov/cloudflare-scrape#updates before submitting a bug report.\n")
            raise

        # Safely evaluate the Javascript expression
        js = self.format_js(builder)
        answer = str(int(execjs.exec_(js)) + len(domain))

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

def get_tokens(url):
    scraper = create_scraper()
    resp = scraper.get(url)
    if not resp.ok:
        raise ValueError("'%s' returned error %d, could not collect tokens." % (url, resp.status_code))

    return { 
             "__cfduid": resp.cookies.get("__cfduid", ""),
             "cf_clearance": scraper.cookies.get("cf_clearance", "")
           }

def get_cookie_string(url):
    tokens = get_tokens(url)
    return "; ".join("=".join(pair) for pair in tokens.items())
