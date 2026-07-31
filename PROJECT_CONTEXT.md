# PROJECT_CONTEXT

Documento de contexto vivo do projeto **concursos-arquitetura / Portal Concursos**.

Objetivo: permitir que qualquer agente continue o desenvolvimento sem depender do histórico da conversa.

---

## 1) Visão geral

O projeto é um portal de concursos públicos para arquitetura, urbanismo e áreas relacionadas, com três camadas principais:

1. um backend FastAPI com SQLite;
2. um frontend Next.js 16 em App Router;
3. uma camada crescente de **Company Intelligence** para perfis empresariais, equipa, conhecimento, entrevistas e recomendações.

A aplicação está em português na interface e mistura identificadores em português/inglês no código. Isso é normal no estado atual.

---

## 2) Estrutura do repositório

Áreas mais importantes:

| Pasta | Papel |
|---|---|
| `app/` | Backend Python/FastAPI, motor de análise, auth, SQLite e Company Intelligence |
| `frontend/` | Frontend Next.js, UI pública e privada, auth Supabase, páginas de empresa, favoritos, alertas, análises |
| `docs/company_intelligence/` | Documento de arquitetura e roadmap da camada Company Intelligence |
| `analise_documentos/` | Artefactos persistidos das análises por concurso (`analise.json`, `ficha.json`, `textos.json`, etc.) |
| `public/` e `frontend/public/` | Assets estáticos, ícones, SVGs, capas de análise |

Há também scripts de apoio e ficheiros antigos/backup:

- `app/*.bak`
- `app/api.py.bak`
- scripts `teste_*.py`
- scripts de migração/apoio no root

Esses ficheiros existem e podem ser úteis para referência, mas não são a superfície principal da app.

---

## 3) Entradas principais da aplicação

### Backend

- `app/api.py` é a app FastAPI principal.
- `app/main.py` é um script CLI/worker de recolha/análise de concursos.

### Frontend

- `frontend/src/app/...` contém as páginas do Next.js.
- `frontend/src/context/AuthContext.tsx` gere a sessão Supabase no browser.

---

## 4) Ambiente e variáveis

Variáveis usadas no projeto:

### Supabase / autenticação

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

### API do frontend

- `NEXT_PUBLIC_API_URL`

### Company Intelligence / AI documental

- `OPENAI_API_KEY`
- `CNLL_AI_MODEL`
- `CNLL_AI_TIMEOUT`
- `CNLL_AI_MAX_CHARS`

### Worker de análise / coleta

- `CNLL_ANALISE_WORKER`
- `CNLL_ANALISE_WORKER_POLL`
- `CNLL_ANALISE_DOWNLOAD_INTERVALO`
- `CNLL_ANALISE_DOWNLOAD_TIMEOUT`
- `BASE_VERSAO_PORTAL`
- `BASE_TIMEOUT_SEGUNDOS`
- `BASE_PAGE_SIZE`
- `BASE_MAX_PAGINAS`
- `BASE_MAX_DETALHES`
- `BASE_INTERVALO_PEDIDOS`
- `BASE_INTERVALO_DETALHES`
- `BASE_MAX_TENTATIVAS`
- `BASE_ESPERA_BLOQUEIO`
- `BASE_JITTER_MAXIMO`
- `BASE_HEADLESS`

### Email

- variáveis lidas por `app/emailer.py` e `app/apresentacao_mensal.py` para SMTP / envio.

### Nota importante

O frontend tem `npm run build` dentro de `frontend/`.  
Na raiz do repositório, o `package.json` não tem scripts de build relevantes para a app web.

---

## 5) Backend: arquitetura real

### 5.1 FastAPI principal

`app/api.py` define a aplicação FastAPI e inclui:

- `favoritos_router`
- `analises_router`
- `alertas_router`
- `company_ai_router`

Além disso, a própria `app/api.py` também expõe endpoints diretos para:

