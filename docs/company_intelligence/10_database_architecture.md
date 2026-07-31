\# CNLL Company Intelligence

\# Database Architecture





\## Objetivo



Definir a estrutura de dados necessária para suportar:



\- empresas;

\- equipas;

\- identidades profissionais individuais;

\- perfis empresariais;

\- memória AI;

\- análise de concursos;

\- aprendizagem através de decisões.





\---



\# Princípio fundamental





A empresa não é uma identidade única.



A inteligência da empresa resulta da combinação de:





Company Information



\+



Member Profiles



\+



Project Knowledge



\+



Decision Learning





A empresa é uma rede de conhecimento composta por pessoas.







\---



\# Arquitetura geral





User



|



|



Company Member



|



|



Company



|



+----------------+



|                |



Member Profile   Company Intelligence Profile



|                |



|                |



Individual       Agregação



Identity         Estratégica







\---



\# Entidades principais





\# 1. Companies





Representa o gabinete/escritório.





Tabela:





companies







Campos:





id



name



website



description



created\_at



updated\_at







Exemplo:





CNLL



Gabinete de arquitetura.







\---



\# 2. Company Members





Representa a relação entre uma pessoa e uma empresa.





Tabela:





company\_members







Campos:





id



company\_id



user\_id



role



status



created\_at







Roles:





owner



admin



architect



designer



collaborator







Exemplo:





CNLL



|



+-- Utilizador A (owner)



|



+-- Utilizador B (architect)







\---



\# 3. Member Profiles





Representa a identidade profissional individual.





Cada pessoa possui o seu próprio perfil.





Tabela:





member\_profiles







Campos:





id



member\_id



identity\_json



experience\_json



competences\_json



preferences\_json



goals\_json



visibility\_json



created\_at



updated\_at







\---



\# Member Profile JSON





\## identity\_json





Informação profissional:





{

"name": "",



"role": "",



"specialization": "",



"education": ""



}







\---



\## experience\_json





Experiência:





{

"projects": \[],



"typologies": \[],



"sectors": \[],



"responsibilities": \[]



}







\---



\## competences\_json





Competências:





{

"technical": \[],



"software": \[],



"methodologies": \[]



}







\---



\## preferences\_json





Interesses profissionais:





{

"preferred\_typologies": \[],



"preferred\_sectors": \[],



"preferred\_locations": \[]



}







\---



\## goals\_json





Objetivos:





{

"career\_goals": \[],



"development\_areas": \[]



}







\---



\## visibility\_json





Controlo de informação:





{

"company\_visible": \[],



"private": \[]



}







\---



\# 4. Company Intelligence Profile





Representa a camada agregada da empresa.





Não substitui os perfis individuais.





É construída através de:





Company Information



\+



Member Profiles



\+



Projects



\+



Decisions







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



"competences": \[],



"projects": \[],



"values": \[],



"methodology": {}



}







\---



\# strategy\_profile\_json





Informação estratégica privada:





{

"priority\_areas": \[],



"preferred\_typologies": \[],



"preferred\_locations": \[],



"preferred\_scales": \[],



"avoid\_areas": \[]



}







\---



\# ai\_memory\_json





Memória da AI:





{

"confirmed\_facts": \[],



"validated\_preferences": \[],



"open\_questions": \[],



"contradictions": \[],



"learning\_history": \[]



}







\---



\# 5. Company Projects





Projetos associados à empresa.





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



\# 6. Company Decisions





Decisões tomadas sobre concursos.





Tabela:





company\_decisions







Campos:





id



company\_id



competition\_id



recommendation\_score



decision



reason



created\_at







Decisions:





participar



não\_participar



avaliar







\---



\# Relação entre entidades





Uma empresa:





companies





tem:





company\_members





que têm:





member\_profiles







E possui:





company\_projects



company\_profiles



company\_decisions







\---



\# Segurança





Todas as entidades devem estar isoladas por empresa.





Nunca permitir:





Empresa A consultar dados da Empresa B.







Toda a informação deve respeitar:





company\_id







\---



\# Informação pública vs privada





\## Pública





Pode aparecer no site:





\- identidade da empresa;

\- projetos publicados;

\- competências institucionais;

\- serviços.







\## Interna da empresa





Usada para AI:





\- estratégia;

\- preferências;

\- decisões;

\- scoring.







\## Privada individual





Pertence ao membro:





\- objetivos pessoais;

\- notas privadas;

\- preferências não partilhadas.







\---



\# Relação com AI





\## Extractor





Recebe:





Website



\+



Portfolio





Cria:





Company Intelligence inicial.







\---



\## Interviewer





Pode entrevistar:





Empresa:



\- posicionamento;

\- estratégia.





Membros:



\- experiência;

\- competências;

\- interesses.







\---



\## Matching Engine





Analisa:





Concurso



\+



Empresa



\+



Membros relevantes







Resultado:





Score de compatibilidade.







\---



\## Response Generator





Usa:





\- experiência da empresa;

\- experiência dos membros;

\- estratégia;

\- projetos.





Para criar respostas personalizadas.







\---



\# Futuro





Preparado para:





\- embeddings;

\- RAG;

\- aprendizagem contínua;

\- matching de pessoas a concursos;

\- equipas multidisciplinares;

\- evolução profissional;

\- múltiplos escritórios.

