import asyncio

from kestrel_gateway.config.settings import load_settings
from kestrel_gateway.server import KestrelGateway


async def main():
    settings = load_settings()
    gateway = KestrelGateway(settings)
    await gateway.server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
