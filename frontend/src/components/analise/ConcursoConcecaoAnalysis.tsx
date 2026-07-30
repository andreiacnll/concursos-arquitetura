"use client";

import {
  Trophy,
  Users,
  Lightbulb,
  AlertTriangle,
  CheckCircle,
  MapPin,
  Award,
  UserCheck,
  BookOpen,
} from "lucide-react";

interface ConcursoConcecaoProps {
  ficha: any;
  concurso?: any;
}

/**
 * ConcursoConcecaoAnalysis – Cards extra para concursos de conceção
 *
 * Apenas renderiza informação EXCLUSIVA de concursos de conceção
 * que NÃO existe nos concursos normais.
 *
 * O page.tsx já trata:
 * - DecisionDashboard (Vale a pena concorrer?)
 * - Programa preliminar
 * - Dados económicos
 * - Critérios de avaliação
 * - Entregáveis
 *
 * Este componente adiciona:
 * - Modelo do concurso (prémios, júri, trabalhos, fases)
 * - Equipa necessária (equipa mínima, especialidades, consultores)
 * - Contexto urbano / localização
 * - Estratégia CNLL (oportunidades, desafios, perfil, recomendação)
 */
export default function ConcursoConcecaoAnalysis({
  ficha,
  concurso,
}: ConcursoConcecaoProps) {

  const modeloConcursoData = ficha?.modelo_concurso || {};
  const equipa = ficha?.equipa || {};
  const localizacao = ficha?.localizacao || {};
  const analiseAi = ficha?.analise_ai || {};

  return (
    <div className="concurso-concecao-analysis">

      {/* ═══ 1. MODELO DO CONCURSO ═══ */}
      {modeloConcursoData && Object.keys(modeloConcursoData).length > 0 && (
        <section className="profile-card" style={{ marginBottom: "24px" }}>
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
                <p style={{ color: "#607b43" }}>{modeloConcursoData.tipo_concurso || "Concurso de conceção"}</p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Trabalhos selecionados</h3>
                <p style={{ fontSize: "32px", fontWeight: 600, color: "#607b43" }}>
                  {modeloConcursoData.trabalhos_selecionados || "—"}
                </p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Número de vencedores</h3>
                <p style={{ fontSize: "32px", fontWeight: 600, color: "#607b43" }}>
                  {modeloConcursoData.numero_vencedores || "—"}
                </p>
              </div>
              <div className="concecao-modelo-item">
                <h3>Fase posterior</h3>
                <p style={{ color: "#607b43" }}>
                  {modeloConcursoData.fase_posterior || "Não especificado"}
                </p>
              </div>
            </div>

            {modeloConcursoData.premios && modeloConcursoData.premios.length > 0 && (
              <div className="concecao-premios">
                <h3>Prémios</h3>
                <div className="concecao-premios-list">
                  {modeloConcursoData.premios.map((premio: { posicao: string; valor: string }, idx: number) => (
                    <div key={idx} className="concecao-premio-item">
                      <Award size={18} />
                      <span>{premio.posicao}</span>
                      <strong>{premio.valor}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {modeloConcursoData.jurados && modeloConcursoData.jurados.length > 0 && (
              <div className="concecao-juri">
                <h3><UserCheck size={18} /> Júri</h3>
                <ul>
                  {modeloConcursoData.jurados.map((jurado: string, idx: number) => (
                    <li key={idx}>{jurado}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ═══ 2. EQUIPA NECESSÁRIA ═══ */}
      {equipa && Object.keys(equipa).length > 0 && (
        <section className="profile-card" style={{ marginBottom: "24px" }}>
          <div className="profile-card-header">
            <Users size={24} />
            <div>
              <h2>Equipa necessária</h2>
              <p>Composição obrigatória e habilitações exigidas</p>
            </div>
          </div>
          <div className="profile-card-body">
            {equipa.equipa_minima && equipa.equipa_minima.length > 0 && (
              <div className="concecao-equipa-bloco">
                <h3>Equipa mínima</h3>
                <ul>
                  {equipa.equipa_minima.map((item: string, idx: number) => (
                    <li key={idx}><CheckCircle size={16} /> {item}</li>
                  ))}
                </ul>
              </div>
            )}
            {equipa.especialidades && equipa.especialidades.length > 0 && (
              <div className="concecao-equipa-bloco">
                <h3>Especialidades obrigatórias</h3>
                <div className="programa-tags">
                  {equipa.especialidades.map((esp: string, idx: number) => (
                    <span key={idx}>{esp}</span>
                  ))}
                </div>
              </div>
            )}
            {equipa.consultores_obrigatorios && equipa.consultores_obrigatorios.length > 0 && (
              <div className="concecao-equipa-bloco">
                <h3>Consultores obrigatórios</h3>
                <ul>
                  {equipa.consultores_obrigatorios.map((c: string, idx: number) => (
                    <li key={idx}><Users size={16} /> {c}</li>
                  ))}
                </ul>
              </div>
            )}
            {equipa.habilitacoes_exigidas && equipa.habilitacoes_exigidas.length > 0 && (
              <div className="concecao-equipa-bloco">
                <h3>Habilitações exigidas</h3>
                <ul>
                  {equipa.habilitacoes_exigidas.map((h: string, idx: number) => (
                    <li key={idx}><BookOpen size={16} /> {h}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ═══ 3. CONTEXTO URBANO / LOCALIZAÇÃO ═══ */}
      {localizacao && Object.keys(localizacao).length > 0 && (
        <section className="profile-card" style={{ marginBottom: "24px" }}>
          <div className="profile-card-header">
            <MapPin size={24} />
            <div>
              <h2>Contexto urbano / localização</h2>
              <p>Enquadramento geográfico e urbano da intervenção</p>
            </div>
          </div>
          <div className="profile-card-body">
            <div className="concecao-localizacao-grid">
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
                <h3>Código postal</h3>
                <p>{localizacao.codigo_postal || "Não identificado"}</p>
              </div>
              <div className="concecao-localizacao-item">
                <h3>Coordenadas</h3>
                <p>
                  {localizacao.coordenadas ||
                    (localizacao.latitude && localizacao.longitude
                      ? `${localizacao.latitude}, ${localizacao.longitude}`
                      : "Não identificado")}
                </p>
              </div>
            </div>
            {localizacao.contexto_urbano && (
              <div className="concecao-localizacao-contexto">
                <h3>Leitura arquitetónica do contexto</h3>
                <p style={{ fontSize: "16px", lineHeight: "1.7" }}>{localizacao.contexto_urbano}</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ═══ 4. ESTRATÉGIA CNLL ═══ */}
      <section className="profile-card" style={{ marginBottom: "24px" }}>
        <div className="profile-card-header">
          <Lightbulb size={24} />
          <div>
            <h2>Estratégia CNLL</h2>
            <p>Leitura estratégica para o atelier</p>
          </div>
        </div>
        <div className="profile-card-body">
          <div className="concecao-estrategia-grid">
            <div className="concecao-estrategia-item">
              <h3><CheckCircle size={18} /> Oportunidades</h3>
              <ul>
                {(analiseAi?.oportunidades || ["Análise em desenvolvimento"]).map((item: string, idx: number) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="concecao-estrategia-item">
              <h3><AlertTriangle size={18} /> Desafios</h3>
              <ul>
                {(analiseAi?.riscos || ["Análise em desenvolvimento"]).map((item: string, idx: number) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="concecao-perfil">
            <h3>Perfil ideal de atelier</h3>
            <p>{analiseAi?.perfil_ideal_atelier || "Não especificado"}</p>
          </div>
          <div className="concecao-recomendacao">
            <h3>Recomendação CNLL</h3>
            <p style={{ fontWeight: 600, color: "#607b43" }}>{analiseAi?.recomendacao || "Análise em desenvolvimento"}</p>
          </div>
        </div>
      </section>

      <style jsx>{`
        .concecao-modelo-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 20px;
        }
        .concecao-modelo-item h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 8px;
        }
        .concecao-premios {
          margin-top: 20px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .concecao-premios h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 12px;
        }
        .concecao-premios-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .concecao-premio-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          background: #f9f9f4;
          border-radius: 8px;
          font-size: 14px;
        }
        .concecao-premio-item strong {
          margin-left: auto;
          color: #607b43;
        }
        .concecao-juri {
          margin-top: 16px;
        }
        .concecao-juri h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .concecao-juri ul {
          margin: 0;
          padding-left: 20px;
        }
        .concecao-juri li {
          font-size: 14px;
          margin-bottom: 4px;
        }
        .concecao-equipa-bloco {
          margin-bottom: 16px;
        }
        .concecao-equipa-bloco h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 8px;
        }
        .concecao-equipa-bloco ul {
          list-style: none;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .concecao-equipa-bloco ul li {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
        }
        .concecao-localizacao-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
        }
        .concecao-localizacao-item h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 6px;
        }
        .concecao-localizacao-contexto {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .concecao-localizacao-contexto h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 8px;
        }
        .concecao-estrategia-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        .concecao-estrategia-item h3 {
          font-size: 14px;
          margin-bottom: 10px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .concecao-estrategia-item ul {
          margin: 0;
          padding-left: 0;
          list-style: none;
        }
        .concecao-estrategia-item li {
          font-size: 14px;
          margin-bottom: 6px;
          padding-left: 20px;
          position: relative;
        }
        .concecao-estrategia-item li::before {
          content: "•";
          position: absolute;
          left: 4px;
          color: #607b43;
        }
        .concecao-perfil {
          margin-top: 20px;
          padding-top: 16px;
          border-top: 1px solid #eee;
        }
        .concecao-perfil h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 8px;
        }
        .concecao-recomendacao {
          margin-top: 16px;
          padding: 14px;
          background: #f0f4ea;
          border-radius: 10px;
        }
        .concecao-recomendacao h3 {
          font-size: 13px;
          color: #777;
          margin-bottom: 6px;
        }
        @media (max-width: 768px) {
          .concecao-estrategia-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

    </div>
  );
}
