import asyncio

from mcp.server.stdio import stdio_server

from kestrel_gateway.config.settings import load_settings
from kestrel_gateway.server import KestrelGateway


async def main():
    settings = load_settings()
    gateway = KestrelGateway(settings)

    async with stdio_server() as (read_stream, write_stream):
        await gateway.server.run(
            read_stream, write_stream,
            gateway.server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
