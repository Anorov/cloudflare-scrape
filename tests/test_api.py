# -*- coding: utf-8 -*-

import responses
import sure  # noqa

from . import DefaultResponse, requested_page as body, url
from cfscrape.api import request, get, head, post, patch, put, delete, options


class TestAPI:

    def test_request(self):
        request.should.be.callable

    @responses.activate
    def test_get(self):
        responses.add(DefaultResponse(url=url, method='GET', body=body))
        get(url).content.should.equal(body)

    @responses.activate
    def test_head(self):
        responses.add(DefaultResponse(url=url, method='HEAD'))
        head(url).content.should.equal(b'')

    @responses.activate
    def test_post(self):
        responses.add(DefaultResponse(url=url, method='POST', body=body))
        post(url).content.should.equal(body)

    @responses.activate
    def test_patch(self):
        responses.add(DefaultResponse(url=url, method='PATCH', body=body))
        patch(url).content.should.equal(body)

    @responses.activate
    def test_put(self):
        responses.add(DefaultResponse(url=url, method='PUT', body=body))
        put(url).content.should.equal(body)

    @responses.activate
    def test_delete(self):
        responses.add(DefaultResponse(url=url, method='DELETE', body=body))
        delete(url).content.should.equal(body)

    @responses.activate
    def test_options(self):
        responses.add(DefaultResponse(url=url, method='OPTIONS'))
        options(url).content.should.equal(b'')
