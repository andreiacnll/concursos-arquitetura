import unicodedata


EXPRESSOES_ARQUITETURA_EXPLICITA = [
    # Serviços de arquitetura
    "servicos de arquitetura",
    "servico de arquitetura",
    "prestacao de servicos de arquitetura",
    "aquisicao de servicos de arquitetura",
    "consultoria de arquitetura",

    # Projetos de arquitetura
    "projeto de arquitetura",
    "projetos de arquitetura",
    "projeto arquitetonico",
    "projetos arquitetonicos",
    "projeto arquitetural",
    "projetos arquiteturais",

    # Arquitetura e especialidades
    "arquitetura e especialidades",
    "arquitetura, engenharia e especialidades",
    "arquitetura e engenharia",
    "projeto de arquitetura e especialidades",
    "projetos de arquitetura e especialidades",
    "projeto de arquitetura e projetos de especialidades",
    "projetos de arquitetura e projetos de especialidades",
    "projeto geral de arquitetura e especialidades",

    # Projeto de execução
    "projeto de execucao de arquitetura",
    "projetos de execucao de arquitetura",
    "projeto de execucao de arquitetura e especialidades",
    "projetos de execucao de arquitetura e especialidades",

    # Revisão
    "revisao de projeto de arquitetura",
    "revisao de projetos de arquitetura",
    "revisao do projeto de arquitetura",
    "revisao dos projetos de arquitetura",
    "revisao de arquitetura e especialidades",
    "revisao de projetos de arquitetura e especialidades",

    # Concursos de conceção
    "concurso de concecao de arquitetura",
    "concurso de concepcao de arquitetura",
    "concurso de concecao arquitetonica",
    "concurso de concepcao arquitetonica",

    # Arquitetura de interiores
    "arquitetura de interiores",
    "projeto de arquitetura de interiores",
    "servicos de arquitetura de interiores",

    # Coordenação de projeto
    "coordenacao de projeto de arquitetura",
    "coordenacao do projeto de arquitetura",
    "coordenacao de projetos de arquitetura",
    "coordenacao dos projetos de arquitetura",
    "coordenacao de arquitetura e especialidades",
    "coordenacao dos projetos de arquitetura e especialidades",
]


EXPRESSOES_ACAO_DE_PROJETO = [
    "elaboracao de projeto",
    "elaboracao de projetos",
    "elaboracao do projeto",
    "elaboracao dos projetos",

    "desenvolvimento de projeto",
    "desenvolvimento de projetos",
    "desenvolvimento do projeto",
    "desenvolvimento dos projetos",

    "projeto de execucao",
    "projetos de execucao",

    "anteprojeto",
    "anteprojetos",

    "estudo previo",
    "estudos previos",

    "projeto base",
    "projetos base",

    "revisao de projeto",
    "revisao de projetos",
    "revisao do projeto",
    "revisao dos projetos",

    "concecao de projeto",
    "concecao do projeto",
    "concepcao de projeto",
    "concepcao do projeto",

    "coordenacao de projeto",
    "coordenacao de projetos",
    "coordenacao do projeto",
    "coordenacao dos projetos",

    "equipa projetista",
    "equipa de projeto",
]


EXPRESSOES_COORDENACAO_DE_PROJETO = [
    "coordenacao de projeto",
    "coordenacao de projetos",
    "coordenacao do projeto",
    "coordenacao dos projetos",
    "coordenacao de arquitetura",
    "coordenacao da arquitetura",
    "coordenacao de especialidades",
    "coordenacao das especialidades",
    "coordenacao entre arquitetura e especialidades",
    "coordenacao da equipa projetista",
    "coordenacao de equipa projetista",
]


EXPRESSOES_EXCLUSAO_FORTE = [
    # Informática
    "arquitetura de sistemas",
    "arquitetura de software",
    "arquitetura aplicacional",
    "arquitetura empresarial",
    "arquitetura tecnologica",
    "arquitetura de dados",
    "arquitetura de informacao",
    "arquitetura de infraestrutura",
    "engenharia de software",
    "desenvolvimento de software",
    "sistemas aplicacionais",
    "aplicacoes informaticas",
    "infraestruturas informaticas",
    "ciberseguranca",
    "hardware",
    "data center",
    "centro de dados",

    # Comunicação e design gráfico
    "identidade visual",
    "identidade grafica",
    "design grafico",
    "comunicacao visual",
    "imagem de marca",
    "logotipo",
    "concecao grafica",
    "concepcao grafica",
    "producao grafica",

    # Serviços sem projeto arquitetónico
    "servicos de limpeza",
    "limpeza de edificios",
    "servicos de vigilancia",
    "servicos de catering",
    "fornecimento de refeicoes",
    "fornecimento de combustiveis",
    "aquisicao de combustiveis",
    "fornecimento de mobiliario",
    "aquisicao de mobiliario",
]