- `GET /`
- `GET /health`
- `GET /analise/{id_concurso}`
- `GET /concursos`
- `GET /historico`
- `GET /concursos/{concurso_id}`
- `GET /estatisticas`
- `GET /concursos/{concurso_id}/timeline`

### 5.2 Observação sobre concursos

Existe também `app/routes/concursos.py` com `prefix="/concursos"`, mas no estado atual revisto o `app/api.py` é o que expõe a superfície efetiva.  
Se houver dúvidas sobre como a rota `/concursos` é servida em produção, essa é uma coisa a confirmar com cuidado.

### 5.3 Auth do backend

`app/auth.py` valida o bearer token contra o Supabase:

- lê `Authorization: Bearer ...`
- chama `SUPABASE_URL/auth/v1/user`
- devolve `UtilizadorAutenticado(id, email)`

Se a configuração Supabase não existir, o backend responde `503`.

### 5.4 SQLite

`app/database.py` é o centro da persistência:

- abre a ligação SQLite via `abrir_conexao()`
- cria tabelas com `CREATE TABLE IF NOT EXISTS`
- migra colunas quando necessário
- preserva compatibilidade com dados existentes

`criar_base_dados()` é chamado no startup do FastAPI e garante a estrutura.

---

## 6) Backend: análise de concursos

O motor histórico do produto continua a ser a análise de concursos públicos.

### Pipeline principal

1. `app/coletor.py` recolhe anúncios do Portal BASE.
2. `app.ai.analisar_concurso(...)` classifica relevância.
3. `app.dre.enriquecer_concurso(...)` acrescenta critérios quando existe link do Diário da República.
4. `app.database.guardar_concurso(...)` persiste o concurso.
5. `app.analise.worker` processa análises em background.
6. `app.analise.document_ai` lê documentos e produz estrutura de ficha.
7. `app.database.guardar_analise(...)` grava a análise.

### Ficheiros importantes

- `app/analise/worker.py`
- `app/analise/document_ai.py`
- `app/analise/extrair_texto_pdf.py`
- `app/analise/gerar_ficha.py`
- `app/analise/gerador.py`
- `app/analise/equipa.py`
- `app/analise/classificador.py`
- `app/analise/criterios.py`

### O que já faz

- recolha automática de concursos
- extração de texto de PDFs
- análise determinística e/ou assistida por AI documental
- geração de `ficha.json` e `analise.json`
- timeline por concurso
- histórico de análises e versões
- favoritos e alertas ligados ao utilizador

### O que ainda é legado / apoio

`app/analise/document_ai.py` já suporta:

- extração local determinística
- tentativa opcional de OpenAI quando `OPENAI_API_KEY` existe

Não é ainda o “Company Intelligence extractor”; é o motor de análise dos concursos.

---

## 7) Database: estado atual

O SQLite contém tanto o core do portal como a nova camada de empresa.

### Tabelas principais do core

- `concursos`
- `analises`
- `analise_jobs`
- `analise_versoes`
- `timeline_eventos`
- `favoritos`
- `alertas`
- `alertas_subscricoes`
- outras tabelas auxiliares do sistema de análise e histórico

### Tabelas Company Intelligence

| Tabela | Função |
|---|---|
| `companies` | empresa base associada a um utilizador |
| `company_members` | membros da empresa |
| `company_profiles` | perfil agregado da empresa |
| `member_profiles` | perfil individual por membro |
| `company_interview_sessions` | sessões de entrevista |
| `company_interview_questions` | perguntas da entrevista |
| `company_interview_answers` | respostas às perguntas |
| `company_knowledge_memory` | factos empresariais com origem, confiança e estado |

### Relações importantes

