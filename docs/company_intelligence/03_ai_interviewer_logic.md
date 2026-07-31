\# CNLL Company Intelligence

\# AI Interviewer Logic





\## Objetivo





O AI Interviewer é o sistema responsável por completar e validar a inteligência da empresa através de perguntas adaptativas.





Não funciona como um formulário fixo.





Primeiro analisa a informação existente.



Depois identifica lacunas.



Finalmente cria perguntas com maior impacto para melhorar a qualidade do perfil.







\---



\# Princípio fundamental





O interviewer nunca começa por perguntar.





Antes de criar perguntas analisa:





\- informação existente;

\- fonte da informação;

\- confiança;

\- impacto no matching;

\- importância estratégica.







Uma pergunta só deve existir quando a resposta pode melhorar a inteligência da empresa ou dos membros.







\---



\# Arquitetura de entrevista





Existem dois níveis de entrevista:





\## 1. Company Interviewer





Focado na identidade institucional.





Analisa:





\- posicionamento;

\- serviços;

\- metodologia;

\- valores;

\- estratégia;

\- áreas prioritárias.







Exemplo:





"Quais são as áreas onde a empresa pretende concentrar novos concursos?"







\---



\## 2. Member Interviewer





Focado na identidade profissional individual.





Analisa:





\- experiência;

\- competências;

\- especializações;

\- interesses;

\- objetivos profissionais.







Exemplo:





"Que tipologias de projeto representam maior interesse profissional?"







\---



\# Processo





\## 1. Recolha de informação





Fontes:





\- website;

\- portfolio;

\- documentos;

\- projetos;

\- respostas dos utilizadores.













\---



\## 2. Construção inicial





O sistema cria:





Company Information



\+



Member Profiles



\+



Company Intelligence inicial







Cada informação deve possuir:





\- valor;

\- fonte;

\- confiança;

\- estado.







\---



\# Estados da informação





Cada elemento deve ser classificado:





\## CONFIRMADO





Informação validada pelo utilizador ou fonte segura.







\## EXTRAÍDO





Informação encontrada automaticamente.







\## VALIDAR





Informação encontrada mas necessita confirmação.







\## DESCONHECIDO





Informação inexistente.







\## CONTRADITÓRIO





Existem fontes incompatíveis.







\---



\# Identificação de lacunas





O sistema cria perguntas apenas quando:





\- falta informação importante;

\- confiança é baixa;

\- informação influencia recomendações;

\- existe contradição;

\- existe oportunidade estratégica.







\---



\# Priorização das perguntas





Cada pergunta recebe um valor:





importance



\+



uncertainty



\+



matching\_impact







Perguntas com maior impacto são apresentadas primeiro.







\---



\# Tipos de perguntas





\## Validação





Confirmar informação extraída.





Exemplo:





"Identificámos experiência em equipamentos públicos. Esta informação está correta?"





Respostas:





\- Sim

\- Não

\- Corrigir







\---



\## Escala





Avaliar intensidade de interesse.





Exemplo:





"Qual o interesse da empresa nesta área?"





Escala:





0 - Sem interesse



1 - Baixo



2 - Interesse futuro



3 - Relevante



4 - Prioritário



5 - Estratégico







\---



\## Seleção múltipla





Escolher várias áreas.





Exemplo:





"Que tipologias são prioritárias?"





\- Cultura

\- Educação

\- Saúde

\- Habitação

\- Espaço público







\---



\## Ordenação





Definir prioridades.





Exemplo:





"Ordene as áreas estratégicas para os próximos anos."







\---



\## Texto livre





Usado quando é necessária informação única.





Exemplo:





"Como descrevem a abordagem diferenciadora da empresa?"







\---



\# Atualização da inteligência





Uma resposta nunca deve substituir informação existente sem validação.





Fluxo:





Pergunta



↓



Resposta



↓



Validação



↓



Atualização do perfil



↓



Nova análise de lacunas







\---



\# Relação com Matching Engine





O objetivo do interviewer é melhorar:





Company Intelligence



\+



Member Profiles





que alimentam:





Concurso



↓



Matching



↓



Score







\---



\# Relação com Response Generator





Informação recolhida permite criar respostas baseadas em:





\- experiência real;

\- competências existentes;

\- equipa disponível;

\- estratégia definida.







\---



\# Regras fundamentais





Nunca inventar competências.





Nunca transformar intenção em facto.





Nunca assumir que a empresa quer determinada área apenas porque possui experiência.





Separar sempre:





Factos



Preferências



Objetivos



Possibilidades







\---



\# Evolução futura





Preparado para:





\- LLM question planner;

\- aprendizagem com respostas;

\- perguntas personalizadas por empresa;

\- perguntas personalizadas por membro;

\- atualização contínua da inteligência empresarial.

