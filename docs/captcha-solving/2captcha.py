import cfscrape  # Required to bypass IUAM challenge and to detect captcha
import sys  # Required to print to stderr i.e. print("foobar", file=sys.stderr)
import re  # Required to parse the captcha siteKey from responses

from time import sleep  # <-- Required to poll 2captcha API
from requests.compat import urlparse  # Required for captcha form's action URI

# https://2captcha.com/2captcha-api#solving_recaptchav2_new

API_KEY = ''  # 2captcha API KEY

# Create a scraper/session
scraper = cfscrape.create_scraper()


def request(url, *args, **kwargs):
    """Simple request wrapper"""

    try:
        # Request a page that may reply with reCAPTCHA(v2)
        return scraper.get(url, *args, **kwargs)
    except cfscrape.CloudflareCaptchaError as error:
        # Some services expect pageurl to only include the domain
        pageurl = error.response.url  # Accounts for redirects
        # Use 2captcha to solve and get the "g-recaptcha-response"
        token = solve_captcha(pageurl, error.response.text)
        # Construct the URL needed to submit the solution
        o = urlparse(url)  # You could hardcode this URL in your script
        url = '%s://%s/cdn-cgi/l/chk_captcha' % (o.scheme, o.net_loc)
        # The URL query parameters to send to Cloudflare
        kwargs['params'] = {'g-recaptcha-response': token}
        # Cloudflare should redirect unless there's more challenges
        # !!! Avoid sending extra stuff, maybe only send params !!!
        return request(url, *args, **kwargs)


def solve_captcha(pageurl, html):
    """2captcha API requests"""

    print('Solving captcha at %s' % pageurl, file=sys.stderr)

    try:
        # Parse the siteKey from the response or hardcode it in your script
        site_key = re.search(r'\sdata-sitekey=["\']?([^\s"\'<>&]+)', html).group(1)
    except AttributeError as error:
        print('Failed to extract siteKey:', file=sys.stderr)
        raise error

    print('siteKey: %s' % site_key, file=sys.stderr)

    # The URL query parameters to send to 2captcha
    params = {
        'key': API_KEY,
        'method': 'userrecaptcha',
        'version': 'v2',
        'googlekey': site_key,
        'pageurl': pageurl,
        'json': '0'  # This example uses the CSV response
    }

    # Post the siteKey to 2captcha to get response with captcha ID
    response = scraper.post('http://2captcha.com/in.php', params=params)
    response.raise_for_status()

    # Handle CSV formatted response i.e. "OK|CID"
    result = response.text.split('|')
    if len(result) < 2 or result[0] != 'OK':
        # See https://2captcha.com/2captcha-api#in_errors
        raise ValueError('Failed to get captcha ID: %s' % response.text)

    cid = result[1]  # CAPTCHA ID

    # The URL query parameters to send to 2captcha
    params = {
        'key': API_KEY,
        'action': 'get',
        'id': cid,
        'json': '0'  # This example uses the CSV response
    }

    # Poll for the answer (g-recaptcha-response)
    while True:
        response = scraper.get('http://2captcha.com/res.php', params=params)
        response.raise_for_status()

        # Somebody over at 2captcha doesn't know how to spell...
        if 'CAPCHA_NOT_READY' in response.text:
            sleep(5)  # API docs say to wait 5 seconds
            continue

        # Handle CSV formatted response i.e. "OK|TOKEN"
        result = response.text.split('|')
        if len(result) < 2 or result[0] != 'OK':
            # https://2captcha.com/2captcha-api#res_errors
            raise ValueError('Failed to get captcha token: %s' % response.text)

        # Return the "g-recaptcha-response" token
        return result[1]


# Attempt to scrape URL of Cloudflare protected website
print(request('https://captcha.website').text)