- `company_members.company_id -> companies.id` com `ON DELETE CASCADE`
- `company_profiles.company_id -> companies.id` com `ON DELETE CASCADE`
- `member_profiles.member_id -> company_members.id` com `ON DELETE CASCADE`
- `company_interview_sessions.company_id -> companies.id` com `ON DELETE CASCADE`
- `company_interview_questions.session_id -> company_interview_sessions.id` com `ON DELETE CASCADE`
- `company_interview_answers.question_id -> company_interview_questions.id` com `ON DELETE CASCADE`
- `company_knowledge_memory.company_id -> companies.id` com `ON DELETE CASCADE`

### Estado da integridade

As tabelas de Company Intelligence já foram desenhadas para cascata e compatibilidade com SQLite, preservando o padrão `CREATE TABLE IF NOT EXISTS`.

---

## 8) Company Intelligence: estado atual

Esta é a área mais importante para continuidade do projeto.

### 8.1 Objetivo atual

Construir um sistema empresarial onde:

- um utilizador pode ter uma empresa;
- a empresa pode ter vários membros;
- cada membro pode ter um perfil individual;
- a empresa agrega conhecimento e perfil AI;
- entrevistas e ingestões atualizam esse conhecimento;
- recomendações de concursos usam esse contexto.

### 8.2 Estrutura de módulos

Em `app/company_ai/` existem módulos “vivos” e módulos de placeholder.

#### Módulos vivos

- `models.py`
- `company_storage.py`
- `profile_storage.py`
- `member_storage.py`
- `knowledge_storage.py`
- `company_extractor.py`
- `company_ingestion.py`
- `profile_builder.py`
- `profile_updater.py`
- `answer_interpreter.py`
- `question_engine.py`
- `knowledge_validation.py`
- `interview_storage.py`
- `company_context.py`
- `competition_context.py`
- `compatibility_analysis.py`
- `recommendation_engine.py`
- `recommendation_presenter.py`
- `intelligence_builder.py`
- `router.py`

#### Placeholders explícitos

- `extractor.py` → placeholder legado
- `interviewer.py` → placeholder legado

Esses ficheiros existem para sinalizar a evolução futura, mas a lógica ativa está noutros módulos.

### 8.3 Modelos Pydantic atuais

#### Empresa / equipa

- `Company`
- `CompanyMember`

#### Perfil individual

- `MemberIdentity`
- `MemberExperience`
- `MemberCompetences`
- `MemberPreferences`
- `MemberGoals`
- `MemberVisibility`
- `MemberProfile`

#### Perfil da empresa

- `CompanyIdentity`
- `CompanyProjectExperience`
- `CompanyPreferences`
- `CompanyMemory`
- `CompanyProfile`

#### Conhecimento

- `KnowledgeFact`
- `InterpretedAnswer`
- `ValidationQuestion`
- `Question`
- `QuestionOption`
- `ExtractedFact`
- `CompanyExtractionResult`
- `RecommendationCardData`
- `CompatibilityResult`
- `CompanyRecommendation`
- `CompanyContext`
- `CompetitionContext`

### 8.4 Storage / persistence

#### `company_storage.py`

Responsável por:

- `obter_empresa_utilizador(user_id)`
- `criar_empresa(user_id, name, website=None)`
- `adicionar_membro(company_id, user_id, role="member")`
- `listar_membros(company_id)`

Notas atuais:

- `company_storage.py` tambem inclui pesquisa segura de empresas por nome/dominio normalizados para sugestoes.
- `companies.name` e `companies.website` nao sao unicos.
- `company_members` tem `UNIQUE(company_id, user_id)`.
- `obter_empresa_utilizador(user_id)` devolve apenas uma empresa ativa, dando prioridade a empresas em que o utilizador e owner; ainda nao ha seletor de multiplas empresas.
- Pesquisa de empresas e apenas sugestiva. Nunca associa utilizadores automaticamente por nome, dominio ou website.
- `POST /company/members` deve ser usado apenas por owner/admin. Fluxos publicos futuros devem usar convite/aprovacao antes de expor dados privados.

#### `profile_storage.py`

Persistência do `CompanyProfile` por `company_id`.

- `obter_company_profile(company_id)`
- `guardar_company_profile(company_id, profile)`

