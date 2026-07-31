\# CNLL Knowledge Base Architecture





\## Objetivo



Criar uma camada de conhecimento que permita à inteligência artificial utilizar contexto histórico e empresarial.



A Knowledge Base será utilizada por:



\- Company AI Profile;

\- Concurso Matching;

\- Análise AI;

\- Geração de respostas;

\- Aprendizagem futura.





\---



\# Princípio





A AI não deve depender apenas do documento atual.



Deve conseguir consultar:





Empresa



\+



Projetos



\+



Concursos anteriores



\+



Decisões



\+



Respostas





para gerar recomendações melhores.





\---



\# Estrutura geral





knowledge\_base/





\## 1. Company Knowledge





Informação específica da empresa.





Exemplos:





\- identidade;

\- serviços;

\- competências;

\- valores;

\- metodologia;

\- linguagem;

\- preferências.





Fonte:



\- website;

\- portfolio;

\- entrevista AI.







\---



\## 2. Project Knowledge





Base de projetos.





Cada projeto deve guardar:





{

"name":"",



"year":"",



"location":"",



"typology":"",



"description":"",



"competences":\[],



"source":"",



"confirmed":true



}







Utilização:





\- selecionar referências;

\- comparar concursos;

\- gerar argumentos.





\---



\## 3. Competition Knowledge





Base de concursos analisados.





Guardar:





\- programa;

\- entidade;

\- localização;

\- procedimento;

\- critérios;

\- requisitos;

\- análise estratégica.







Permitir:





Encontrar concursos semelhantes.





\---



\## 4. Response Knowledge





Memória das respostas geradas.





Guardar:





\- concurso;

\- estratégia utilizada;

\- argumentos;

\- referências selecionadas;

\- resultado.





Objetivo:





Aprender que argumentos funcionam melhor.







\---



\## 5. Decision Knowledge





Aprendizagem através do utilizador.





Guardar:





{

"competition\_id":"",



"company\_id":"",



"AI\_score":85,



"company\_decision":"participar",



"reason":"",



"date":""



}







A decisão humana tem prioridade sobre a previsão AI.





\---



\# RAG Flow





Quando a AI recebe um novo concurso:





1\.



Extrair características do concurso.





2\.



Pesquisar conhecimento relevante:





\- projetos semelhantes;

\- concursos semelhantes;

\- preferências da empresa.





3\.



Construir contexto.





4\.



Enviar ao LLM.





5\.



Gerar análise.





\---



\# Exemplo





Novo concurso:





"Centro cultural Lisboa"





Pesquisa:





Empresa:



\- projetos culturais;

\- Lisboa;

\- experiência semelhante.





Histórico:



\- concursos culturais anteriores.





Resultado:





AI:





"Existe elevada compatibilidade porque a empresa possui experiência comprovada em equipamentos culturais e demonstra preferência por este tipo de procedimento."





\---



\# Organização técnica futura





Possível estrutura:





company\_profiles



projects



competitions



responses



decisions



embeddings





\---



\# Embeddings





Documentos relevantes podem ser transformados em embeddings para pesquisa semântica.





Exemplo:





Pergunta:



"Projetos semelhantes a esta escola"





Pesquisa:





Não procura apenas palavras.



Procura significado:





\- escolas;

\- aprendizagem;

\- equipamentos educativos;

\- espaços públicos.







\---



\# Evolução futura





Quando existir volume suficiente:





Dados CNLL



↓



Dataset especializado



↓



Fine tuning / LoRA



↓



Modelo especializado em concursos de arquitetura







\---



\# Regra principal





A memória pertence à empresa.



Cada escritório deve ter o seu próprio contexto isolado.



Uma empresa nunca deve aceder ao conhecimento privado de outra.

