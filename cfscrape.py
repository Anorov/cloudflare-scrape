import re
import requests
import lxml.html

def grab_cloudflare(url):
    sess = requests.Session()
    sess.headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:17.0) Gecko/20100101 Firefox/17.0"}
    page = sess.get(url).content
    safe_eval = lambda s: eval(s, {"__builtins__": {}}) if "#" not in s and "__" not in s else ""
    if "a = $('#jschl_answer');" in page:
        #Cloudflare anti-bots is on
        html = lxml.html.fromstring(page)
        challenge = html.find(".//input[@name='jschl_vc']").attrib["value"]
        script = html.findall(".//script")[-1].text_content()
        domain = url.split("/")[2]
        math = re.search(r"a\.val\((\d.+?)\)", script).group(1)
        answer = str(safe_eval(math) + len(domain))
        data = {"act": "jschl", "jschl_vc": challenge, "jschl_answer": answer}
        return sess.post(url, data).content
    else:
        return page