EXPRESSOES_FISCALIZACAO_E_OBRA = [
    "fiscalizacao de obra",
    "fiscalizacao da obra",
    "fiscalizacao das obras",
    "fiscalizacao de obras",

    "fiscalizacao de empreitada",
    "fiscalizacao da empreitada",
    "fiscalizacao das empreitadas",
    "fiscalizacao de empreitadas",

    "servicos de fiscalizacao",
    "prestacao de servicos de fiscalizacao",
    "aquisicao de servicos de fiscalizacao",

    "direcao de fiscalizacao",
    "direcao da fiscalizacao",

    "coordenacao de seguranca em obra",
    "coordenacao de seguranca na obra",
    "coordenacao de seguranca da obra",
    "coordenacao de seguranca das obras",

    "coordenacao de seguranca em empreitada",
    "coordenacao de seguranca na empreitada",
    "coordenacao de seguranca da empreitada",
    "coordenacao de seguranca das empreitadas",

    "gestao da empreitada",
    "gestao de empreitada",
    "gestao das empreitadas",
    "gestao de empreitadas",

    "gestao de qualidade da empreitada",
    "gestao da qualidade da empreitada",
    "controlo de qualidade da obra",
    "controlo de qualidade da empreitada",

    "coordenacao de gestao ambiental da empreitada",
    "coordenacao ambiental da empreitada",

    "acompanhamento de obra",
    "acompanhamento da obra",
    "acompanhamento de obras",
    "acompanhamento das obras",

    "acompanhamento da empreitada",
    "acompanhamento de empreitada",
    "supervisao de obra",
    "supervisao da obra",
]


EXPRESSOES_ENGENHARIA_NAO_ARQUITETONICA = [
    # Água e saneamento
    "abastecimento de agua",
    "rede de abastecimento de agua",
    "rede de agua",
    "redes de agua",
    "rede de saneamento",
    "redes de saneamento",
    "saneamento de aguas residuais",
    "ciclo urbano da agua",
    "infraestruturas de agua",
    "infraestruturas hidraulicas",
    "sistemas hidraulicos",
    "conduta",
    "condutas",
    "adutora",
    "adutoras",
    "pipeline",
    "pipelines",
    "etar",
    "estacao de tratamento de aguas residuais",
    "estacao de tratamento de agua",

    # Rodovias
    "rede viaria",
    "infraestruturas rodoviarias",
    "estrada",
    "estradas",
    "caminho municipal",
    "caminhos municipais",
    "caminhos rurais",
    "repavimentacao",
    "pavimentacao",
    "variante rodoviaria",
    "sinalizacao rodoviaria",
    "drenagem rodoviaria",

    # Engenharia marítima e geotécnica
    "estabilizacao de taludes",
    "protecao costeira",
    "protecao da orla costeira",
    "dunas",
    "esporao",
    "esporoes",
    "barragem",
    "barragens",
    "assoreamento",

    # Infraestruturas técnicas isoladas
    "instalacoes eletricas",
    "instalacoes mecanicas",
    "instalacoes tecnicas",
    "eficiencia energetica",
    "rede de gas",
    "redes de gas",
]


# A família 712 é a referência principal para serviços de arquitetura.
PREFIXO_CPV_ARQUITETURA = "712"


def normalizar_texto(texto):
    """
    Converte um valor para minúsculas, remove acentos
    e elimina espaços repetidos.
    """
    if texto is None:
        return ""

    texto = str(texto).lower().strip()

    texto = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )

    return " ".join(texto.split())


def garantir_lista(valor):
    """
    Garante que um valor é devolvido como lista.
    """
    if valor is None:
        return []

    if isinstance(valor, list):
        return valor

    if isinstance(valor, tuple):
        return list(valor)

    return [valor]


def encontrar_correspondencias(texto, expressoes):
    """
    Devolve as expressões encontradas, sem duplicados.
    """
    encontradas = [
        expressao
        for expressao in expressoes
        if expressao in texto
    ]

    return list(dict.fromkeys(encontradas))


def obter_cpvs_normalizados(concurso):
    """
    Obtém os CPVs e mantém apenas os algarismos.
    """
    cpvs = garantir_lista(concurso.get("cpvs"))

    resultado = []

    for cpv in cpvs:
        codigo = "".join(
            caractere
            for caractere in normalizar_texto(cpv)
            if caractere.isdigit()
        )

        if codigo:
            resultado.append(codigo)

    return resultado


def tem_cpv_arquitetura(concurso):
    """
    Verifica se existe um CPV iniciado por 712.
    """
    return any(
        cpv.startswith(PREFIXO_CPV_ARQUITETURA)
        for cpv in obter_cpvs_normalizados(concurso)
    )


def obter_tipos_contrato_normalizados(concurso):
    """
    Normaliza os tipos de contrato.
    """
    tipos = garantir_lista(concurso.get("tipos_contrato"))

    return [
        normalizar_texto(tipo)
        for tipo in tipos
        if tipo is not None
    ]


