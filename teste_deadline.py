from app.coletor import PortalBaseBrowser

id_anuncio = "451315"

with PortalBaseBrowser() as portal:
    portal.inicializar()

    detalhe = portal.obter_detalhe(id_anuncio)

    print("\n===== CAMPOS DEADLINE =====")

    for chave, valor in detalhe.items():
        if (
            "deadline" in chave.lower()
            or "proposal" in chave.lower()
            or "date" in chave.lower()
        ):
            print(chave, "=", valor)

    print("\n===== proposalDeadline =====")
    print(detalhe.get("proposalDeadline"))
