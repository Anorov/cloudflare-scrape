# -*- coding: utf-8 -*-
import ssl
import urllib3
import pytest

from cfscrape import CloudflareAdapter


@pytest.fixture
def adapter():
    adapter = CloudflareAdapter()
    yield adapter
    adapter.close()


def test_create_adapter(adapter):
    assert isinstance(adapter, urllib3.HTTPAdapter)


def test_get_connection(adapter):
    conn = adapter.get_connection("https://127.0.0.1", None)

    assert isinstance(conn.conn_kw, dict)
    assert "ssl_context" in conn.conn_kw
    ssl_context = conn.conn_kw["ssl_context"]

    # This should be ssl.SSLContext unless pyOpenSSL is installed.
    # If pyOpenSSL is injected into urllib3, this should still work.
    assert isinstance(ssl_context, (ssl.SSLContext, urllib3.contrib.pyopenssl.PyOpenSSLContext))


def test_set_ciphers(adapter):
    # Reinitialize the pool manager with a different context
    ctx = ssl.create_default_context()
    adapter.init_poolmanager(1, 1, ssl_context=ctx)

    # Check to see if the context remains the same without error
    conn = adapter.get_connection('https://127.0.0.1', None)
    assert isinstance(conn.conn_kw, dict)
    assert conn.conn_kw["ssl_context"] is ctx
