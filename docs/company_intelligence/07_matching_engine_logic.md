\# CNLL Matching Engine Logic





\## Objetivo



Comparar o perfil estratégico da empresa com a informação extraída de um concurso.



O objetivo não é apenas identificar correspondências.



O objetivo é responder:



"Este concurso faz sentido para esta empresa?"





\---



\# Princípio



O sistema nunca deve avaliar apenas pela tipologia.



Exemplo:



Concurso:

"Escola"





Não significa automaticamente:



Empresa interessada em escolas.





A avaliação deve considerar:



\- experiência;

\- preferências;

\- localização;

\- procedimento;

\- escala;

\- estratégia;

\- capacidade demonstrada.





\---



\# Dados de entrada





\## Perfil empresa





Exemplo:





{

"areas\_prioritarias": {},



"tipologias": {},



"localizacoes": {},



"procedimentos": {},



"experiencia": {},



"projetos\_referencia": {}



}







\## Concurso





Exemplo:





{

"tipologia": "",



"localizacao": "",



"procedimento": "",



"programa": "",



"criterios\_avaliacao": "",



"exigencias": {}



}







\---



\# Critérios de avaliação





\## 1. Compatibilidade de área





Comparar:



Experiência da empresa



com



Programa do concurso







Peso:



25%







\---



\## 2. Interesse estratégico





Comparar:



Preferências indicadas pela empresa



com



Características do concurso







Peso:



25%







\---



\## 3. Capacidade demonstrada





Avaliar:



Existem projetos semelhantes?





Peso:



20%







\---



\## 4. Localização





Comparar:



Geografia pretendida



com



Localização do concurso







Peso:



10%







\---



\## 5. Procedimento





Comparar:



Tipo de concurso



com



Preferências da empresa







Peso:



10%







\---



\## 6. Risco





Avaliar:



\- prazo;

\- complexidade;

\- requisitos;

\- concorrência esperada.







Peso:



10%







\---



\# Resultado





Gerar:





{

"score": 0-100,





"recommendation":



"Participar",



"Analisar",



"Não prioritário",





"reasons":\[],



"risks":\[],



"recommended\_strategy":""



}







\---



\# Explicação obrigatória





O sistema nunca deve apresentar apenas um número.





Exemplo:





Score:



87%





Motivos:



\+ Concurso de conceção alinhado com estratégia da empresa



\+ Experiência comprovada em tipologia semelhante



\+ Localização prioritária





Riscos:



\- Prazo reduzido

\- Necessidade de equipa multidisciplinar





\---



\# Aprendizagem





Após decisão da empresa:





Guardar:





{

"concurso\_id":"",



"empresa\_id":"",



"score\_ai":87,



"decisao\_empresa":



"participar",



"data":""



}







Estas decisões serão usadas para melhorar futuras recomendações.

