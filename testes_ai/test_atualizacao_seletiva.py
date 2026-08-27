import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from app import database

class AtualizacaoSeletivaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=database.DB_PATH; database.DB_PATH=Path(self.tmp.name)/"db.sqlite"; database.criar_base_dados(); self.link="https://base.example/x"; self.id=database.guardar_concurso("X","E",self.link,"2026-07-01",criterio_tipo="Monofator",criterio_resumo="Preco 100%")
 def tearDown(self):
  database.DB_PATH=self.old
  try: self.tmp.cleanup()
  except PermissionError: pass
 def test_novo_existente_igual_e_alterado(self):
  self.assertFalse(database.atualizar_concurso_existente_se_alterado(self.link,{"preco_base":None})["changed"])
  changed=database.atualizar_concurso_existente_se_alterado(self.link,{"criterio_tipo":"Multifator","criterio_resumo":"Qualidade 70% · Preco 30%","link_pecas":"https://official/x-v2.pdf"})
  self.assertTrue(changed["changed"]); self.assertIn("criterio_tipo",changed["changed_fields"])
  database.atualizar_dados_concurso(self.link,criterio_tipo="Multifator",criterio_resumo="Qualidade 70% · Preco 30%")
  with closing(database.abrir_conexao()) as con:
   row=con.execute("SELECT id,has_updates,changed_fields,criterio_tipo FROM concursos WHERE link=?",(self.link,)).fetchone(); history=con.execute("SELECT campo,valor_anterior,valor_novo FROM concurso_alteracoes WHERE concurso_id=?",(self.id,)).fetchall()
  self.assertEqual(row["id"],self.id); self.assertEqual(row["criterio_tipo"],"Multifator"); self.assertEqual(row["has_updates"],1); self.assertTrue(history)
if __name__=='__main__': unittest.main()