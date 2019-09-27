import cfscrape  # Required to bypass IUAM challenge and to detect captcha
import sys  # Required to print to stderr i.e. print("foobar", file=sys.stderr)
import re  # Required to parse the captcha siteKey from responses

from requests.compat import urlparse  # Required for captcha form's action URI
# Official python API client: https://pypi.org/project/python-anticaptcha/
from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask

# https://anti-captcha.com/apidoc/recaptcha
# https://anticaptcha.atlassian.net/wiki/spaces/API/pages/196635/Documentation+in+English

API_KEY = ''  # anti-captcha API KEY

# Create a scraper/session and anti-captcha client
scraper = cfscrape.create_scraper()
client = AnticaptchaClient(API_KEY)


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
    """anti-captcha API requests"""

    print('Solving captcha at %s' % pageurl, file=sys.stderr)

    try:
        # Parse the siteKey from the response or hardcode it in your script
        site_key = re.search(r'\sdata-sitekey=["\']?([^\s"\'<>&]+)', html).group(1)
    except AttributeError as error:
        print('Failed to extract siteKey:', file=sys.stderr)
        raise error

    print('siteKey: %s' % site_key, file=sys.stderr)

    task = NoCaptchaTaskProxylessTask(
        website_url=url,
        website_key=site_key
    )

    job = client.createTaskSmee(task)

    # Return the "g-recaptcha-response" token
    return job.get_solution_response()


# Attempt to scrape URL of Cloudflare protected website
print(request('https://captcha.website').text)
