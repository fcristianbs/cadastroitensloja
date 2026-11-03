import unittest
from app.services.product_service import (
    generate_slug,
    validate_product_data,
    build_product_record,
    CATEGORIAS_PERMITIDAS
)

class ProductServiceTestCase(unittest.TestCase):
    
    def test_slug_generation(self):
        """Testa geração de slugs em kebab-case limpos e sem acentos."""
        self.assertEqual(
            generate_slug("Suporte Starlink Mini · Veicular"),
            "suporte-starlink-mini-veicular"
        )
        self.assertEqual(
            generate_slug("Suporte Starlink Mini · Tubo 1\""),
            "suporte-starlink-mini-tubo-1"
        )
        self.assertEqual(
            generate_slug("Adaptador de mangueira 3/4\" -> 1/2\""),
            "adaptador-de-mangueira-3-4-1-2"
        )
        self.assertEqual(
            generate_slug("Presilha de reposição · Persiana (4 un.)"),
            "presilha-de-reposicao-persiana-4-un"
        )

    def test_rn02_categoria_permitida(self):
        """Testa RN02: Apenas categorias permitidas são aceitas."""
        for cat in CATEGORIAS_PERMITIDAS:
            data = {
                "nome": "Produto Teste",
                "slug": "produto-teste",
                "categoria": cat,
                "resumo": "Resumo teste",
                "descricao": "Descricao teste",
                "uso": "interno",
                "material": "PLA",
                "imagens": [{"src": "/static/img/teste.png"}]
            }
            valid, errors = validate_product_data(data, is_new=False)
            self.assertTrue(valid, f"Categoria válida {cat} falhou: {errors}")

        # Categoria inválida
        data_invalida = {
            "nome": "Produto Inválido",
            "slug": "produto-invalido",
            "categoria": "eletronicos",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "interno",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_invalida, is_new=False)
        self.assertFalse(valid)
        self.assertTrue(any("Categoria 'eletronicos' inválida" in e for e in errors))

    def test_rn05_material_vs_uso(self):
        """Testa RN05: Regra de Material vs Uso (PLA proibido em uso externo)."""
        # Caso 1: Externo com PLA -> DEVE FALHAR
        data_externo_pla = {
            "nome": "Suporte Externo",
            "slug": "suporte-externo",
            "categoria": "engenharia",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "externo",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_externo_pla, is_new=False)
        self.assertFalse(valid)
        self.assertTrue(any("Regra RN05 violada" in e for e in errors))

        # Caso 2: Externo com PETG-UV -> DEVE PASSAR
        data_externo_petg_uv = {
            "nome": "Suporte Externo UV",
            "slug": "suporte-externo-uv",
            "categoria": "engenharia",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "externo",
            "material": "PETG-UV",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_externo_petg_uv, is_new=False)
        self.assertTrue(valid, f"PETG-UV deveria ser aceito: {errors}")

        # Caso 3: Externo com ASA -> DEVE PASSAR
        data_externo_asa = {
            "nome": "Suporte Externo ASA",
            "slug": "suporte-externo-asa",
            "categoria": "engenharia",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "externo",
            "material": "ASA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_externo_asa, is_new=False)
        self.assertTrue(valid, f"ASA deveria ser aceito: {errors}")

        # Caso 4: Interno com PLA -> DEVE PASSAR
        data_interno_pla = {
            "nome": "Suporte Interno PLA",
            "slug": "suporte-interno-pla",
            "categoria": "gadgets",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "interno",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_interno_pla, is_new=False)
        self.assertTrue(valid, f"PLA interno deveria ser aceito: {errors}")

    def test_build_product_record_schema(self):
        """Verifica se build_product_record gera o schema completo e correto."""
        raw = {
            "nome": "Suporte Starlink Mini · Veicular",
            "slug": "suporte-starlink-mini-veicular",
            "categoria": "engenharia",
            "subcategoria": "starlink",
            "resumo": "Fixação aerodinâmica de alta resistência.",
            "descricao": "Projetado em PETG-UV.",
            "preco": "149.90",
            "precoParcelado": "ou 3x de R$ 49,90",
            "material": "PETG-UV",
            "uso": "externo",
            "specs_resumo": "aerodinâmico · UV",
            "destaque": True,
            "selo": "NOVO",
            "ordem": 1,
            "specs": [{"chave": "MATERIAL", "valor": "PETG-UV"}],
            "variacoes": [{
                "nome": "Fixação",
                "opcoes": ["Rack de Teto", "Ventosa"],
                "padrao": "Rack de Teto",
                "permiteOutraMedida": True
            }],
            "cores": [{"nome": "Preto", "hex": "#111111", "padrao": True}],
            "imagens": [{"src": "/static/img/produtos/teste.png", "alt": "Teste", "tipo": "instalada"}],
            "instalacao": ["Passo 1", "Passo 2"],
            "mercadoLivreUrl": "https://mercadolivre.com.br/item",
            "relacionados": ["suporte-starlink-mini-tubo-1"]
        }
        record = build_product_record(raw)
        self.assertEqual(record["slug"], "suporte-starlink-mini-veicular")
        self.assertEqual(record["preco"], 149.90)
        self.assertEqual(record["destaque"], True)
        self.assertEqual(record["selo"], "NOVO")
        self.assertEqual(len(record["specs"]), 1)
        self.assertEqual(len(record["variacoes"]), 1)
        self.assertEqual(len(record["cores"]), 1)
        self.assertEqual(len(record["instalacao"]), 2)
        self.assertEqual(record["mercadoLivreUrl"], "https://mercadolivre.com.br/item")

if __name__ == "__main__":
    unittest.main()

