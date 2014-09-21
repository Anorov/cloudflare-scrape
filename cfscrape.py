import re
import PyV8
from urlparse import urlparse
import requests
from requests.adapters import HTTPAdapter

DEFAULT_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Ubuntu Chromium/34.0.1847.116 Chrome/34.0.1847.116 Safari/537.36")

class CloudflareAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        domain = request.url.split("/")[2]
        resp = super(CloudflareAdapter, self).send(request, **kwargs)

        # Check if we already solved a challenge
        if request._cookies.get("cf_clearance", domain="." + domain):
            return resp

        # Check if Cloudflare anti-bot is on
        if "a = document.getElementById('jschl-answer');" in resp.content:
            return self.solve_cf_challenge(resp, request.headers, **kwargs)

        # Otherwise, no Cloudflare anti-bot detected
        return resp

    def add_headers(self, request):
        # Spoof Chrome on Linux if no custom User-Agent has been set
        if "requests" in request.headers["User-Agent"]:
            request.headers["User-Agent"] = DEFAULT_USER_AGENT

    def solve_cf_challenge(self, resp, headers, **kwargs):
        headers = headers.copy()
        url = resp.url
        parsed = urlparse(url)
        domain = parsed.netloc
        page = resp.content
        kwargs.pop("params", None) # Don't pass on params

        try:
            # Extract the arithmetic operation
            challenge = re.search(r'name="jschl_vc" value="(\w+)"', page).group(1)
            builder = re.search(r"setTimeout.+?\r?\n([\s\S]+?a\.value =.+?)\r?\n", page).group(1)
            builder = re.sub(r"a\.value =(.+?) \+ .+?;", r"\1", builder)
            builder = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", builder)

        except AttributeError:
            # Something is wrong with the page. This may indicate Cloudflare has changed their
            # anti-bot technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            raise IOError("Unable to parse Cloudflare anti-bots page. Try upgrading cfscrape, or "
                          "submit a bug report if you are running the latest version.")

        # Lock must be added explicitly, because PyV8 bypasses the GIL
        with PyV8.JSLocker():
            with PyV8.JSContext() as ctxt:
                # Safely evaluate the Javascript expression
                answer = str(int(ctxt.eval(builder)) + len(domain))

        params = {"jschl_vc": challenge, "jschl_answer": answer}
        submit_url = "%s://%s/cdn-cgi/l/chk_jschl" % (parsed.scheme, domain)
        headers["Referer"] = url

        return requests.get(submit_url, params=params, headers=headers, **kwargs)


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
