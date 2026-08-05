from pathlib import Path
from playwright.sync_api import sync_playwright


URL = (
    "https://www.base.gov.pt/Base4/pt/detalhe/"
    "?type=anuncios&id=451655"
)


def main():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        pedidos = []
        respostas = []

        def guardar_pedido(request):
            url = request.url
            pedidos.append(url)

        page.on(
            "request",
            guardar_pedido
        )

        def guardar_resposta(response):
            try:
                url = response.url
                tipo = response.headers.get("content-type", "")

                if (
                    "json" in tipo.lower()
                    or "api" in url.lower()
                    or "screenservices" in url.lower()
                    or "dataaction" in url.lower()
                ):
                    respostas.append(url)

            except Exception:
                pass

        page.on(
            "response",
            guardar_resposta
        )

        print("Abrir BASE...")
        response = page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        print("URL FINAL:")
        print(page.url)

        print("STATUS:")
        print(response.status if response else None)

        page.screenshot(
            path="base_451655.png",
            full_page=True
        )

        Path("base_451655.html").write_text(
            page.content(),
            encoding="utf-8"
        )

        print("HTML e screenshot guardados")

        print("\nBOTÕES:")
        botoes = page.locator("button").evaluate_all(
            """
            els => els.map(
                e => e.innerText
            )
            """
        )

        for b in botoes:
            if b.strip():
                print("-", b.strip())


        print("\nTEXTOS COM PEÇAS:")
        elementos = page.locator("text=/peças|pecas/i").all_inner_texts()

        for e in elementos:
            print("-", e)

        print("\nPEDIDOS RELACIONADOS:")
        for url in pedidos:
            print(url)

        print("\nRESPOSTAS JSON/API:")
        for url in respostas:
            print(url)

        texto = page.content()

        print("Página carregada")
        
        palavras = [
            "Peças do procedimento",
            "Ligação para peças do procedimento",
            "pecas",
            "download",
            ".zip",
        ]

        for palavra in palavras:
            if palavra.lower() in texto.lower():
                print("Encontrado:", palavra)


        links = page.locator("a").evaluate_all(
            """
            els => els.map(
                e => ({
                    texto:e.innerText,
                    href:e.href
                })
            )
            """
        )


        for link in links:

            texto = (
                link["texto"] or ""
            ).lower()

            href = (
                link["href"] or ""
            ).lower()

            if (
                "peça" in texto
                or "peca" in texto
                or "download" in texto
                or ".zip" in href
            ):
                print("\nPOSSÍVEL LINK:")
                print(link)


        browser.close()



if __name__ == "__main__":
    main()

