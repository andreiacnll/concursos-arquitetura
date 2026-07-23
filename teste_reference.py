from app.coletor import PortalBaseBrowser

with PortalBaseBrowser() as portal:
    portal.inicializar()

    detalhe = portal.obter_detalhe("451969")

    print("===== CAMPOS POSSÍVEIS =====")

    for chave, valor in detalhe.items():
        if (
            "ref" in chave.lower()
            or "link" in chave.lower()
            or "url" in chave.lower()
            or "pdf" in chave.lower()
            or "dr" in chave.lower()
        ):
            print(chave, "=", valor)