Se não existir perfil, devolve um perfil vazio em vez de falhar.

#### `member_storage.py`

Persistência do `MemberProfile` por `member_id`.

- `obter_member_profile(member_id)`
- `guardar_member_profile(member_id, profile)`
- `criar_member_profile(member_id)`

#### `knowledge_storage.py`

Memória de conhecimento empresarial.

- `save_knowledge_fact(...)`
- `get_company_knowledge(company_id)`
- `get_knowledge_by_field(company_id, field)`
- `apply_validation_answer(...)`

#### `interview_storage.py`

Persistência do fluxo de entrevista.

- `create_interview_session(company_id)`
- `get_active_interview_session(company_id)`
- `save_question(session_id, question)`
- `save_answer(question_id, answer)`
- `get_session_questions(session_id)`
- `get_question_context(question_id)`
- `get_question_answer(question_id)`

### 8.5 Fluxo atual da Company Intelligence

#### A) Perfil empresarial

1. `GET /company/profile`
2. `POST /company/profile`
3. `PUT /company/profile`

O backend:

- descobre a empresa do utilizador com `obter_empresa_utilizador()`
- carrega o perfil por `company_id`
- se não existir, devolve perfil vazio

#### B) Perfil por membro

1. `GET /company/members/{member_id}/profile`
2. `POST /company/members/{member_id}/profile`
3. `PUT /company/members/{member_id}/profile`

Esse perfil individual serve de base para a agregação futura da inteligência da empresa.

#### C) Conhecimento e ingestão documental

1. `POST /company/documents/ingest`
2. `company_extractor.extract_company_information(...)`
3. `knowledge_storage.save_knowledge_fact(...)`
4. `profile_builder.apply_extraction_to_profile(...)`
5. `profile_storage.guardar_company_profile(...)`

Hoje isto é determinístico, sem LLM real.

#### D) Entrevista AI

1. `GET /company/questions`
2. `GET /company/interview`
3. `POST /company/interview/{question_id}/answer`
4. `POST /company/interview/{question_id}/apply`

O fluxo atual combina:

- perguntas de descoberta do `question_engine`
- perguntas de validação do `knowledge_validation`
- respostas interpretadas por `answer_interpreter`
- atualização do perfil por `profile_updater`
- atualização do conhecimento quando a pergunta é de validação

#### E) Contexto agregado

- `build_company_intelligence(company_id)`
- `build_company_context(company_id)`
- `build_competition_context(analysis_data)`

Essas camadas juntam:

- perfil da empresa
- membros
- perfis dos membros
- conhecimento
- informação em falta

#### F) Compatibilidade e recomendações

O fluxo atual é:

1. `build_company_context(company_id)`
2. `build_competition_context(analysis_data)`
3. `analyze_compatibility(...)`
4. `generate_recommendation(...)`
5. `build_recommendation_card(...)`

Endpoints:

- `GET /company/recommendations`
- `GET /company/recommendation-cards`

### 8.6 O que o router expõe hoje

`app/company_ai/router.py` inclui os seguintes endpoints:

- `GET /company/profile`
- `POST /company/profile`
- `PUT /company/profile`
- `GET /company/intelligence`
- `GET /company/recommendations`
- `GET /company/recommendation-cards`
- `POST /company/documents/ingest`
- `POST /company/documents/ingest-file`
- `POST /company/website/ingest`
- `GET /company/search`
- `GET /company/questions`
- `GET /company/interview`
- `POST /company/interview/{question_id}/answer`
- `POST /company/interview/{question_id}/apply`
- `GET /company/members/{member_id}/profile`
- `POST /company/members/{member_id}/profile`
- `PUT /company/members/{member_id}/profile`
- `GET /company`
- `POST /company`
- `GET /company/members`
- `POST /company/members`

### 8.7 Ponto importante de implementação

Em todo este sistema, o padrão é:

