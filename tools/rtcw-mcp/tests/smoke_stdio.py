"""Start server.py over stdio, list tools, call the read-only ones. Run: .venv/bin/python tests/smoke_stdio.py"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parents[1]


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")], cwd=str(HERE))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            for name, args in (("game_status", {}), ("list_maps", {}), ("known_spots", {"map": "trainyard"})):
                res = await s.call_tool(name, args)
                print(name, "->", res.content[0].text[:300].replace("\n", " "))
            res = await s.call_tool("screenshot", {"map": "bad/map", "spots": ["1 2 3 4 5"]})
            print("bad map ->", res.content[0].text[:200].replace("\n", " "))
            print("resources:", [str(x.uri) for x in (await s.list_resources()).resources])


asyncio.run(main())
