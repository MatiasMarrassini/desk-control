"""Bucle asyncio en un hilo aparte: ahí vive todo el Bluetooth, así la ventana nunca se congela."""
import asyncio
import concurrent.futures
import threading


class BucleAsync:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._hilo = threading.Thread(target=self._correr, name="ble", daemon=True)

    def _correr(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def iniciar(self) -> None:
        self._hilo.start()

    def ejecutar(self, coro) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def detener(self, timeout: float = 5.0) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._hilo.join(timeout)
