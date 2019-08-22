# -*- coding: utf-8 -*-

import pytest
import cfscrape
import requests
import re
import os
import ssl
import responses
import subprocess

from sure import expect
from . import challenge_responses, recaptcha_responses, requested_page, url, \
    cloudflare_cookies, DefaultResponse, ChallengeResponse, fixtures, \
    cfscrape_kwargs


class TestCloudflareScraper:

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031', redirect_to=url)
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

    @responses.activate
    def test_js_challenge_unable_to_identify(self):
        body = fixtures('js_challenge_10_04_2019.html')
        body = body.replace(b'setTimeout', b'')

        responses.add(ChallengeResponse(url=url, body=body))

        scraper = cfscrape.create_scraper(**cfscrape_kwargs)
        message = re.compile(r'Unable to identify Cloudflare IUAM Javascript')
        scraper.get.when.called_with(url) \
            .should.have.raised(ValueError, message)

    @responses.activate
    def test_js_challenge_unexpected_answer(self):
        body = fixtures('js_challenge_10_04_2019.html')
        body = body.replace(b'\'; 121\'', b'a.value = "foobar"')

        responses.add(ChallengeResponse(url=url, body=body))

        scraper = cfscrape.create_scraper(**cfscrape_kwargs)
        message = re.compile(r'Cloudflare IUAM challenge returned unexpected answer')
        scraper.get.when.called_with(url) \
            .should.have.raised(ValueError, message)

    @responses.activate
    def test_js_challenge_missing_pass(self):
        body = fixtures('js_challenge_10_04_2019.html')
        body = body.replace(b'name="pass"', b'')

        responses.add(ChallengeResponse(url=url, body=body))

        scraper = cfscrape.create_scraper(**cfscrape_kwargs)
        message = re.compile(r'Unable to parse .* pass is missing from challenge form')
        scraper.get.when.called_with(url) \
            .should.have.raised(ValueError, message)

    def test_js_challenge_subprocess_unknown_error(self, caplog):
        def test(self, **kwargs):
            __Popen = subprocess.Popen

            # Temporarily disable this method to generate an exception
            subprocess.Popen = None

            try:
                scraper = cfscrape.CloudflareScraper(**kwargs)
                scraper.get.when.called_with(url) \
                    .should.have.raised(TypeError)
                caplog.text.should.match(re.compile(r'Error executing Cloudflare IUAM Javascript'))
            finally:
                subprocess.Popen = __Popen

        challenge_responses(
            filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031'
        )(test)(self)

    def test_js_challenge_subprocess_system_error(self, caplog):
        def test(self, **kwargs):
            __Popen = subprocess.Popen

            # Temporarily Mock subprocess method to raise an OSError
            def mock(*args, **kwargs):
                raise OSError('System Error')

            subprocess.Popen = mock

            try:
                scraper = cfscrape.CloudflareScraper(**kwargs)
                scraper.get.when.called_with(url) \
                    .should.have.raised(OSError, re.compile(r'System Error'))
                caplog.text.should.equal('')
            finally:
                subprocess.Popen = __Popen

        challenge_responses(
            filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031'
        )(test)(self)

    def test_js_challenge_subprocess_non_zero(self, caplog):
        def test(self, **kwargs):
            __Popen = subprocess.Popen

            # Temporarily Mock subprocess method to return non-zero exit code
            def mock(*args, **kwargs):
                def node(): pass
                node.communicate = lambda: ('stdout', 'stderr')
                node.returncode = 1
                return node

            subprocess.Popen = mock

            try:
                scraper = cfscrape.CloudflareScraper(**kwargs)
                message = re.compile(r'non-zero exit status')
                scraper.get.when.called_with(url) \
                    .should.have.raised(subprocess.CalledProcessError, message)
                caplog.text.should.match(re.compile(r'Error executing Cloudflare IUAM Javascript'))
                caplog.text.should_not.match(re.compile(r'Outdated Node.js detected'))
            finally:
                subprocess.Popen = __Popen

        challenge_responses(
            filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031'
        )(test)(self)

    def test_js_challenge_outdated_node(self, caplog):
        def test(self, **kwargs):
            __Popen = subprocess.Popen

            # Temporarily Mock subprocess method to return non-zero exit code
            def mock(*args, **kwargs):
                def node(): pass
                node.communicate = lambda: ('stdout', 'Outdated Node.js detected')
                node.returncode = 1
                return node

            subprocess.Popen = mock

            try:
                scraper = cfscrape.CloudflareScraper(**kwargs)
                message = re.compile(r'non-zero exit status')
                scraper.get.when.called_with(url) \
                    .should.have.raised(subprocess.CalledProcessError, message)
                caplog.text.should_not.match(re.compile(r'Error executing Cloudflare IUAM Javascript'))
                caplog.text.should.match(re.compile(r'Outdated Node.js detected'))
            finally:
                subprocess.Popen = __Popen

        challenge_responses(
            filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031'
        )(test)(self)

    @challenge_responses(filename='js_challenge_10_04_2019.html', jschl_answer='18.8766915031')
    def test_js_challenge_environment_error(self, **kwargs):
        __path = os.environ['PATH']
        # Temporarily unset PATH to hide Node.js
        os.environ['PATH'] = ''
        try:
            scraper = cfscrape.CloudflareScraper(**kwargs)
            message = re.compile(r'Missing Node.js runtime')
            scraper.get.when.called_with(url) \
                .should.have.raised(EnvironmentError, message)
        finally:
            os.environ['PATH'] = __path

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

    @responses.activate
    def test_get_tokens_request_error(self, caplog):
        # get_tokens doesn't accept the delay kwarg.
        kwargs = cfscrape_kwargs.copy()
        kwargs.pop('delay', None)

        responses.add(DefaultResponse(url=url, status=500))
        cfscrape.get_tokens.when.called_with(url, **kwargs) \
                .should.have.raised(requests.HTTPError)
        caplog.text.should.match(re.compile(r'Could not collect tokens'))

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

    def test_create_scraper_with_session(self):
        session = requests.session()
        session.headers = {'foo': 'bar'}
        session.data = None

        scraper = cfscrape.create_scraper(sess=session)
        scraper.headers.should.equal(session.headers)
        scraper.should_not.have.property('data')

        session.data = {'bar': 'foo'}
        scraper = cfscrape.create_scraper(sess=session)
        scraper.data.should.equal(session.data)
