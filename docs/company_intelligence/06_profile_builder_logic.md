\# CNLL Company Intelligence

\# Profile Builder Logic





\## Objetivo





O Profile Builder é responsável por construir a primeira versão da inteligência de uma empresa através de informação existente.





Fontes possíveis:





\- website institucional;

\- portfolio;

\- documentos;

\- projetos;

\- informação fornecida pelos utilizadores.







O objetivo não é criar um perfil definitivo.





O objetivo é criar uma primeira representação que será posteriormente validada pelo Interviewer.







\---



\# Princípio fundamental





O Profile Builder não assume.





Toda a informação criada deve manter:





\- origem;

\- confiança;

\- estado;

\- necessidade de validação.







Nenhuma inferência deve ser transformada em facto.







\---



\# Fluxo geral





\## Entrada





Fontes:





Website



\+



Portfolio PDF



\+



Documentos adicionais







↓



\## Extração





Identificação de:





\- identidade da empresa;

\- serviços;

\- projetos;

\- competências;

\- linguagem institucional;

\- membros identificados;

\- áreas de experiência.







↓



\## Estruturação





Separação em:







Company Information





\+



Member Information





\+



Project Knowledge





\+



Initial Intelligence







↓



\## Validação





O Interviewer analisa:





\- informação incompleta;

\- informação incerta;

\- informação estratégica em falta.







\---



\# Estrutura criada





\## Company Information





Informação institucional:





\- nome;

\- descrição;

\- localização;

\- serviços;

\- metodologia;

\- valores;

\- posicionamento.







Estado:





CONFIRMADO



EXTRAÍDO



VALIDAR







\---



\# Member Information





Quando existirem dados identificáveis:





Criar possíveis Member Profiles.





Exemplo:





Nome:



Função:



Experiência:



Competências:







A informação individual deve sempre ser validada antes de ser associada a um utilizador.







\---



\# Project Knowledge





Extrair projetos:





\- nome;

\- localização;

\- ano;

\- tipologia;

\- descrição;

\- competências demonstradas;

\- fonte.







Cada projeto deve manter:





source



confidence



status







\---



\# Initial Company Intelligence





Construída através de:





Company Information



\+



Member Profiles



\+



Projects







Inclui:





\- competências agregadas;

\- áreas de experiência;

\- padrões identificados;

\- possíveis especializações.







\---



\# Estados da informação





Toda a informação deve possuir:





\## CONFIRMADO





Validada pelo utilizador ou fonte oficial.





\## EXTRAÍDO





Encontrada automaticamente.





\## VALIDAR





Necessita confirmação.





\## PROPOSTA





Possível interpretação estratégica.





\## CONTRADITÓRIO





Existem fontes incompatíveis.







\---



\# Relação com Interviewer





O Profile Builder não faz perguntas.





Responsabilidade:





Extrair



↓



Estruturar



↓



Sinalizar lacunas







O Interviewer:





Analisa lacunas



↓



Cria perguntas



↓



Melhora o perfil







\---



\# Relação com Member Identity





O sistema deve distinguir:





Empresa:





"O gabinete trabalha em equipamentos públicos."





Pessoa:





"Arquitecto X possui experiência em equipamentos públicos."







Nunca misturar capacidades institucionais com capacidades individuais.







\---



\# Relação com Matching Engine





O Profile Builder cria a base para:





Concurso



\+



Company Intelligence



\+



Member Profiles







Resultado:





Score inicial de compatibilidade.







\---



\# Relação com Response Generator





A informação estruturada permite gerar respostas baseadas em:





\- projetos reais;

\- competências comprovadas;

\- equipa disponível;

\- posicionamento estratégico.







\---



\# Regras





Nunca:





\- inventar experiência;

\- atribuir autoria sem confirmação;

\- transformar presença num portfolio em preferência estratégica;

\- assumir competências individuais.







Sempre:





\- guardar fonte;

\- guardar confiança;

\- permitir validação;

\- manter histórico.







\---



\# Evolução futura





Preparado para:





\- extração multimodal;

\- análise de imagens de portfolio;

\- leitura de CVs;

\- identificação automática de equipas;

\- aprendizagem através de validações;

\- criação de knowledge base empresarial.