- não criar novas bases de dados;
- usar SQLite existente;
- preservar dados legados;
- aceitar perfis vazios como estado válido;
- não inventar informação;
- manter a lógica determinística até existir LLM real.

---

## 9) Company Intelligence: fluxos detalhados

### 9.1 Company Extractor

`company_extractor.py` recebe texto documental e devolve factos estruturados:

- `company.services`
- `company.competences`
- `company.identity`
- `projects.typologies`

Estado atual:

- regras determinísticas simples
- sem LLM real
- sem ligação direta automática ao perfil por endpoint

### 9.2 Profile Builder

`profile_builder.py` faz merge da extração no `CompanyProfile`:

- nunca apaga dados existentes
- remove duplicados
- ignora factos inválidos/incompatíveis

### 9.3 Ingestion Pipeline

`company_ingestion.py` orquestra:

texto documental → extractor → knowledge memory → profile builder → persistência

Hoje esta é a rota de entrada documental principal da empresa.

### 9.4 Question Engine

`question_engine.py` transforma lacunas de informação em perguntas estruturadas:

- `field`
- `type`
- `priority`
- `question`
- `options`
- `reason`

### 9.5 Interview Sessions

`interview_storage.py` guarda:

- sessão
- perguntas
- respostas

As perguntas podem ser:

- `discovery`
- `validation`

### 9.6 Knowledge Validation

`knowledge_validation.py` gera perguntas quando:

- a confiança é baixa
- o estado não está confirmado

### 9.7 Answer Interpreter

`answer_interpreter.py` converte resposta em estrutura compatível com o updater.

### 9.8 Profile Updater

`profile_updater.py` aplica respostas ao perfil sem apagar informação existente.

### 9.9 Contexto e recomendação

`company_context.py`, `competition_context.py`, `compatibility_analysis.py`, `recommendation_engine.py` e `recommendation_presenter.py` formam a base para comparação empresa vs concurso.

Estado atual:

- sem score numérico
- sem ranking avançado
- sem persistência de recomendações
- sem favoritos ligados a Company Intelligence
- recomendações geradas de forma explicável

---

## 10) Frontend: arquitetura real

### 10.1 Layout base

