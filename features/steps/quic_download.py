import asyncio
import logging
from types import SimpleNamespace

from behave import *

from istream_player.quic.client import QuicClientImpl
from istream_player.quic.event_parser import H3EventParserImpl

use_step_matcher("re")


@given("A QUIC Client")
def step_impl(context):
    """
    Parameters
    ----------
    context : behave.runner.Context
    """
    context.args = SimpleNamespace()
    context.args.quic_client = QuicClientImpl([], H3EventParserImpl())


@when("The client is asked to get content from an URL")
def step_impl(context):
    """
    Parameters
    ----------
    context : behave.runner.Context
    """
    # context.args.url = "https://lab.yangliu.xyz/videos/BBB/output.mpd"
    context.args.url1 = "https://oracle1.jace.website/videos/BBB/chunk-stream0-00010.m4s"
    context.args.url2 = "https://oracle1.jace.website/videos/BBB/chunk-stream0-00011.m4s"


@then("The client get it")
def step_impl(context):
    """
    Parameters
    ----------
    context : behave.runner.Context
    """
    logging.basicConfig(level=logging.DEBUG)
    quic_client: QuicClientImpl = context.args.quic_client

    # asyncio.run(quic_client.get(context.args.url))

    async def foo():
        await quic_client.download(context.args.url1)
        await quic_client.download(context.args.url2)
        await quic_client.wait_complete(context.args.url1)
        await quic_client.wait_complete(context.args.url2)

    asyncio.run(foo())
