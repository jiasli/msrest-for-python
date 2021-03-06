#--------------------------------------------------------------------------
#
# Copyright (c) Microsoft Corporation. All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#--------------------------------------------------------------------------
import concurrent.futures

from requests.adapters import HTTPAdapter

from msrest.universal_http import (
    ClientRequest
)
from msrest.universal_http.requests import (
    BasicRequestsHTTPSender,
    RequestsHTTPSender,
    RequestHTTPSenderConfiguration
)

def test_session_callback():

    cfg = RequestHTTPSenderConfiguration()
    with RequestsHTTPSender(cfg) as driver:

        def callback(session, global_config, local_config, **kwargs):
            assert session is driver.session
            assert global_config is cfg
            assert local_config["test"]
            my_kwargs = kwargs.copy()
            my_kwargs.update({'used_callback': True})
            return my_kwargs

        cfg.session_configuration_callback = callback

        request = ClientRequest('GET', 'http://127.0.0.1/')
        output_kwargs = driver._configure_send(request, **{"test": True})
        assert output_kwargs['used_callback']

def test_max_retries_on_default_adapter():
    # max_retries must be applied only on the default adapters of requests
    # If the user adds its own adapter, don't touch it
    cfg = RequestHTTPSenderConfiguration()
    max_retries = cfg.retry_policy()

    with RequestsHTTPSender(cfg) as driver:
        request = ClientRequest('GET', '/')
        driver.session.mount('"http://127.0.0.1/"', HTTPAdapter())

        driver._configure_send(request)
        assert driver.session.adapters["http://"].max_retries is max_retries
        assert driver.session.adapters["https://"].max_retries is max_retries
        assert driver.session.adapters['"http://127.0.0.1/"'].max_retries is not max_retries


def test_threading_basic_requests():
    # Basic should have the session for all threads, it's why it's not recommended
    sender = BasicRequestsHTTPSender()
    main_thread_session = sender.session

    def thread_body(local_sender):
        # Should be the same session
        assert local_sender.session is main_thread_session

        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(thread_body, sender)
        assert future.result()

def test_threading_cfg_requests():
    cfg = RequestHTTPSenderConfiguration()

    # The one with conf however, should have one session per thread automatically
    sender = RequestsHTTPSender(cfg)
    main_thread_session = sender.session

    # Check that this main session is patched
    assert main_thread_session.resolve_redirects.is_msrest_patched

    def thread_body(local_sender):
        # Should have it's own session
        assert local_sender.session is not main_thread_session
        # But should be patched as the main thread session
        assert local_sender.session.resolve_redirects.is_msrest_patched
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(thread_body, sender)
        assert future.result()
