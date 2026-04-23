import asyncio
import edge_tts
import threading

async def test():
    c = edge_tts.Communicate('hello', 'en-US-AvaNeural')
    await c.save('test2.mp3')
    print('done in async thread')

def thread_worker():
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(test())
    new_loop.close()

t = threading.Thread(target=thread_worker)
t.start()
t.join()
