import asyncio
import edge_tts

async def test():
    c = edge_tts.Communicate('hello', 'en-US-AvaNeural')
    await c.save('test.mp3')
    print('done')

asyncio.run(test())
