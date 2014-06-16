import re
import requests
import PyV8

def grab_cloudflare(url, *args, **kwargs):
    sess = requests.session()
    sess.headers["User-Agent"] = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:17.0) Gecko/20100101 Firefox/17.0"
    resp = sess.get(url, *args, **kwargs)
    page = resp.content

    if "a = document.getElementById('jschl-answer');" not in page:
        # Return page as it is; no Cloudflare protection detected
        return page

    # Otherwise, Cloudflare anti-bots is on

    if resp.history:
        # If there are redirects, use the URL of the last redirect
        url = resp.history[-1].headers["Location"]

    domain = url.split("/")[2]

    challenge = re.search(r'name="jschl_vc" value="(\w+)"', page).group(1)

    builder = re.search(r"setTimeout.+?\r?\n([\s\S]+?a\.value =.+?)\r?\n", page).group(1)
    builder = re.sub(r"a\.value =(.+?) \+ .+?;", r"\1", builder)
    builder = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", builder)

    ctxt = PyV8.JSContext()
    ctxt.enter()
    # Safely evaluate Javascript expression
    answer = str(int(ctxt.eval(builder)) + len(domain))

    params = {"jschl_vc": challenge, "jschl_answer": answer}
    submit_url = url + "/cdn-cgi/l/chk_jschl"
    return sess.get(submit_url, params=params, headers={"Referer": url}, *args, **kwargs).content
