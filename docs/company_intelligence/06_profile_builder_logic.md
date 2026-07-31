\# CNLL Company Profile Builder Logic





\## Objetivo



Construir o perfil final da empresa combinando:



\- informação extraída automaticamente;

\- respostas dadas pelo utilizador;

\- validações feitas durante o processo de entrevista.





O perfil final será utilizado por:



\- pesquisa personalizada;

\- alertas;

\- análise de concursos;

\- scoring;

\- geração de respostas.





\---



\# Princípio fundamental



O sistema deve distinguir sempre:



1\. Informação encontrada



Obtida através de:

\- website;

\- portfolio;

\- documentos.





2\. Informação confirmada



Validada pelo utilizador.





3\. Informação estratégica



Preferências e objetivos indicados pela empresa.





Nunca transformar informação encontrada automaticamente em preferência estratégica.





Exemplo:





Encontrado:



"A empresa realizou projetos escolares."





Não assumir:



"A empresa quer todos os concursos escolares."





Perguntar:



"Os equipamentos educativos representam uma área estratégica para a empresa?"





\---



\# Estrutura do perfil final





\## 1. Identidade pública





Fonte:



Extractor + validação





Inclui:



\- nome;

\- descrição;

\- localização;

\- história;

\- serviços.





\---



\## 2. Competências





Combinar:



Experiência detectada



\+



Confirmação do utilizador





Cada competência deve ter:





{

"area": "reabilitação",



"experiencia": 5,



"interesse\_futuro": 4,



"fonte": "portfolio",



"validado": true



}





\---



\## 3. Projetos de referência





Cada projeto deve guardar:





{

"nome": "",



"tipologia": "",



"localizacao": "",



"competencias": \[],



"fonte": "",



"confirmado": true



}





Projetos serão usados futuramente para:



\- recomendações;

\- respostas;

\- seleção automática de referências.





\---



\## 4. Preferências estratégicas





Criadas apenas através de entrevista.





Exemplo:





{

"tipologias": {



"equipamentos\_publicos": 5,



"habitacao": 3,



"turismo": 2



},





"procedimentos": {



"concurso\_concecao": 5,



"publico": 4



}



}





Escala:



0-5





\---



\## 5. Estratégia futura





Guardar:



\- áreas que pretende desenvolver;

\- mercados pretendidos;

\- áreas a evitar;

\- posicionamento.





\---



\# Sistema de confiança





Cada informação deve ter:





{

"valor": "",



"origem": "",



"confidence": 0.0,



"status": ""



}





Status possíveis:





CONFIRMED



VALIDATED



DETECTED



INFERRED



UNKNOWN







\---



\# Atualização do perfil





O perfil deve evoluir.





Quando o utilizador responde:



Não substituir informação anterior sem guardar histórico.





Guardar:





valor anterior



\+



nova resposta



\+



data





\---



\# Memória AI





Criar uma camada específica:





{

"empresa":



"CNLL",





"como\_apresentar":



\[],





"argumentos\_fortes":



\[],





"referencias\_preferidas":



\[],





"estrategia\_concursos":



\[]



}





Esta memória será usada quando a AI:



\- analisar concursos;

\- criar recomendações;

\- preparar respostas.





\---



\# Resultado final esperado





O sistema deve conseguir responder:





"Que tipo de empresa é esta?"





"Que concursos fazem sentido?"





"Que projetos devem ser usados como referência?"





"Que argumentos representam melhor esta empresa?"



