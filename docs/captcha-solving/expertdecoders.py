import cfscrape  # Required to bypass IUAM challenge and to detect captcha
import sys  # Required to print to stderr i.e. print("foobar", file=sys.stderr)
import re  # Required to parse the captcha siteKey from responses
import uuid  # Required to generate a unique ID for expertdecoders API

from requests.compat import urlparse  # Required for captcha form's action URI

# https://expertdecoders.com/Programmer-Resources
# https://humancoder.com/RecaptchaV2Api.aspx

API_KEY = ''  # expertdecoders/humancoder/fasttypers API KEY

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
    """expertdecoders API requests"""

    print('Solving captcha at %s' % pageurl, file=sys.stderr)

    try:
        # Parse the siteKey from the response or hardcode it in your script
        site_key = re.search(r'\sdata-sitekey=["\']?([^\s"\'<>&]+)', html).group(1)
    except AttributeError as error:
        print('Failed to extract siteKey:', file=sys.stderr)
        raise error

    print('siteKey: %s' % site_key, file=sys.stderr)

    # The payload to send to expertdecoders (Not actual files)
    params = {
        'action': 'upload',
        'key': API_KEY,
        'captchatype': '3',
        'gen_task_id': str(uuid.uuid1()),  # Task ID used for refund claim
        'sitekey': site_key,
        'pageurl': pageurl
    }

    response = scraper.post('http://fasttypers.org/imagepost.ashx', files=params)
    response.raise_for_status()

    # Return the "g-recaptcha-response" token
    return response.text


# Attempt to scrape URL of Cloudflare protected website
print(request('https://captcha.website').text)
