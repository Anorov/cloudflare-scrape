---
name: Bug report template
about: For reporting issues and errors
title: ''
labels: bug
assignees: ''

---

Before creating an issue, first upgrade cfscrape with `pip install -U cfscrape` and see if you're still experiencing the problem. Please also confirm your Node version (`node --version` or `nodejs --version`) is version 10 or higher.

Make sure the website you're having issues with is actually using anti-bot protection by Cloudflare and not a competitor like Imperva Incapsula or Sucuri. And if you're using an anonymizing proxy, a VPN, or Tor, Cloudflare often flags those IPs and may block you or present you with a captcha as a result.

Please **confirm the following statements and check the boxes** before creating an issue:

- [ ] I've upgraded cfscrape with `pip install -U cfscrape`
- [ ] I'm using Node version 10 or higher
- [ ] The site protection I'm having issues with is from Cloudflare
- [ ] I'm not using Tor, a VPN, or an anonymizing proxy

## Python version number

Run `python --version` and paste the output below:

```

```

## cfscrape version number

Run `pip show cfscrape` and paste the output below:

```

```

## Code snippet involved with the issue

```

```

## Complete exception and traceback

(*If the problem doesn't involve an exception being raised, leave this blank*)

```

```

## URL of the Cloudflare-protected page

[LINK GOES HERE]

## URL of Pastebin/Gist with HTML source of protected page

[LINK GOES HERE]
