\# CNLL Company Intelligence

\# Company Interviewer Engine Architecture





\## Objetivo



Criar um sistema de entrevista inteligente capaz de completar o perfil de uma empresa através de perguntas adaptativas.



O interviewer não funciona como um formulário fixo.



Analisa:



\- informação existente;

\- informação em falta;

\- qualidade dos dados;

\- objetivos estratégicos;



e decide qual a próxima pergunta mais relevante.





\---



\# Princípio





A pergunta seguinte deve maximizar o valor da informação recolhida.





Não perguntar:



"Qual é a área da empresa?"





Quando já existe informação:



"Empresa trabalha em arquitetura pública e reabilitação."





Perguntar:



"Qual destas áreas representa uma prioridade estratégica nos próximos concursos?"







\---



\# Inputs





O Interviewer recebe:





Company Profile



\+



Company Strategy



\+



AI Memory



\+



Documentos analisados



\+



Histórico de respostas







\---



\# Output





O sistema gera:





Question



\+



Reason



\+



Answer Type



\+



Impact on Profile







Exemplo:





Pergunta:



"Que importância têm concursos internacionais para a empresa?"





Motivo:



"Informação necessária para ajustar recomendações futuras."





Tipo:



multiple\_choice





Impacto:



strategy.international\_interest







\---



\# Tipos de perguntas





\## Escolha múltipla





Para preferências.





Exemplo:





Que tipologias são prioritárias?





\[] Cultura



\[] Habitação



\[] Educação



\[] Saúde







\---



\## Escala





Para intensidade.





Exemplo:





Qual o interesse nesta área?





0 - Sem interesse



1 - Curiosidade



2 - Interesse futuro



3 - Área estratégica







\---



\## Texto livre





Para informação única.





Exemplo:





"Descreva a abordagem diferenciadora da empresa."







\---



\## Confirmação





Para validar informação extraída.





Exemplo:





"Identificámos experiência em escolas. Esta informação está correta?"





Sim



Não



Corrigir







\---



\# Estados da informação





Cada informação possui:





CONFIRMADO



VALIDAR



DESCONHECIDO



CONTRADITÓRIO







\---



\# Motor de decisão





O interviewer avalia:





1\. Informação inexistente





Exemplo:



Não existe informação sobre localização.





Criar pergunta.







2\. Informação incompleta





Exemplo:



Existe projeto mas falta tipologia.





Perguntar.







3\. Informação contraditória





Exemplo:



Website diz uma coisa e portfolio outra.





Perguntar.







4\. Informação estratégica





Mesmo existindo informação pública, perguntar preferências futuras.







\---



\# Priorização





Cada pergunta recebe score:





importance



\+



uncertainty



\+



impact\_on\_matching







Perguntas com maior impacto aparecem primeiro.







\---



\# Exemplo de fluxo





Entrada:





Website analisado.



Portfolio analisado.







Perfil criado:



60% completo.







Interviewer:





Pergunta 1:



"Quais são as tipologias onde pretendem concentrar concursos?"







Resposta:





"Cultura e equipamentos públicos"







Atualização:





strategy.priority\_areas







Nova pergunta:





"Qual a escala mínima de projeto pretendida?"







\---



\# Ligação ao Matching Engine





O interviewer existe para melhorar:





Company Profile



↓



Matching Engine



↓



Score concursos







Melhor informação



=



Melhores recomendações







\---



\# Ligação ao Response Generator





Informação recolhida permite:





"Porque deve a empresa participar neste concurso?"





Resposta baseada em:





\- experiência;

\- estratégia;

\- diferenciação;

\- objetivos.







\---



\# Regras





Nunca assumir respostas.



Nunca transformar texto extraído em preferência estratégica.



Separar:



factos



de



intenções.







\---



\# Futuro





Preparado para:





\- LLM question planner;

\- aprendizagem com respostas;

\- comparação entre empresas;

\- sugestões automáticas;

\- atualização contínua do perfil.

