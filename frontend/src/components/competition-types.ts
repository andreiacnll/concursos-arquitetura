export type Concurso = {
  id: number;
  titulo: string;
  entidade: string;
  link: string;
  data: string;
  relevante: number;
  data_limite: string | null;
  preco_base: string | null;
  estado: "aberto" | "encerrado" | "sem_prazo";
  distrito?: string | null;
  municipio?: string | null;
  categoria?: string | null;
  tipo_procedimento?: string | null;
};
