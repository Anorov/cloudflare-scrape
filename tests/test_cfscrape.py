# -*- coding: utf-8 -*-

import pytest
import cfscrape
import requests
import re
import ssl

from sure import expect
from . import challenge_responses, recaptcha_responses, requested_page, url, \
    cloudflare_cookies, server_error_response


class TestCloudflareScraper:

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_js_challenge_10_04_2019(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @challenge_responses(filename='js_challenge_21_03_2019.html', jschl_answer='13.0802397598')
    def test_js_challenge_21_03_2019(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @challenge_responses(filename='js_challenge_13_03_2019.html', jschl_answer='38.5879578333')
    def test_js_challenge_13_03_2019(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @challenge_responses(filename='js_challenge_03_12_2018.html', jschl_answer='10.66734594')
    def test_js_challenge_03_12_2018(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @challenge_responses(filename='js_challenge_09_06_2016.html', jschl_answer='6648')
    def test_js_challenge_09_06_2016(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @pytest.mark.skip(reason='Unable to identify Cloudflare IUAM Javascript on website.')
    @challenge_responses(filename='js_challenge_21_05_2015.html', jschl_answer='649')
    def test_js_challenge_21_05_2015(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        expect(scraper.get(url).content).to.equal(requested_page)

    @recaptcha_responses(filename='cf_recaptcha_15_04_2019.html')
    def test_cf_recaptcha_15_04_2019(self, **kwargs):
        scraper = cfscrape.CloudflareScraper(**kwargs)
        message = re.compile(r'captcha challenge presented')
        scraper.get.when.called_with(url) \
            .should.have.raised(cfscrape.CloudflareCaptchaError, message)

        v = ssl.OPENSSL_VERSION_NUMBER
        ssl.OPENSSL_VERSION_NUMBER = 0x0090581f
        try:
            scraper = cfscrape.CloudflareScraper(**kwargs)
            message = re.compile(r'OpenSSL version is lower than 1.1.1')
            scraper.get.when.called_with(url) \
                .should.have.raised(cfscrape.CloudflareCaptchaError, message)
        finally:
            ssl.OPENSSL_VERSION_NUMBER = v

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_get_cookie_string(self, **kwargs):
        # get_cookie_string doesn't accept the delay kwarg.
        # Set the delay in the Test class to speed up this test.
        delay = kwargs.pop('delay', 0.1)
        expected_ua = kwargs.setdefault('user_agent', 'custom-ua')

        cfduid, cf_clearance = cloudflare_cookies()

        # Use a class to workaround a `responses` bug where
        # cookies aren't mocked correctly.
        class Test(cfscrape.CloudflareScraper):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('delay', delay)
                super(Test, self).__init__(*args, **kwargs)

                self.cookies.set('__cfduid', cfduid)
                self.cookies.set('cf_clearance', cf_clearance)

        result = Test.get_cookie_string(url, **kwargs)
        result.should.be.a('tuple')
        result.should.have.length_of(2)

        cookie_arg, user_agent = result

        cookie_arg.should.be.a('str')
        cookie_arg.should.contain('cf_clearance=%s' % cf_clearance.value)
        cookie_arg.should.contain('__cfduid=%s' % cfduid.value)

        user_agent.should.equal(expected_ua)

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_get_tokens(self, **kwargs):
        # get_tokens doesn't accept the delay kwarg.
        # Set the delay in the Test class to speed up this test.
        delay = kwargs.pop('delay', 0.1)
        expected_ua = kwargs.setdefault('user_agent', 'custom-ua')

        cfduid, cf_clearance = cloudflare_cookies()

        # Use a class to workaround a `responses` bug where
        # cookies aren't mocked correctly.
        class Test(cfscrape.CloudflareScraper):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('delay', delay)
                super(Test, self).__init__(*args, **kwargs)

                self.cookies.set('__cfduid', cfduid)
                self.cookies.set('cf_clearance', cf_clearance)

        tokens = Test.get_tokens(url, **kwargs)
        tokens.should.be.a('tuple')
        tokens.should.have.length_of(2)

        cookies, user_agent = tokens

        cookies.should.be.a('dict')
        cookies.should.equal({
            'cf_clearance': cf_clearance.value,
            '__cfduid': cfduid.value
        })

        user_agent.should.equal(expected_ua)

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_get_tokens_missing_cookie(self, **kwargs):
        # get_tokens doesn't accept the delay kwarg.
        delay = kwargs.pop('delay', 0.1)

        # Use derived class to set delay and test without cookies
        class Test(cfscrape.CloudflareScraper):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('delay', delay)
                super(Test, self).__init__(*args, **kwargs)

        message = re.compile(r'Unable to find Cloudflare cookies')
        Test.get_tokens.when.called_with(url, **kwargs) \
            .should.have.raised(ValueError, message)

    @server_error_response
    def test_get_tokens_request_error(self, **kwargs):
        # get_tokens doesn't accept the delay kwarg.
        kwargs.pop('delay', None)
        cfscrape.get_tokens.when.called_with(url, **kwargs) \
                .should.have.raised(requests.HTTPError)

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_cloudflare_is_bypassed(self, **kwargs):
        # Use a class to workaround a `responses` bug where
        # cookies aren't mocked correctly.
        class Test(cfscrape.CloudflareScraper):
            def __init__(self, *args, **kwargs):
                super(Test, self).__init__(*args, **kwargs)

                cf_clearance = cloudflare_cookies()[1]
                self.cookies.set('cf_clearance', cf_clearance)

        scraper = Test(**kwargs)
        scraper.cloudflare_is_bypassed(url).should.be.ok
