\# CNLL Company Intelligence Extraction Architecture





\## 1. Objetivo



O Company Intelligence Extractor é a camada responsável por transformar documentos e fontes externas de uma empresa em informação estruturada para alimentar o sistema de inteligência empresarial.



O objetivo não é criar conteúdos institucionais.



O objetivo é construir conhecimento interno sobre:



\- identidade da empresa;

\- serviços;

\- competências;

\- projetos;

\- equipa;

\- experiência;

\- posicionamento;

\- preferências estratégicas.





\---



\# 2. Princípio fundamental



O extractor nunca deve substituir informação por inferência.



Cada informação extraída deve manter:



\- valor;

\- origem;

\- confiança;

\- estado.





Exemplo:





```json

{

"value": "Experiência em equipamentos públicos",



"source": {

"type": "portfolio\_pdf",

"file": "portfolio.pdf",

"page": 24

},



"confidence": 0.90,



"status": "confirmed"

}

