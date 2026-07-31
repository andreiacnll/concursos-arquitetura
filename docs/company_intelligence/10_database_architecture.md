\# CNLL Company Intelligence Database Architecture





\## Objetivo



Definir a estrutura de dados necessária para suportar:



\- perfis empresariais;

\- entrevistas AI;

\- conhecimento da empresa;

\- matching de concursos;

\- respostas personalizadas;

\- aprendizagem futura.





\---



\# Princípios





\## Separação de dados



Existem três tipos de informação:





1\. Dados públicos



Podem aparecer no perfil institucional.





2\. Dados estratégicos privados



Usados apenas para recomendações e análise.





3\. Memória AI



Contexto interno usado pelos agentes AI.







\---



\# Entidades principais





\# 1. Companies





Representa a empresa/escritório.





Tabela:



companies





Campos:





id



name



website



description



location



created\_at



updated\_at







\---



\# 2. Company Users





Relaciona utilizadores com empresas.





Tabela:



company\_users





Campos:





id



company\_id



user\_id



role





Roles:





owner



admin



member







\---



\# 3. Company Profiles





Perfil inteligente da empresa.





Tabela:





company\_profiles





Campos:





id



company\_id





public\_profile\_json





strategy\_profile\_json





ai\_memory\_json





completion\_score





created\_at



updated\_at







\---



\# public\_profile\_json





Informação institucional:





{

"identity": {},



"services": \[],



"projects": \[],



"competences": \[],



"values": \[]



}







\---



\# strategy\_profile\_json





Informação estratégica:





{

"priority\_areas": {},



"preferred\_typologies": {},



"locations": {},



"procedures": {},



"scale\_preferences": {}



}







\---



\# ai\_memory\_json





Memória:





{

"confirmed\_facts": \[],



"validated\_preferences": \[],



"open\_questions": \[],



"language\_style": \[]



}







\---



\# 4. Company Documents





Documentos enviados pela empresa.





Tabela:





company\_documents





Campos:





id



company\_id



type



file\_url



source



processed



created\_at







Tipos:





portfolio



website



presentation



other







\---



\# 5. Company AI Sessions





Histórico da entrevista.





Tabela:





company\_ai\_sessions





Campos:





id



company\_id



question



question\_type



answer



source



created\_at







Permite:





\- continuar entrevista;

\- consultar histórico;

\- melhorar perfil.







\---



\# 6. Company Projects





Projetos extraídos.





Tabela:





company\_projects





Campos:





id



company\_id



name



year



location



typology



description



competences\_json



source



confidence







\---



\# 7. Competition Matching





Ligação entre empresa e concursos.





Tabela:





company\_competition\_matches





Campos:





id



company\_id



competition\_id



score



recommendation



reasons\_json



risks\_json



created\_at







\---



\# 8. Company Decisions





Decisões humanas.





Tabela:





company\_decisions





Campos:





id



company\_id



competition\_id



decision



reason



created\_at







Decisions possíveis:





participar



não\_participar



avaliar







\---



\# 9. AI Responses





Respostas geradas.





Tabela:





company\_ai\_responses





Campos:





id



company\_id



competition\_id



strategy\_json



arguments\_json



references\_json



created\_at







\---



\# Segurança





Todas as tabelas devem possuir:





company\_id





Nunca permitir:





Empresa A consultar dados Empresa B.





Utilizar:





Row Level Security (Supabase RLS)







\---



\# JSON vs tabelas





Guardar em JSON:





\- perfis flexíveis;

\- preferências;

\- memória AI;

\- argumentos.





Guardar em tabelas:





\- relações;

\- documentos;

\- projetos;

\- decisões;

\- histórico.







\---



\# Futuro





Preparado para:





\- embeddings;

\- vector database;

\- múltiplos utilizadores;

\- planos comerciais;

\- equipas dentro de empresas.







\---



\# Fluxo de dados





Empresa cria conta



↓



Cria company



↓



Upload documentos



↓



AI extrai informação



↓



Cria company\_profile



↓



Interviewer completa informação



↓



Perfil usado em concursos

