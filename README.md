cloudflare-scrape
=================

A simple Python module to bypass Cloudflare's anti-bot page, implemented as a [Requests](https://github.com/kennethreitz/requests) adapter. Cloudflare changes their techniques periodically, so I will update this repo frequently.

This can be useful if you wish to scrape or crawl a website protected with Cloudflare. Cloudflare's anti-bot page currently just checks if the client supports Javascript, though they may add additional techniques in the future.

Due to Cloudflare continuously changing and hardening their protection page, `cloudflare-scrape` now uses **PyV8**, a wrapper around Google's V8 Javascript engine.

Note: This only works when regular Cloudflare anti-bots is enabled (the "Checking your browser before accessing..." loading page). If there is a reCAPTCHA challenge, you're out of luck. Thankfully, the Javascript check page is much more common.

For reference, this is the default message Cloudflare uses for these sorts of pages:

    Checking your browser before accessing website.com.

    This process is automatic. Your browser will redirect to your requested content shortly.

    Please allow up to 5 seconds…

Dependencies
============
* Python 2.6 - 2.7
* **[Requests](https://github.com/kennethreitz/requests)** >= 2.0
* **[PyV8](https://code.google.com/p/pyv8/)**

There are a few different ways to install PyV8, depending on your OS and if you want to compile it from source or use a pre-compiled binary. Use whatever works best for you.

Usage
====
The simplest way to use cfscrape is by calling `create_scraper()`.

    import cfscrape

    scraper = cfscrape.create_scraper() # returns a requests.Session object
    print scraper.get("http://somesite.com").text # => "<!DOCTYPE html><html><head>..."

You use cloudflare-scrape exactly the same way you use Requests. Consult [Requests' documentation](http://docs.python-requests.org/en/latest/user/quickstart/) for more information.

This module is implemented as an adapter, so you can also mount it to an existing requests.Session object if you wish.

    import requests
    import cfscrape

    sess = requests.session()
    sess.headers = {"X-Some-Custom-Header": "Some Value"}
    sess.mount("http://", cfscrape.CloudflareAdapter())

Note that `create_scraper()` is merely a convenience function that creates a new Requests session and mounts the adapter to it. It will also do the mounting for you if you pass it an existing session.

    import requests
    import cfscrape

    sess = requests.session()
    sess.headers = {"X-Some-Custom-Header": "Some Value"}
    sess = cfscrape.create_scraper(sess) # this just runs sess.mount(...)

