cloudflare-scrape
=================

A simple Python function to bypass Cloudflare's anti-bot page. They change their method periodically, so I will update this repo frequently.

This can be useful if you wish to scrape or crawl a website protected with Cloudflare. You can also expand the function to return the `Session` object (`sess` in this case) and use it to crawl the site further.

Due to Cloudflare continuously changing and hardening their protection page, `cloudflare-scrape` now uses **PyV8**, a wrapper around Google's V8 Javascript engine.

Note: This only works when regular Cloudflare anti-bots is enabled (the "please wait 5 seconds..." loading page). If there is a reCAPTCHA challenge, you're out of luck.

Dependencies
============
* **[requests](https://github.com/kennethreitz/requests)** >= 2.0
* **[PyV8](https://code.google.com/p/pyv8/)**

There are a few different ways to install PyV8, depending on your OS and if you want to compile it from source or use a pre-compiled binary. Use whatever works best for you.

Usage
====
    from cfscrape import grab_cloudflare

    url = "http://somesite.com"
    print grab_cloudflare(url) # => "<html><head>..."
