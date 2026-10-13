from webview.util import is_local_url

from widget import main


def test_la_interfaz_se_carga_sin_servidor_http():
    # pywebview levanta un servidor HTTP local para rutas "locales"; con file:// no abre ningún puerto.
    url = main.url_interfaz()
    assert url.startswith("file:///") and url.endswith("/widget/ui/index.html")
    assert is_local_url(url) is False
