# -*- coding: utf-8 -*-

import re

from base64 import b64encode
from requests.compat import urlparse
from collections import OrderedDict

from .exceptions import CloudflareError
from .utils import BUG_REPORT


class CloudflareChallenge(object):

    def __init__(self, response, delay=None):
        self.delay = delay
        self.domain = urlparse(response.url).netloc

        # Convenience attribute
        response.challenge = self

        html = response.text

        try:
            js, ms = re.search(
                r"setTimeout\(function\(\){\s*(var "
                r"s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value\s*=.+?)\r?\n"
                r"(?:[^{<>]*},\s*(\d{4,}))?",
                html,
            ).groups()

            self.js = js

            # The challenge requires `document.getElementById` to get this content.
            # Future proofing would require escaping newlines and double quotes
            match = re.search(r"<div(?: [^<>]*)? id=\"cf-dn.*?\">([^<>]*)", html)
            self.innerHTML = match.group(1) if match else ""

            # Use the provided delay, parsed delay, or default to 8 secs
            if self.delay is None:
                self.delay = float(ms) / 1000 if ms else 8
        except Exception as e:
            msg = "Unable to identify Cloudflare IUAM Javascript on website. %s\n%s"
            msg %= (e.message, BUG_REPORT)
            raise CloudflareError(msg, response=response)

        self.prepare()

        try:
            self.form = OrderedDict(
                re.findall(r'name="(s|jschl_vc|pass)"(?: [^<>]*)? value="(.+?)"', html)
            )

            for k in ("jschl_vc", "pass"):
                if k not in self.form:
                    raise ValueError("%s is missing from challenge form" % k)
        except Exception as e:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            msg = "Unable to parse Cloudflare anti-bot IUAM page: %s\n%s"
            msg %= (e.message, BUG_REPORT)
            raise CloudflareError(msg, response=response)

    def prepare(self):
        # Prefix the JS challenge with a fake document object.
        # Interpolate the domain, div contents, and JS challenge.
        # The `a.value` to be returned is tacked onto the end.
        template = """
            var document = {
              createElement: function () {
                return { firstChild: { href: "http://%s/" } }
              },
              getElementById: function () {
                return {"innerHTML": "%s"};
              }
            };

            %s; a.value
        """

        self.prepared_js = template % (
            self.domain,
            self.innerHTML,
            self.js
        )

    def to_base64(self):
        # Encode the challenge for security while preserving quotes and spacing.
        return b64encode(self.prepared_js.encode("utf-8")).decode("ascii")
