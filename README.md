cloudflare-scrape
=================

A simple Python module to bypass Cloudflare's anti-bot page (also known as "I'm Under Attack Mode", or IUAM), implemented as a [Requests](https://github.com/kennethreitz/requests) adapter. Cloudflare changes their techniques periodically, so I will update this repo frequently.

This can be useful if you wish to scrape or crawl a website protected with Cloudflare. Cloudflare's anti-bot page currently just checks if the client supports Javascript, though they may add additional techniques in the future.

Due to Cloudflare continually changing and hardening their protection page, cloudflare-scrape now uses **[PyExecJS](https://github.com/doloopwhile/PyExecJS)**, a Python wrapper around multiple Javascript runtime engines. This allows the script to easily and effectively impersonate a regular web browser without explicitly parsing and converting Cloudflare's Javascript obfuscation techniques.

The only supported Javascript engines at this time are Node.js and V8 (with or without the PyV8 module). This is due to potential security concerns with the other engines.

Note: This only works when regular Cloudflare anti-bots is enabled (the "Checking your browser before accessing..." loading page). If there is a reCAPTCHA challenge, you're out of luck. Thankfully, the Javascript check page is much more common.

For reference, this is the default message Cloudflare uses for these sorts of pages:

    Checking your browser before accessing website.com.

    This process is automatic. Your browser will redirect to your requested content shortly.

    Please allow up to 5 seconds...

Any script using cloudflare-scrape will sleep for 5 seconds for the first visit to any site with Cloudflare anti-bots enabled, though no delay will occur after the first request.

Warning
======

This script will execute arbitrary Javascript code, which can potentially be harmful in some runtime environments. Precautions have been taken to try and execute the code in a sandboxed manner (for example, when Node.js's runtime is in use, the `vm` module is leveraged, which will prevent most attacks), but I cannot 100% guarantee safety when scraping a page that has been maliciously crafted to specifically exploit cloudflare-scrape. Attacks could range from a simple denial of service (a `while(true){}` keeping your script stuck forever) all the way to arbitrary code execution on the machine (though measures are taken in an attempt to prevent this).

As I have not fully assessed the capabilities of alternative runtimes, like Spidermonkey and Phantom.js, to execute arbitrary code, only Node and V8 can be used at this time. I may add support for other engines if I can confirm there are no security risks.

Despite these safeguards, you should use this module with caution. I would also recommend using a VM to perform your scraping, if possible.

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
* Node.js or V8. PyV8 is optional. I recommend Node.js. You can install it with `apt-get install nodejs` on Ubuntu, [or by reading Node.js's installation instructions](https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager#debian-and-ubuntu-based-linux-distributions) otherwise.

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

scraper = cfscrape.create_scraper() # returns a requests.Session object
print scraper.get("http://somesite.com").content # => "<!DOCTYPE html><html><head>..."
```

That's it. Any requests made from this session object to websites protected by Cloudflare anti-bot will be handled automatically. Websites not using Cloudflare will be treated normally. You don't need to configure or call anything further, and you can effectively treat all websites as if they're not protected with anything.

You use cloudflare-scrape exactly the same way you use Requests. Just instead of calling `requests.get()` or `requests.post()`, you call `scraper.get()` or `scraper.post()`. Consult [Requests' documentation](http://docs.python-requests.org/en/latest/user/quickstart/) for more information.

### Integration

It's easy to integrate cloudflare-scrape with other applications and tools. Cloudflare uses 2 cookies as tokens: one to verify you made it past their challenge page and one to track your session. Simply send along both of these cookies with any HTTP request and you will bypass the challenge page. Both cookies will eventually expire, so be sure to have code to handle that case and to re-acquire the cookies.

To retrieve just the cookies, use `cfscrape.get_tokens()`. (Note this function is a top-level function in the module, and is not a method of the scraper. So use `cfscrape.get_tokens()`, do not use `scraper.get_tokens()`.)

These functions return a tuple of `(cookie_dict, user_agent_string)`. **You must use the same user-agent for obtaining the tokens and for making requests with those tokens, otherwise Cloudflare will flag you as a bot.** That means you have to pass the returned `user_agent_string` to whatever script or service you are passing the tokens to, and it must use that passed user-agent when it makes HTTP requests.

You may optionally specify a custom user-agent with `cfscrape.get_tokens("User-Agent Here")`. A user-agent spoofing Firefox on Linux will be used by default.

```python
import cfscrape

tokens, user_agent = cfscrape.get_tokens("http://somesite.com")
print tokens
# => {'cf_clearance': 'c8f913c707b818b47aa328d81cab57c349b1eee5-1426733163-3600', '__cfduid': 'dd8ec03dfdbcb8c2ea63e920f1335c1001426733158'}
```

There is also a convenience function for returning the tokens as a string for use as a Cookie HTTP header value: `get_cookie_string()`.

If you were crafting an HTTP request manually, you could do something like:

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

Here is an example of integrating cloudflare-scrape with curl. As you can see, all you have to do is pass the cookies to curl.

```python
import subprocess
import cfscrape

# Manually
# tokens, user_agent = cfscrape.get_tokens("http://somesite.com")
# cookie_arg = "cf_clearance=%s; __cfduid=%s" % (tokens["cf_clearance"], tokens["__cfduid"])

# With convenience function
cookie_arg, user_agent = cfscrape.get_cookie_string("http://somesite.com")

result = subprocess.check_output(["curl", "--cookie", cookie_arg, "-A", user_agent, "http://somesite.com"])
```

### Existing Requests sessions

This module is implemented as a Requests adapter, so you can also mount it to an existing `requests.Session` object if you wish.

```python
import requests
import cfscrape

sess = requests.session()
sess.headers = {"X-Some-Custom-Header": "Some Value"} # You could also have done `scraper.headers = ...` if using create_scraper()
sess.mount("http://", cfscrape.CloudflareAdapter())
sess.mount("https://", cfscrape.CloudflareAdapter())
```

Note that `create_scraper()` is merely a convenience function that creates a new Requests session and mounts the adapter to it. It will also do the mounting for you if you pass it an existing session.

```python
import requests
import cfscrape

sess = requests.session()
sess.headers = {"X-Some-Custom-Header": "Some Value"}
sess = cfscrape.create_scraper(sess) # this just runs sess.mount(...)
```
