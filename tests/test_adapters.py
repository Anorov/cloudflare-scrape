# -*- coding: utf-8 -*-

import ssl
import sure  # noqa
import urllib3

from cfscrape import CloudflareAdapter


class TestCloudflareAdapter:

    def test_create_adapter(self):
        adapter = CloudflareAdapter()
        adapter.should.be.a("requests.adapters.HTTPAdapter")
        adapter.close()

    def test_get_connection(self):
        adapter = CloudflareAdapter()

        conn = adapter.get_connection("https://127.0.0.1", None)

        conn.conn_kw.should.be.a("dict")
        conn.conn_kw.should.have.key("ssl_context")
        ssl_context = conn.conn_kw["ssl_context"]

        # This should be ssl.SSLContext unless pyOpenSSL is installed.
        # If pyOpenSSL is injected into urllib3, this should still work.
        try:
            assert isinstance(ssl_context, urllib3.contrib.pyopenssl.PyOpenSSLContext)
        except Exception:
            assert isinstance(ssl_context, ssl.SSLContext)

        adapter.close()

    def test_set_ciphers(self):
        adapter = CloudflareAdapter()

        # Reinitialize the pool manager with a different context
        ctx = ssl.create_default_context()
        adapter.init_poolmanager(1, 1, ssl_context=ctx)
        # Check to see if the context remains the same without error
        conn = adapter.get_connection('https://127.0.0.1', None)
        conn.conn_kw.should.be.a("dict")
        assert conn.conn_kw["ssl_context"] is ctx

        adapter.close()
