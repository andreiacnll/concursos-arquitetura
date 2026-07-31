\# CNLL Company Intelligence

\# Company Intelligence Persistence Architecture





\## Objetivo





Definir como a informação da empresa, dos membros e da inteligência AI é persistida.





O sistema deve preservar:





\- identidade institucional;

\- identidades profissionais individuais;

\- conhecimento acumulado;

\- estratégia;

\- decisões;

\- evolução ao longo do tempo.







\---



\# Princípio





A empresa não possui apenas um perfil.





Existe uma hierarquia:





Empresa



↓



Membros



↓



Perfis individuais



↓



Inteligência agregada







\---



\# Fluxo de criação





\## Novo utilizador





Utilizador cria conta.





↓



Pode criar ou ser associado a uma empresa.





↓



É criado:



Company Member







\---



\# Criação da empresa





Quando uma empresa é criada:





Criar:





companies





\+



company\_members





\+



company\_profiles vazio







\---



\# Company Profile





O Company Profile representa a inteligência agregada da empresa.





Não representa uma pessoa.





É construído através de:





\- informação institucional;

\- perfis dos membros;

\- projetos;

\- decisões;

\- respostas AI.







\---



\# Estrutura de dados





\## companies





Dados institucionais:





{

name,



website,



description



}







\---



\## company\_members





Ligação entre pessoas e empresa:





{

company\_id,



user\_id,



role,



status



}







\---



\## member\_profiles





Informação individual:





{

identity:{},



experience:{},



competences:{},



preferences:{},



goals:{},



visibility:{}



}







\---



\## company\_profiles





Informação agregada:





{

public\_profile:{},



strategy\_profile:{},



ai\_memory:{},



completion\_score:{}



}







\---



\# Persistência





Todas as entidades devem ser persistentes.





Nunca utilizar:





TEMPORARY\_MEMORY





ou





variáveis globais.







\---



\# Histórico





O sistema deve permitir evolução:





Perfil inicial



↓



Perfil após entrevista



↓



Perfil após análise de concursos



↓



Perfil após decisões reais







Futuro:





company\_profile\_versions







\---



\# Relação com Interviewer





O Interviewer pode atuar em dois níveis:





\## Empresa





Perguntas sobre:





\- posicionamento;

\- serviços;

\- estratégia;

\- objetivos.







\## Membro





Perguntas sobre:





\- experiência;

\- competências;

\- interesses;

\- especialização.







\---



\# Relação com Extractor





Extractor:





Website



\+



Portfolio





↓



Extrai:





\- projetos;

\- competências;

\- linguagem institucional.





Depois:





Cria perfil inicial da empresa.





\---



\# Relação com Matching





Matching usa:





Concurso



\+



Company Intelligence



\+



Member Profiles







Resultado:





Score de compatibilidade.







\---



\# Privacidade





Separar:





\## Público





Informação institucional.





\## Empresa





Estratégia e conhecimento interno.





\## Individual





Informação pessoal/profissional privada.







\---



\# Regras





Nunca assumir competências individuais.





Nunca transformar informação extraída em preferência estratégica sem validação.





Toda a informação deve ter origem:





\- documentos;

\- respostas humanas;

\- decisões confirmadas.







\---



\# Futuro





Preparado para:





\- equipas multidisciplinares;

\- aprendizagem contínua;

\- RAG;

\- embeddings;

\- evolução profissional;

\- matching pessoa-concurso.

