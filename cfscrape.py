import re
import requests
import lxml.html

        
def grab_cloudflare(url, *args, **kwargs):
    sess = requests.session()
    sess.headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:17.0) Gecko/20100101 Firefox/17.0"}
    safe_eval = lambda s: eval(s, {"__builtins__": {}}) if "#" not in s and "__" not in s else ""
    page = sess.get(url, *args, **kwargs).content

    if "a = document.getElementById('jschl-answer');" in page:
        # Cloudflare anti-bots is on
        html = lxml.html.fromstring(page)
        challenge = html.find(".//input[@name='jschl_vc']").attrib["value"]
        script = html.findall(".//script")[-1].text_content()
        domain_parts = url.split("/")
        domain = domain_parts[2]
        math = re.search(r"a\.value = (\d.+?);", script).group(1)
        answer = str(safe_eval(math) + len(domain))
        data = {"jschl_vc": challenge, "jschl_answer": answer}
        get_url = domain_parts[0] + '//' + domain + "/cdn-cgi/l/chk_jschl"
        return sess.get(get_url, params=data, headers={"Referer": url}, *args, **kwargs).content
    else:
        return page