- `frontend/src/app/layout.tsx`
- `frontend/src/components/layout/GlobalNavbar.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

### 10.2 Layouts

- `PublicLayout`
- `PrivateLayout`
- `PortalLayout`

`PrivateLayout` usa `AuthGuard`, navbar e sidebar.

### 10.3 Autenticação frontend

`frontend/src/context/AuthContext.tsx` gere:

- sessão Supabase
- `signIn`
- `signUp`
- `signOut`
- persistência “manter sessão iniciada”

### 10.4 Supabase / session persistence

Arquivos:

- `frontend/src/lib/supabase/client.ts`
- `frontend/src/lib/supabase/server.ts`
- `frontend/src/lib/supabase/middleware.ts`
- `frontend/src/lib/supabase/session-persistence.ts`
- `frontend/src/proxy.ts`

Função:

- manter/renovar sessão
- proteger rotas
- redirecionar autenticação

`proxy.ts` protege:

- `/perfil`
- `/favoritos`
- `/analises`
- `/alertas`
- `/auth`

`/empresa` é protegido pelo `PrivateLayout/AuthGuard`.

### 10.5 Páginas públicas e privadas

#### Públicas

- `/` → dashboard de concursos
- `/auth/login`
- `/auth/register`
- `/auth/callback`

#### Privadas

- `/perfil`
- `/favoritos`
- `/analises`
- `/analise/[id]`
- `/alertas`
- `/empresa`
- `/entidades`

### 10.6 Página `/empresa`

Esta página é a área “Minha Empresa”.

Comportamento atual:

- carrega `GET /company`
- carrega `GET /company/profile`
- trata ausência de empresa/perfil como estado vazio, não como erro
- abre onboarding automaticamente quando o perfil é vazio ou incompleto
- mostra erro real apenas quando há falha de servidor/rede
- permite abrir onboarding manualmente mesmo em estado de erro

Componentes principais usados:

- `CompanyProfileForm`
- `CompanyInformationSection`
- `CompanyKnowledgeSection`
- `CompanyOnboardingModal`
- `CompanySourceStep`
- `CompanyInterviewStep`
- `CompanyProfileSummary`

### 10.7 Páginas de análise e recomendações

- `/analise/[id]` mostra ficha detalhada de um concurso
- `/analises` mostra filas/estado de jobs
- `/favoritos` mostra favoritos e incorpora `RecommendationList`
- `RecommendationCard` e `RecommendationList` já consomem `GET /company/recommendation-cards`

### 10.8 Dashboard de concursos

`frontend/src/app/page.tsx` carrega concursos e mostra `CompetitionsDashboard`.

`CompetitionCard` inclui:

- link para o concurso
- bookmark/favorito
- atalho para criar análise AI

---

## 11) Componentes Company Intelligence no frontend

### 11.1 Estrutura existente

`frontend/src/components/company/` contém:

- `company-types.ts`
- `CompanyProfileForm.tsx`
- `CompanyInformationSection.tsx`
- `CompanyKnowledgeSection.tsx`
- `CompanySourceStep.tsx`
- `CompanyInterviewStep.tsx`
- `CompanyProfileSummary.tsx`
- `CompanyOnboardingModal.tsx`

### 11.2 Tipos frontend

`company-types.ts` define:

- `CompanyProfile`
- `CompanyIdentity`
- `CompanyPreferences`
- `CompanyMemory`
- `CompanyBasicInfo`
- `CompanyInterviewQuestion`

Helpers importantes:

- `createEmptyCompanyProfile()`
- `normalizeCompanyProfile(data)`
- `isCompanyProfileEmpty(profile)`
- `needsCompanyOnboarding(profile)`
- `listToText(...)`
- `textToList(...)`

### 11.3 Onboarding da empresa

`CompanyOnboardingModal` implementa um wizard em 4 passos:

1. fontes da empresa
2. processamento AI
3. entrevista AI
4. perfil criado

Chama:

- `POST /company/profile`
- `POST /company/documents/ingest`
- `POST /company/documents/ingest-file`
- `POST /company/website/ingest`
- `GET /company/search`
- `GET /company/interview`
- `POST /company/interview/{question_id}/answer`
- `POST /company/interview/{question_id}/apply`

### 11.4 Perfil empresarial

`CompanyProfileForm` mostra e edita:

- nome da empresa
- website
- identidade
- serviços
- competências
- estratégia

### 11.5 Perfil / conhecimento

`CompanyKnowledgeSection` mostra a memória AI disponível no `CompanyProfile`.

### 11.6 Step de fontes

`CompanySourceStep` recolhe:

- website
- portfolio PDF
- documentos institucionais

### 11.7 Step de entrevista

`CompanyInterviewStep` apresenta perguntas vindas da entrevista e guarda respostas.

### 11.8 Resumo final

`CompanyProfileSummary` mostra:

- identidade
- serviços
- competências
- projetos encontrados

---

## 12) Estado das funcionalidades já implementadas

### Backend

- FastAPI principal em funcionamento
- autenticação Supabase no backend
- SQLite com tabelas de análise e Company Intelligence
- endpoints de concursos, análises, favoritos, alertas
- endpoints Company Intelligence para empresa, membros, perfil, entrevista, conhecimento, contexto e recomendações
- ingestão documental determinística
- entrevista determinística
- knowledge memory
- contexto empresarial e contexto de concurso
- comparação e recomendações explicáveis

### Frontend

- app pública de concursos
- dashboard principal
- auth login/register/callback
- favoritos, alertas, análises, histórico
- página `/empresa` com onboarding e edição de perfil
- UI de recomendações em `/favoritos`
- layout privado com sidebar/navbar

### Build

- `frontend` compila com `npm.cmd run build`
- a build foi validada nesta sessão

---

## 13) Funcionalidades pendentes / ainda não implementadas

Estas continuam fora do âmbito ativo ou ainda são apenas base arquitetural:

- LLM real no Company Intelligence
- OpenAI/DeepSeek efetivos para Company Intelligence
- embeddings
- RAG
- matching avançado
- scoring numérico avançado
- ranking persistido de recomendações
- persistência de recomendações
- admin approval flow para empresas
- permissões complexas por membro/perfil
- convites por email
- upload binario de ficheiros ja existe no onboarding via `POST /company/documents/ingest-file`; ainda falta melhorar UX/limites/preview e suporte a mais formatos
- parsing real de PDF existe no backend via `pypdf`; ainda falta robustez para PDFs digitalizados/OCR
- qualquer alteração ao worker de análise que mude o pipeline histórico sem necessidade

### Cuidado com a nomenclatura

Há módulos que parecem prontos mas são apenas placeholders:

- `app/company_ai/extractor.py`
- `app/company_ai/interviewer.py`

Os módulos efetivos estão noutros ficheiros:

- `company_extractor.py`
- `question_engine.py`
- `knowledge_validation.py`
- `answer_interpreter.py`
- `profile_updater.py`

---

## 14) Observações práticas para continuar o trabalho

1. Se for mexer em rotas protegidas no frontend, lembrar que:
   - `AuthGuard` controla o acesso client-side;
   - `proxy.ts` controla parte da proteção e refresh da sessão.

2. Se for mexer em Company Intelligence:
   - respeitar o padrão SQLite + `abrir_conexao()`;
   - não criar uma segunda base;
   - não apagar dados existentes;
   - manter compatibilidade com perfis vazios.

3. Se for mexer na página `/empresa`:
   - perfis inexistentes devem ser tratados como estado válido;
   - onboarding deve abrir automaticamente quando necessário;
   - erro real deve continuar visível;
   - a página não deve bloquear só porque ainda não existe empresa.

4. Se for mexer no backend de concursos:
   - a lógica de análise histórica já está consolidada em `app/analise/` + `app/database.py`;
   - mudanças no worker podem afetar artefactos em `analise_documentos/`.

---

## 15) Estado recente validado

Neste momento, a build do frontend foi validada com sucesso:

- comando: `npm.cmd run build`
- diretório: `frontend/`

Isso é relevante porque o repositório raiz não expõe o script de build da app web.

---

## 16) Onde continuar sem perder contexto

Se precisares continuar o desenvolvimento, os ficheiros mais importantes para começar são:

- `app/api.py`
- `app/database.py`
- `app/auth.py`
- `app/company_ai/router.py`
- `app/company_ai/models.py`
- `app/company_ai/company_storage.py`
- `app/company_ai/profile_storage.py`
- `app/company_ai/member_storage.py`
- `app/company_ai/knowledge_storage.py`
- `app/company_ai/company_ingestion.py`
- `app/company_ai/company_context.py`
- `app/company_ai/competition_context.py`
- `app/company_ai/compatibility_analysis.py`
- `app/company_ai/recommendation_engine.py`
- `app/company_ai/recommendation_presenter.py`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/proxy.ts`
- `frontend/src/app/empresa/page.tsx`
- `frontend/src/components/company/CompanyOnboardingModal.tsx`

---

## 17) Resumo curto

O projeto já tem:

- portal de concursos funcional
- backend FastAPI + SQLite
- auth Supabase
- análise de concursos
- Company Intelligence com perfil, membros, conhecimento, entrevistas, ingestão, contexto e recomendações
- frontend com dashboard, análise, favoritos, alertas, perfil e empresa

O que falta é sobretudo:

- maturar Company Intelligence com LLM/ranking/matching reais
- fechar integrações de frontend/backend ainda pendentes
- consolidar fluxos de onboarding e documentação de produção
