import {
  Euro,
  Trophy,
  Users,
  Target,
  Lightbulb,
  AlertTriangle,
  CheckCircle,
  FileText,
  Scale,
  MapPin,
  ClipboardList,
} from "lucide-react";


interface ConcursoConcecaoProps {
  ficha: any;
  concurso?: any;
}


export default function ConcursoConcecaoAnalysis({
  ficha,
  concurso,
}: ConcursoConcecaoProps) {

  const identificacao = ficha?.identificacao || {};
  const modeloConcursoData = ficha?.modelo_concurso || {};
  const programa = ficha?.programa || {};
  const economia = ficha?.economia || {};
  const criterios = ficha?.criterios || {};
  const entregaveis = ficha?.entregaveis || {};
  const equipa = ficha?.equipa || {};
  const localizacao = ficha?.localizacao || {};
  const analiseAi = ficha?.analise_ai || {};


  const titulo = identificacao?.titulo || "Concurso de Conceção";
  const entidade = identificacao?.entidade || concurso?.entidade || "Entidade não indicada";
  const localizacaoTexto = identificacao?.localizacao || "Localização não indicada";


  const modeloConcurso = {
    tipoConcurso: modeloConcursoData?.tipo_concurso || "Concurso de conceção",
    premios: modeloConcursoData?.premios || [],
    trabalhosSelecionados: modeloConcursoData?.trabalhos_selecionados || 0,
    numeroVencedores: modeloConcursoData?.numero_vencedores || "Não identificado",
    jurados: modeloConcursoData?.jurados || [],
    criterios: modeloConcursoData?.criterios_avaliacao || [],
    fasePosterior: modeloConcursoData?.fase_posterior || modeloConcursoData?.desenvolvimento_posterior || "Não especificado",
  };


  const estrategia = {
    porqueInteressa: analiseAi?.oportunidades || [],
    desafios: analiseAi?.riscos || [],
    perfilIdeal: analiseAi?.perfil_ideal_atelier || "Não especificado",
    recomendacao: analiseAi?.recomendacao || "Análise em desenvolvimento",
  };

  const valePena = analiseAi?.vale_a_pena_concorrer || {};


  return (
    <div className="concurso-concecao-analysis">


      {/* 1. Cabeçalho */}
      <section className="concecao-header">
        <div className="concecao-header-content">
          <span className="concecao-badge">Concurso de Conceção</span>
          <h1>{titulo}</h1>
          <div className="concecao-meta">
            <div className="concecao-meta-item">
              <Users size={18} />
              <span>{entidade}</span>
            </div>
            <div className="concecao-meta-item">
              <Target size={18} />
              <span>{localizacaoTexto}</span>
            </div>
          </div>
        </div>
      </section>


      {/* 2. Decisão CNLL - Vale a pena concorrer? */}
      <div className="ai-decision-section">
        <div className="decision-header">
          <h2>Vale a pena concorrer?</h2>
          <p>Análise CNLL para este concurso de conceção</p>
        </div>
        <div className="decision-grid">
          <div className="decision-column score-column">
            <span>Score global</span>
            <strong style={{ fontSize: "48px", color: "#607b43" }}>{analiseAi?.score || "—"}</strong>
            <strong>/100</strong>
          </div>
          <div className="decision-column">
            <span>Interesse arquitetónico</span>
            <h3>{analiseAi?.interesse_arquitetonico || "Não avaliado"}</h3>
            <p>{estrategia.recomendacao}</p>
          </div>
          <div className="decision-column">
            <span>Complexidade</span>
            <h3>{analiseAi?.complexidade || "Não avaliada"}</h3>
            <p>{estrategia.desafios[0] || "Não especificado"}</p>
          </div>
          <div className="decision-column">
            <span>Veredito</span>
            <h3 style={{ color: "#607b43" }}>{valePena?.veredito || "—"}</h3>
            <p>{valePena?.dimensao_oportunidade || estrategia.recomendacao}</p>
          </div>
        </div>

        {valePena && Object.keys(valePena).length > 0 && (
          <div className="concecao-vale-pana-detalhes" style={{ marginTop: "24px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "16px" }}>
            <div className="concecao-detalhe-item">
              <strong>Dimensão da oportunidade</strong>
              <p>{valePena.dimensao_oportunidade || "Não identificado"}</p>
            </div>
            <div className="concecao-detalhe-item">
              <strong>Esforço necessário</strong>
              <p>{valePena.esforco_necessario || "Não identificado"}</p>
            </div>
            <div className="concecao-detalhe-item">
              <strong>Complexidade do programa</strong>
              <p>{valePena.complexidade_programa || "Não identificado"}</p>
            </div>
            <div className="concecao-detalhe-item">
              <strong>Número de entregáveis</strong>
              <p>{valePena.numero_entregaveis || "Não identificado"}</p>
            </div>
            <div className="concecao-detalhe-item">
              <strong>Composição da equipa</strong>
              <p>{valePena.composicao_equipa || "Não identificado"}</p>
            </div>
            <div className="concecao-detalhe-item">
              <strong>Probabilidade de exclusão</strong>
              <p>{valePena.probabilidade_exclusao || "Não identificado"}</p>
            </div>
          </div>
        )}
      </div>


      {/* 3. Modelo do concurso */}
      <section className="concecao-modelo-section">
        <div className="profile-card">
          <div className="profile-card-header">
            <Trophy size={24} />
            <div>
              <h2>Modelo do concurso</h2>
              <p>Características específicas deste concurso de conceção</p>
            </div>
          </div>
          <div className="profile-card-body">
            <div className="concecao-modelo-grid">
              <div className="concecao-modelo-item">
                <h3>Tipo de concurso</h3>
                <p style={{ color: "#607b43" }}>{modeloConcurso.tipoConcurso}</p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Trabalhos selecionados</h3>
                <p style={{ fontSize: "32px", fontWeight: 600, color: "#607b43" }}>
                  {modeloConcurso.trabalhosSelecionados}
                </p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Número de vencedores</h3>
                <p style={{ fontSize: "32px", fontWeight: 600, color: "#607b43" }}>
                  {modeloConcurso.numeroVencedores}
                </p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Fase posterior</h3>
                <p style={{ color: "#607b43" }}>
                  {modeloConcurso.fasePosterior}
                </p>
              </div>
            </div>

            {modeloConcurso.premios.length > 0 && (
              <div className="concecao-premios">
                <h3>Prémios</h3>
                <div className="concecao-premios-list">
                  {modeloConcurso.premios.map((premio: { posicao: string; valor: string }, idx: number) => (
                    <div key={idx} className="concecao-premio-item">
                      <Trophy size={18} />
                      <span>{premio.posicao}</span>
                      <strong>{premio.valor}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {modeloConcurso.jurados.length > 0 && (
              <div className="concecao-juri">
                <h3>Júri</h3>
                <ul>
                  {modeloConcurso.jurados.map((jurado: string, idx: number) => (
                    <li key={idx}>{jurado}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>


      {/* 4. Programa funcional */}
      {programa && Object.keys(programa).length > 0 && (
        <section className="programa-preliminar-section">
          <h2>📐 Programa funcional</h2>
          <div className="programa-preliminar-content">
            <div className="programa-item">
              <h3>Leitura do programa</h3>
              <p style={{ fontSize: "16px", lineHeight: "1.7" }}>
                {programa.resumo_intervencao || "Informação não disponível nos documentos analisados"}
              </p>
            </div>

            {programa.tipo_intervencao && (
              <div className="programa-item">
                <h3>Tipo de intervenção</h3>
                <p style={{ color: "#607b43", fontWeight: 600 }}>{programa.tipo_intervencao}</p>
              </div>
            )}

            {programa.equipamento && (
              <div className="programa-item">
                <h3>Equipamento</h3>
                <p style={{ color: "#607b43", fontWeight: 600 }}>{programa.equipamento}</p>
              </div>
            )}

            {programa.funcoes_identificadas && programa.funcoes_identificadas.length > 0 && (
              <div className="programa-item">
                <h3>Elementos principais</h3>
                <div className="programa-tags">
                  {programa.funcoes_identificadas.map((funcao: string, idx: number) => (
                    <span key={idx}>{funcao}</span>
                  ))}
                </div>
              </div>
            )}

            {programa.areas && programa.areas.length > 0 && (
              <div className="programa-item">
                <h3>Áreas</h3>
                <div className="programa-tags">
                  {programa.areas.map((area: string, idx: number) => (
                    <span key={idx}>{area}</span>
                  ))}
                </div>
              </div>
            )}

            {programa.condicionantes && programa.condicionantes.length > 0 && (
              <div className="programa-item">
                <h3>Condicionantes</h3>
                <ul>
                  {programa.condicionantes.map((condicionante: string, idx: number) => (
                    <li key={idx}>{condicionante}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}


      {/* 5. Peças a entregar */}
      {entregaveis && Object.keys(entregaveis).length > 0 && (
        <section className="concecao-entregaveis-section">
          <div className="profile-card">
            <div className="profile-card-header">
              <FileText size={24} />
              <div>
                <h2>Peças a entregar</h2>
                <p>Elementos obrigatórios para submissão da proposta</p>
              </div>
            </div>
            <div className="profile-card-body">
              {entregaveis.elementos_obrigatorios && entregaveis.elementos_obrigatorios.length > 0 && (
                <div className="concecao-entregaveis-lista">
                  <h3>Elementos obrigatórios</h3>
                  <ul>
                    {entregaveis.elementos_obrigatorios.map((item: string, idx: number) => (
                      <li key={idx}>
                        <CheckCircle size={16} />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="concecao-entregaveis-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "16px", marginTop: "16px" }}>
                <div className="concecao-entregaveis-item">
                  <h3>Formato das peças</h3>
                  <p>{entregaveis.formato_pecas || "Não identificado"}</p>
                </div>
                <div className="concecao-entregaveis-item">
                  <h3>Número de painéis</h3>
                  <p>{entregaveis.numero_paineis || "Não identificado"}</p>
                </div>
                <div className="concecao-entregaveis-item">
                  <h3>Escalas exigidas</h3>
                  <p>{entregaveis.escalas_exigidas || "Não identificado"}</p>
                </div>
                <div className="concecao-entregaveis-item">
                  <h3>Maquetes/Modelos</h3>
                  <p>{entregaveis.maquetes_modelos || "Não identificado"}</p>
                </div>
              </div>

              {entregaveis.documentos_escritos && entregaveis.documentos_escritos.length > 0 && (
                <div className="concecao-entregaveis-lista" style={{ marginTop: "16px" }}>
                  <h3>Documentos escritos</h3>
                  <div className="programa-tags">
                    {entregaveis.documentos_escritos.map((doc: string, idx: number) => (
                      <span key={idx}>{doc}</span>
                    ))}
                  </div>
                </div>
              )}

              {entregaveis.ficheiros_digitais && entregaveis.ficheiros_digitais.length > 0 && (
                <div className="concecao-entregaveis-lista" style={{ marginTop: "16px" }}>
                  <h3>Ficheiros digitais</h3>
                  <div className="programa-tags">
                    {entregaveis.ficheiros_digitais.map((ficheiro: string, idx: number) => (
                      <span key={idx}>{ficheiro}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}


      {/* 6. Equipa necessária */}
      {equipa && Object.keys(equipa).length > 0 && (
        <section className="concecao-equipa-section">
          <div className="profile-card">
            <div className="profile-card-header">
              <Users size={24} />
              <div>
                <h2>Requisitos da equipa</h2>
                <p>Composição obrigatória e habilitações exigidas</p>
              </div>
            </div>
            <div className="profile-card-body">
              {equipa.equipa_minima && equipa.equipa_minima.length > 0 && (
                <div className="concecao-equipa-bloco">
                  <h3>Equipa mínima</h3>
                  <ul>
                    {equipa.equipa_minima.map((item: string, idx: number) => (
                      <li key={idx}>
                        <CheckCircle size={16} />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {equipa.especialidades && equipa.especialidades.length > 0 && (
                <div className="concecao-equipa-bloco" style={{ marginTop: "16px" }}>
                  <h3>Especialidades</h3>
                  <div className="programa-tags">
                    {equipa.especialidades.map((esp: string, idx: number) => (
                      <span key={idx}>{esp}</span>
                    ))}
                  </div>
                </div>
              )}

              {equipa.consultores_obrigatorios && equipa.consultores_obrigatorios.length > 0 && (
                <div className="concecao-equipa-bloco" style={{ marginTop: "16px" }}>
                  <h3>Consultores obrigatórios</h3>
                  <ul>
                    {equipa.consultores_obrigatorios.map((consultor: string, idx: number) => (
                      <li key={idx}>
                        <Users size={16} />
                        {consultor}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {equipa.habilitacoes_exigidas && equipa.habilitacoes_exigidas.length > 0 && (
                <div className="concecao-equipa-bloco" style={{ marginTop: "16px" }}>
                  <h3>Habilitações exigidas</h3>
                  <ul>
                    {equipa.habilitacoes_exigidas.map((hab: string, idx: number) => (
                      <li key={idx}>
                        <Scale size={16} />
                        {hab}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </section>
      )}


      {/* 7. Critérios de avaliação */}
      {criterios && Object.keys(criterios).length > 0 && (
        <section className="concecao-criterios-section">
          <div className="profile-card">
            <div className="profile-card-header">
              <Scale size={24} />
              <div>
                <h2>Critérios de avaliação</h2>
                <p>Modelo de adjudicação e ponderação</p>
              </div>
            </div>
            <div className="profile-card-body">
              <div className="concecao-criterios-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "16px" }}>
                <div className="concecao-criterio-item">
                  <h3>Critério de adjudicação</h3>
                  <p style={{ color: "#607b43", fontWeight: 600 }}>
                    {criterios.criterio_adjudicacao || "Não identificado"}
                  </p>
                </div>
                <div className="concecao-criterio-item">
                  <h3>Modelo de avaliação</h3>
                  <p>{criterios.modelo_avaliacao || "Não identificado"}</p>
                </div>
              </div>

              {criterios.percentagens && criterios.percentagens.length > 0 && (
                <div className="concecao-criterios-lista" style={{ marginTop: "16px" }}>
                  <h3>Percentagens dos critérios</h3>
                  <div className="concecao-criterios-percentagens">
                    {criterios.percentagens.map((item: { criterio: string; percentagem: string }, idx: number) => (
                      <div key={idx} className="concecao-criterio-percentagem">
                        <span>{item.criterio}</span>
                        <strong style={{ color: "#607b43" }}>{item.percentagem}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {modeloConcurso.criterios.length > 0 && criterios.percentagens && criterios.percentagens.length === 0 && (
                <div className="concecao-criterios-lista" style={{ marginTop: "16px" }}>
                  <h3>Critérios de avaliação</h3>
                  <ul>
                    {modeloConcurso.criterios.map((criterio: string, idx: number) => (
                      <li key={idx}>{criterio}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </section>
      )}


      {/* 8. Localização */}
      {localizacao && Object.keys(localizacao).length > 0 && (
        <section className="concecao-localizacao-section">
          <div className="profile-card">
            <div className="profile-card-header">
              <MapPin size={24} />
              <div>
                <h2>Localização</h2>
                <p>Enquadramento urbano da intervenção</p>
              </div>
            </div>
            <div className="profile-card-body">
              <div className="concecao-localizacao-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                <div className="concecao-localizacao-item">
                  <h3>Município</h3>
                  <p>{localizacao.municipio || "Não identificado"}</p>
                </div>
                <div className="concecao-localizacao-item">
                  <h3>Freguesia</h3>
                  <p>{localizacao.freguesia || "Não identificado"}</p>
                </div>
                <div className="concecao-localizacao-item">
                  <h3>Morada</h3>
                  <p>{localizacao.morada || "Não identificado"}</p>
                </div>
                <div className="concecao-localizacao-item">
                  <h3>Coordenadas</h3>
                  <p>{localizacao.coordenadas || "Não identificado"}</p>
                </div>
              </div>

              {localizacao.contexto_urbano && (
                <div className="concecao-localizacao-contexto" style={{ marginTop: "16px" }}>
                  <h3>Leitura urbana</h3>
                  <p style={{ fontSize: "16px", lineHeight: "1.7" }}>{localizacao.contexto_urbano}</p>
                </div>
              )}
            </div>
          </div>
        </section>
      )}


      {/* 9. Estratégia CNLL */}
      <section className="concecao-estrategia-section">
        <div className="profile-card">
          <div className="profile-card-header">
            <Lightbulb size={24} />
            <div>
              <h2>Como abordar este concurso</h2>
              <p>Leitura estratégica CNLL</p>
            </div>
          </div>
          <div className="profile-card-body">
            <div className="concecao-estrategia-grid">
              <div className="concecao-estrategia-item">
                <h3>
                  <CheckCircle size={18} />
                  Por que pode interessar
                </h3>
                <ul>
                  {estrategia.porqueInteressa.map((item: string, idx: number) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="concecao-estrategia-item">
                <h3>
                  <AlertTriangle size={18} />
                  Desafios
                </h3>
                <ul>
                  {estrategia.desafios.map((item: string, idx: number) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="concecao-perfil">
              <h3>Perfil ideal de atelier</h3>
              <p>{estrategia.perfilIdeal}</p>
            </div>

            <div className="concecao-recomendacao">
              <h3>Recomendação CNLL</h3>
              <p style={{ fontWeight: 600, color: "#607b43" }}>{estrategia.recomendacao}</p>
            </div>
          </div>
        </div>
      </section>


      {/* 10. Dados económicos */}
      <section className="concecao-economia-section">
        <div className="profile-card">
          <div className="profile-card-header">
            <Euro size={24} />
            <div>
              <h2>Dados económicos</h2>
              <p>Separação clara entre procedimento e obra</p>
            </div>
          </div>
          <div className="profile-card-body">
            <div className="concecao-economia-grid">
              <div className="concecao-economia-item">
                <h3>Valor do procedimento</h3>
                <p style={{ fontSize: "28px", fontWeight: 600, color: "#607b43" }}>
                  {economia?.valor_procedimento || "Não identificado"}
                </p>
                <p style={{ fontSize: "12px", color: "#999" }}>
                  Prémios / custo de participação
                </p>
              </div>
              <div className="concecao-economia-item">
                <h3>Valor estimado da obra</h3>
                <p style={{ fontSize: "20px", fontWeight: 500, color: "#666" }}>
                  {economia?.valor_estimado_obra || "Não identificado"}
                </p>
                <p style={{ fontSize: "12px", color: "#999" }}>
                  A definir em fase posterior
                </p>
              </div>
              <div className="concecao-economia-item">
                <h3>Orçamento previsto</h3>
                <p style={{ fontSize: "20px", fontWeight: 500, color: "#666" }}>
                  {economia?.orcamento_previsto || "Não identificado"}
                </p>
                <p style={{ fontSize: "12px", color: "#999" }}>
                  Valor de referência para a obra
                </p>
              </div>
            </div>

            {economia?.observacoes && (
              <div className="concecao-economia-notas">
                <h3>Observações</h3>
                <ul>
                  <li>{economia.observacoes}</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>


    </div>
  );
}