def e_aquisicao_de_servicos(concurso):
    """
    Verifica se o contrato é uma aquisição ou prestação de serviços.
    """
    tipos = obter_tipos_contrato_normalizados(concurso)

    expressoes = [
        "aquisicao de servicos",
        "prestacao de servicos",
    ]

    return any(
        expressao in tipo
        for tipo in tipos
        for expressao in expressoes
    )


def e_empreitada(concurso):
    """
    Verifica se o contrato inclui uma empreitada.
    """
    tipos = obter_tipos_contrato_normalizados(concurso)

    return any(
        "empreitada" in tipo
        for tipo in tipos
    )


def analisar_concurso(concurso):
    """
    Classifica concursos de aquisição de serviços de arquitetura.

    Regras principais:

    1. O contrato deve ser aquisição ou prestação de serviços.
    2. Deve existir arquitetura explícita, ou CPV 712 acompanhado
       por uma ação real de projeto.
    3. Coordenação de projeto é permitida.
    4. Fiscalização, segurança em obra e gestão da empreitada
       não são consideradas serviços de arquitetura.
    5. Engenharia isolada não é aceite sem arquitetura explícita.
    """
    titulo = concurso.get("titulo", "")
    texto = concurso.get("texto", "")

    texto_normalizado = normalizar_texto(
        f"{titulo} {texto}"
    )

    arquitetura_explicita = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_ARQUITETURA_EXPLICITA,
    )

    acoes_projeto = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_ACAO_DE_PROJETO,
    )

    coordenacao_projeto = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_COORDENACAO_DE_PROJETO,
    )

    exclusoes_fortes = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_EXCLUSAO_FORTE,
    )

    fiscalizacao_e_obra = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_FISCALIZACAO_E_OBRA,
    )

    engenharia_nao_arquitetonica = encontrar_correspondencias(
        texto_normalizado,
        EXPRESSOES_ENGENHARIA_NAO_ARQUITETONICA,
    )

    cpv_arquitetura = tem_cpv_arquitetura(concurso)
    aquisicao_servicos = e_aquisicao_de_servicos(concurso)
    empreitada = e_empreitada(concurso)

    tem_arquitetura_explicita = bool(arquitetura_explicita)
    tem_acao_de_projeto = bool(acoes_projeto)
    tem_coordenacao_de_projeto = bool(coordenacao_projeto)

    # O CPV 712 não é suficiente por si só.
    # Tem de existir também elaboração, revisão, conceção
    # ou coordenação de projeto.
    arquitetura_confirmada_por_cpv = bool(
        cpv_arquitetura
        and (
            tem_acao_de_projeto
            or tem_coordenacao_de_projeto
        )
    )

    tem_objeto_de_arquitetura = bool(
        tem_arquitetura_explicita
        or arquitetura_confirmada_por_cpv
    )

    # Uma empreitada apenas bloqueia quando não existe
    # uma aquisição ou prestação de serviços identificada.
    empreitada_pura = bool(
        empreitada
        and not aquisicao_servicos
    )

    bloqueado_por_exclusao = bool(
        exclusoes_fortes
        or fiscalizacao_e_obra
    )

    # Engenharia isolada é excluída.
    # Contudo, quando existe arquitetura explícita,
    # a componente de engenharia pode fazer parte
    # do projeto de arquitetura e especialidades.
    engenharia_isolada = bool(
        engenharia_nao_arquitetonica
        and not tem_arquitetura_explicita
    )

    relevante = bool(
        aquisicao_servicos
        and tem_objeto_de_arquitetura
        and not empreitada_pura
        and not bloqueado_por_exclusao
        and not engenharia_isolada
    )

    correspondencias = list(
        dict.fromkeys(
            arquitetura_explicita
            + acoes_projeto
            + coordenacao_projeto
        )
    )

    exclusoes = list(
        dict.fromkeys(
            exclusoes_fortes
            + fiscalizacao_e_obra
            + (
                engenharia_nao_arquitetonica
                if engenharia_isolada
                else []
            )
        )
    )

    motivos = []

    if aquisicao_servicos:
        motivos.append(
            "contrato de aquisição ou prestação de serviços"
        )

    if tem_arquitetura_explicita:
        motivos.append(
            "referência explícita a arquitetura"
        )

    if arquitetura_confirmada_por_cpv:
        motivos.append(
            "CPV 712 acompanhado por ação de projeto"
        )

    if tem_coordenacao_de_projeto:
        motivos.append(
            "coordenação relacionada com projeto"
        )

    if bloqueado_por_exclusao:
        motivos.append(
            "serviço de fiscalização, obra ou exclusão forte"
        )

    if engenharia_isolada:
        motivos.append(
            "projeto de engenharia sem arquitetura explícita"
        )

    return {
        "relevante": relevante,
        "correspondencias": correspondencias,
        "exclusoes": exclusoes,
        "cpv_arquitetura": cpv_arquitetura,
        "aquisicao_servicos": aquisicao_servicos,
        "empreitada": empreitada,
        "motivos": motivos,
    }