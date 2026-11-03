import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from werkzeug.datastructures import FileStorage
from app.config import Config
from app.services.image_service import save_product_image
from app.services.product_service import (
    load_produtos,
    save_produtos,
    insert_product,
    build_product_record
)

class ImageAndJsonTestCase(unittest.TestCase):
    def setUp(self):
        # Cria ambiente temporário
        self.temp_dir = Path(tempfile.mkdtemp())
        self.orig_repo = Config.REPO_PATH
        Config.reload_config(str(self.temp_dir))
        
        # Cria estrutura de pastas
        (self.temp_dir / 'data').mkdir(parents=True, exist_ok=True)
        (self.temp_dir / 'data' / 'produtos.json').write_text("[]", encoding="utf-8")

    def tearDown(self):
        Config.reload_config(str(self.orig_repo))
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_product_image_mirrored(self):
        """Testa se a imagem é salva e espelhada nos 2 diretórios obrigatórios."""
        file_bytes = b"fake-png-content-voxel-lab-12345"
        storage = FileStorage(
            stream=io.BytesIO(file_bytes),
            filename="foto_camera_original.png",
            content_type="image/png"
        )
        
        info = save_product_image(
            file_storage=storage,
            slug="suporte-teste-veicular",
            alt_text="Suporte Teste",
            image_type="instalada"
        )
        
        # Verifica src retornado
        self.assertEqual(info["src"], "/static/img/produtos/suporte-teste-veicular.png")
        self.assertEqual(info["filename"], "suporte-teste-veicular.png")
        
        # Verifica existência física nos 2 caminhos
        static_file = Path(info["static_path"])
        public_file = Path(info["public_path"])
        
        self.assertTrue(static_file.exists(), "Arquivo não salvo em static/")
        self.assertTrue(public_file.exists(), "Arquivo não espelhado em public/static/")
        self.assertEqual(static_file.read_bytes(), file_bytes)
        self.assertEqual(public_file.read_bytes(), file_bytes)

    def test_json_formatting_and_utf8(self):
        """Testa se o produtos.json é salvo com UTF-8, indent=2 e acentos preservados."""
        record = build_product_record({
            "nome": "Fixação de Antena · Veicular",
            "slug": "fixacao-antena-veicular",
            "categoria": "engenharia",
            "subcategoria": "starlink",
            "resumo": "Fixação aerodinâmica de alta precisão.",
            "descricao": "Resistente à tração mecânica e radiação UV.",
            "preco": 189.90,
            "material": "PETG-UV",
            "uso": "externo",
            "imagens": [{"src": "/static/img/produtos/fixacao.png"}]
        })
        
        insert_product(record, position="top")
        
        # Lê o conteúdo bruto do arquivo
        json_file = Config.PRODUTOS_JSON_PATH
        raw_text = json_file.read_text(encoding="utf-8")
        
        # Confere se os caracteres acentuados NÃO foram convertidos para \uXXXX
        self.assertIn("Fixação", raw_text)
        self.assertIn("aerodinâmica", raw_text)
        self.assertIn("radiação", raw_text)
        
        # Confere indentação de 2 espaços
        self.assertIn('  {\n    "slug": "fixacao-antena-veicular"', raw_text)
        
        # Carrega com json.loads para validar integridade
        data = json.loads(raw_text)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "fixacao-antena-veicular")
        self.assertEqual(data[0]["preco"], 189.90)

if __name__ == '__main__':
    unittest.main()

