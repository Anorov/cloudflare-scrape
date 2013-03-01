cloudflare-scrape
=================

A simple Python function to bypass Cloudflare's anti-bot page. They change their method periodically, so I will update this repo frequently.

This can be useful if you wish to scrape or crawl a website protected with Cloudflare. You can also expand the function to return the `Session()` object (`sess` in this case) and use it to crawl the site further.

Requires Python 2.5+ and the Python `requests` library and `lxml` library.

Note: This only works when regular Cloudflare anti-bots is enabled (the "please wait 5 seconds..." loading page). If there is a reCAPTCHA challenge, you're out of luck.


Usage
====
    from cfscrape import grab_cloudflare

    url = "http://somesite.com"
    print grab_cloudflare(url)
