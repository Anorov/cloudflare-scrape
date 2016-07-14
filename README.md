cloudflare-scrape
=================

A simple Python module to bypass Cloudflare's anti-bot page (also known as "I'm Under Attack Mode", or IUAM), implemented with [Requests](https://github.com/kennethreitz/requests). Cloudflare changes their techniques periodically, so I will update this repo frequently.

This can be useful if you wish to scrape or crawl a website protected with Cloudflare. Cloudflare's anti-bot page currently just checks if the client supports Javascript, though they may add additional techniques in the future.

Due to Cloudflare continually changing and hardening their protection page, cloudflare-scrape now uses **[PyExecJS](https://github.com/doloopwhile/PyExecJS)**, a Python wrapper around multiple Javascript runtime engines. This allows the script to easily and effectively impersonate a regular web browser without explicitly parsing and converting Cloudflare's Javascript obfuscation techniques.

The only supported Javascript engines at this time are Node.js and PyV8. This is due to potential security concerns with the other engines.

Note: This only works when regular Cloudflare anti-bots is enabled (the "Checking your browser before accessing..." loading page). If there is a reCAPTCHA challenge, you're out of luck. Thankfully, the Javascript check page is much more common.

For reference, this is the default message Cloudflare uses for these sorts of pages:

    Checking your browser before accessing website.com.

    This process is automatic. Your browser will redirect to your requested content shortly.

    Please allow up to 5 seconds...

Any script using cloudflare-scrape will sleep for 5 seconds for the first visit to any site with Cloudflare anti-bots enabled, though no delay will occur after the first request.

Warning
======

This script will execute arbitrary Javascript code, which can potentially be harmful in some runtime environments. Due to this, the only Javascript engines permitted are PyV8 and Node.js. With Node, all code will be executed in a sandbox, making Node's standard library inaccessible. With PyV8, only Javascript built-ins are available, so the filesystem and shell cannot be accessed at all.

Barring a critical flaw in V8 or Node, the primary risk is that someone could craft a page which causes the Javascript interpreter to loop endlessly, or potentially consume a lot of memory if a garbage collector issue is identified in V8 or Node.

Shell execution should be impossible if you use PyV8 or Node.

Installation
============

Simply run `pip install cfscrape`. The PyPI package is at https://pypi.python.org/pypi/cfscrape/

Alternatively, clone this repository and run `python setup.py install`.

You will also need a Javascript runtime. See below for more information.

Dependencies
============

* Python 2.6 - 3.x
* **[Requests](https://github.com/kennethreitz/requests)** >= 2.0
* **[PyExecJS](https://pypi.python.org/pypi/PyExecJS)**
* Node.js or PyV8. I recommend Node.js. You can install it with `apt-get install nodejs` on Ubuntu, [or by reading Node.js's installation instructions](https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager#debian-and-ubuntu-based-linux-distributions) otherwise.

`python setup.py install` will install all of these dependencies except for the Javascript runtime, which must be installed manually if you don't already have a supported one.

Updates
=======

Cloudflare modifies their anti-bot protection page occasionally. So far it has changed maybe once per year on average.

If you notice that the anti-bot page has changed, or if this module suddenly stops working, please create a GitHub issue so that I can update the code accordingly.

In your issue, please include:

* The full exception and stack trace.
* The URL of the Cloudflare-protected page which the script does not work on.
* A Pastebin or Gist containing the HTML source of the protected page.

[This issue comment is a good example.](https://github.com/Anorov/cloudflare-scrape/issues/3#issuecomment-45827514)

Usage
=====

The simplest way to use cloudflare-scrape is by calling `create_scraper()`.

```python
import cfscrape

scraper = cfscrape.create_scraper()  # returns a CloudflareScraper instance
# Or: scraper = cfscrape.CloudflareScraper()  # CloudflareScraper inherits from requests.Session
print scraper.get("http://somesite.com").content  # => "<!DOCTYPE html><html><head>..."
```

That's it. Any requests made from this session object to websites protected by Cloudflare anti-bot will be handled automatically. Websites not using Cloudflare will be treated normally. You don't need to configure or call anything further, and you can effectively treat all websites as if they're not protected with anything.

You use cloudflare-scrape exactly the same way you use Requests. (`CloudflareScraper` works identically to a requests `Session` object.) Just instead of calling `requests.get()` or `requests.post()`, you call `scraper.get()` or `scraper.post()`. Consult [Requests' documentation](http://docs.python-requests.org/en/latest/user/quickstart/) for more information.

## Options

### Javascript engine

ExecJS will pick from a list of Javascript engines that it detects are installed. You can optionally choose a specific ExecJS engine to use. (Only `"Node"` and `"PyV8"` are allowed.)

```python
scraper = cfscrape.create_scraper(js_engine="Node")
# The js_engine keyword argument also works with all of the convenience functions described below

```

### Existing session

If you already have an existing requests session, you can pass it to `create_scraper()` to continue using that session.

```python
session = requests.session()
session.headers = ...
scraper = cfscrape.create_scraper(sess=session)
```

Unfortunately, not all of requests' session attributes are easily transferable, so if you run into problems with this, you should replace your initial `sess = requests.session()` call with `sess = cfscrape.create_scraper()`.

## Integration

It's easy to integrate cloudflare-scrape with other applications and tools. Cloudflare uses two cookies as tokens: one to verify you made it past their challenge page and one to track your session. To bypass the challenge page, simply include both of these cookies (with the appropriate user-agent) in all HTTP requests you make.

To retrieve just the cookies (as a dictionary), use `cfscrape.get_tokens()`. To retrieve them as a full `Cookie` HTTP header, use `cfscrape.get_cookie_string()`.

*User-Agent Handling*

The two integration functions return a tuple of `(cookie, user_agent_string)`. **You must use the same user-agent string for obtaining tokens and for making requests with those tokens, otherwise Cloudflare will flag you as a bot.** That means you have to pass the returned `user_agent_string` to whatever script, tool, or service you are passing the tokens to (e.g. curl, or a specialized scraping tool), and it must use that passed user-agent when it makes HTTP requests.

If your tool already has a particular user-agent configured, you can make cloudflare-scrape use it with `cfscrape.get_tokens("http://somesite.com/", user_agent="User-Agent Here")` (also works for `get_cookie_string`). Otherwise, a user-agent spoofing Firefox on Linux will be chosen by default.

--------------------------------------------------------------------------------

### Integration examples

Remember, you must always use the same user-agent when retrieving or using these cookies. These functions all return a tuple of `(data, user_agent)`.

**Retrieving a cookie dict**

`get_tokens` is a convenience function for returning a Python dict containing Cloudflare's session cookies.

```python
import cfscrape

tokens, user_agent = cfscrape.get_tokens("http://somesite.com")
print tokens
# => {'cf_clearance': 'c8f913c707b818b47aa328d81cab57c349b1eee5-1426733163-3600', '__cfduid': 'dd8ec03dfdbcb8c2ea63e920f1335c1001426733158'}
```

**Retrieving a cookie string**

`get_cookie_string` is a convenience function for returning the tokens as a string for use as a `Cookie` HTTP header value.

This is useful when crafting an HTTP request manually, or working with an external application or library that passes on raw cookie headers.

```python
import cfscrape
request = "GET / HTTP/1.1\r\n"

cookie_value, user_agent = cfscrape.get_cookie_string("http://somesite.com")
request += "Cookie: %s\r\nUser-Agent: %s\r\n" % (cookie_value, user_agent)

print request

# GET / HTTP/1.1\r\n
# Cookie: cf_clearance=c8f913c707b818b47aa328d81cab57c349b1eee5-1426733163-3600; __cfduid=dd8ec03dfdbcb8c2ea63e920f1335c1001426733158
# User-Agent: Some/User-Agent String
```

**curl example**

Here is an example of integrating cloudflare-scrape with curl. As you can see, all you have to do is pass the cookies and user-agent to curl.

```python
import subprocess
import cfscrape

# With get_tokens() cookie dict:

# tokens, user_agent = cfscrape.get_tokens("http://somesite.com")
# cookie_arg = "cf_clearance=%s; __cfduid=%s" % (tokens["cf_clearance"], tokens["__cfduid"])

# With get_cookie_string() cookie header; recommended for curl and similar external applications:

cookie_arg, user_agent = cfscrape.get_cookie_string("http://somesite.com")

# With a custom user-agent string you can optionally provide:

# ua = "Scraping Bot"
# cookie_arg, user_agent = cfscrape.get_cookie_string("http://somesite.com", user_agent=ua)

result = subprocess.check_output(["curl", "--cookie", cookie_arg, "-A", user_agent, "http://somesite.com"])
```

Trimmed down version. Prints page contents of any site protected with Cloudflare, via curl. (Warning: `shell=True` can be dangerous to use with `subprocess` in real code.)

```python
url = "http://somesite.com"
cookie_arg, user_agent = cfscrape.get_cookie_string(url)
cmd = "curl --cookie {cookie_arg} -A {user_agent} {url}"
print(subprocess.check_output(cmd.format(cookie_arg=cookie_arg, user_agent=user_agent, url=url), shell=True))
```
