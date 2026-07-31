\# CNLL Company Intelligence

\# Member Identity Architecture





\## Objetivo



Criar uma camada de identidade profissional individual dentro da empresa.



A inteligência da empresa não deve ser criada apenas através de um perfil coletivo.



Deve resultar da combinação de:



\- pessoas;

\- competências;

\- experiências;

\- interesses;

\- objetivos;

\- conhecimento acumulado.





\---



\# Princípio





A empresa é uma entidade agregadora.



Cada membro possui uma identidade profissional própria.





Arquitetura:





Company



|



+---- Member A



|        |



|        +---- Member Profile



|



+---- Member B



&#x20;        |



&#x20;        +---- Member Profile







A inteligência da empresa é construída através da agregação destas identidades.





\---



\# Estrutura





\## Company





Representa o gabinete/escritório.





Contém:



\- nome;

\- website;

\- informação institucional;

\- dados administrativos.





Não contém diretamente toda a identidade profissional da equipa.







\---



\# Company Members





Representa a relação entre uma pessoa e uma empresa.





Campos:





id



company\_id



user\_id



role



status



created\_at







Exemplos de roles:





owner



admin



architect



designer



collaborator







\---



\# Member Profile





Representa a identidade profissional individual.





Estrutura:





{

identity:{},



experience:{},



competences:{},



preferences:{},



goals:{},



visibility:{}



}







\---



\# Identity





Informação profissional:





\- nome;

\- função;

\- especialidade;

\- descrição profissional;

\- formação relevante.





\---



\# Experience





Experiência acumulada:





\- projetos;

\- tipologias;

\- setores;

\- localização;

\- responsabilidades;

\- competências demonstradas.







\---



\# Competences





Conhecimentos:





\- BIM;

\- coordenação;

\- visualização;

\- investigação;

\- gestão;

\- outras competências.







\---



\# Preferences





Interesses profissionais:





\- tipologias preferidas;

\- setores de interesse;

\- escalas de projeto;

\- geografias.







Estas preferências podem influenciar matching futuro.







\---



\# Goals





Objetivos profissionais:





Exemplos:





\- desenvolver experiência internacional;

\- trabalhar em determinada tipologia;

\- aumentar participação em concursos.







\---



\# Visibility





Nem toda a informação deve ser partilhada.





Campos públicos dentro da empresa:





\- experiência;

\- competências;

\- projetos;

\- especializações.





Campos privados:





\- objetivos pessoais;

\- notas pessoais;

\- preferências privadas.







\---



\# Relação com Company Intelligence





A empresa não substitui os perfis individuais.





A inteligência empresarial é uma agregação:





Member Profiles



\+



Company Information



\+



Project History



\+



Decisions





=



Company Intelligence







\---



\# Relação com concursos





Quando um concurso é analisado:





Concurso



\+



Empresa



\+



Membros relevantes





↓



Compatibilidade







Exemplo:





Concurso:



Museu





Empresa:



Experiência cultural média.





Membro A:



Experiência em museus.





Membro B:



Especialista BIM.





Resultado:





Equipa adequada para responder ao concurso.







\---



\# Relação com AI Interviewer





Existem dois tipos de entrevistas:





\## Company Interviewer





Perguntas institucionais.





Exemplo:





"Quais são as áreas estratégicas da empresa?"







\## Member Interviewer





Perguntas individuais.





Exemplo:





"Que tipo de projetos gostaria de desenvolver nos próximos anos?"







\---



\# Regras





A AI nunca deve assumir competências de uma pessoa.





Toda a informação individual deve ter origem em:



\- resposta do utilizador;

\- documentos autorizados;

\- validação.







\---



\# Futuro





Preparado para:





\- equipas multidisciplinares;

\- matching de pessoas a concursos;

\- distribuição automática de tarefas;

\- evolução profissional;

\- aprendizagem individual.

