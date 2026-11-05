import unittest
from unittest.mock import patch, MagicMock
from app.services.product_service import (
    generate_slug,
    validate_product_data,
    build_product_record,
    load_categorias,
    get_allowed_category_slugs,
    delete_product,
    toggle_esgotado_product
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
        """Testa RN02: Apenas categorias existentes na taxonomia dinâmica são aceitas."""
        allowed_cats = get_allowed_category_slugs()
        self.assertGreater(len(allowed_cats), 0, "Deveria carregar pelo menos uma categoria dinâmica.")

        for cat in allowed_cats:
            data = {
                "nome": "Produto Teste",
                "slug": "produto-teste",
                "categoria": cat,
                "subcategoria": "geral",
                "resumo": "Resumo teste",
                "descricao": "Descricao teste",
                "uso": "interno",
                "material": "PLA",
                "imagens": [{"src": "/static/img/teste.png"}]
            }
            valid, errors = validate_product_data(data, is_new=False)
            self.assertTrue(valid, f"Categoria dinâmica {cat} falhou: {errors}")

        # Categoria inválida que não existe em data/categorias.json
        data_invalida = {
            "nome": "Produto Inválido",
            "slug": "produto-invalido",
            "categoria": "eletronicos-inexistentes",
            "subcategoria": "geral",
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "interno",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_invalida, is_new=False)
        self.assertFalse(valid)
        self.assertTrue(any("Categoria 'eletronicos-inexistentes' inválida" in e for e in errors))

    def test_rn05_material_vs_uso(self):
        """Testa RN05: Regra de Material vs Uso (PLA proibido em uso externo)."""
        # Caso 1: Externo com PLA -> DEVE FALHAR
        data_externo_pla = {
            "nome": "Suporte Externo",
            "slug": "suporte-externo",
            "categoria": "engenharia",
            "subcategoria": "suportes",
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
            "subcategoria": "suportes",
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
            "subcategoria": "suportes",
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
            "subcategoria": "cases",
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

    @patch('app.services.product_service.save_produtos')
    @patch('app.services.product_service.load_produtos')
    def test_delete_product(self, mock_load, mock_save):
        """Testa exclusão de produto do array de produtos."""
        fake_db = [
            {"slug": "item-1", "nome": "Item 1"},
            {"slug": "item-2", "nome": "Item 2"}
        ]
        mock_load.return_value = list(fake_db)

        # Exclui item existente
        success, removed = delete_product("item-1")
        self.assertTrue(success)
        self.assertEqual(removed["slug"], "item-1")
        mock_save.assert_called_once()
        saved_list = mock_save.call_args[0][0]
        self.assertEqual(len(saved_list), 1)
        self.assertEqual(saved_list[0]["slug"], "item-2")

        # Tenta excluir item inexistente
        mock_save.reset_mock()
        mock_load.return_value = list(fake_db)
        success_inexistente, removed_none = delete_product("item-inexistente")
        self.assertFalse(success_inexistente)
        self.assertIsNone(removed_none)
        mock_save.assert_not_called()

    @patch('app.services.product_service.save_produtos')
    @patch('app.services.product_service.load_produtos')
    def test_toggle_esgotado_product(self, mock_load, mock_save):
        """Testa alternância de produto entre esgotado e ativo."""
        fake_db = [
            {"slug": "item-1", "nome": "Item 1", "esgotado": False, "selo": "NOVO"}
        ]
        mock_load.return_value = fake_db

        # 1. Ativo -> Esgotado
        success, novo_status, prod = toggle_esgotado_product("item-1")
        self.assertTrue(success)
        self.assertTrue(novo_status)
        self.assertTrue(prod["esgotado"])
        self.assertEqual(prod["selo"], "ESGOTADO")
        self.assertEqual(prod["selo_anterior"], "NOVO")
        mock_save.assert_called_once()

        # 2. Esgotado -> Reativar
        mock_save.reset_mock()
        success, novo_status, prod = toggle_esgotado_product("item-1")
        self.assertTrue(success)
        self.assertFalse(novo_status)
        self.assertFalse(prod["esgotado"])
        self.assertEqual(prod["selo"], "NOVO")
        mock_save.assert_called_once()

    def test_multi_category_validation_and_build(self):
        """Testa suporte e validações de múltiplas categorias e subcategorias."""
        data_multi = {
            "nome": "Luminária Onda Tech",
            "slug": "luminaria-onda-tech",
            "categorias": ["casa", "setup-games"],
            "subcategorias": ["decoracao", "desktop"],
            "resumo": "Luminária híbrida para ambiente de quarto ou setup gamer.",
            "descricao": "Desc",
            "uso": "interno",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_multi, is_new=False)
        self.assertTrue(valid, f"Deveria aceitar múltiplas categorias válidas: {errors}")

        record = build_product_record(data_multi)
        self.assertEqual(record["categorias"], ["casa", "setup-games"])
        self.assertEqual(record["subcategorias"], ["decoracao", "desktop"])
        # Retrocompatibilidade: primeiro item vira o campo primário
        self.assertEqual(record["categoria"], "casa")
        self.assertEqual(record["subcategoria"], "decoracao")

    def test_multi_category_invalid_subcategory_check(self):
        """Testa que subcategoria não pertencente às categorias ativas é rejeitada."""
        data_invalida = {
            "nome": "Peça Errada",
            "slug": "peca-errada",
            "categorias": ["setup-games"],
            "subcategorias": ["starlink"],  # starlink pertence a engenharia, não setup-games!
            "resumo": "Resumo",
            "descricao": "Desc",
            "uso": "interno",
            "material": "PLA",
            "imagens": [{"src": "/static/img/teste.png"}]
        }
        valid, errors = validate_product_data(data_invalida, is_new=False)
        self.assertFalse(valid)
        self.assertTrue(any("Subcategoria 'starlink' não pertence" in e for e in errors))

    @patch('app.services.git_service.run_git_command')
    @patch('app.services.git_service.get_file_content_from_ref')
    @patch('app.services.product_service.load_produtos')
    def test_get_pending_batch_status(self, mock_load_prod, mock_git_show, mock_git_cmd):
        """Testa cálculo de alterações pendentes no lote."""
        import json
        from app.services.product_service import get_pending_batch_status

        mock_git_cmd.return_value = (True, "0\n", "")
        # Git remoto tem item-1 e item-2
        remote_catalog = [
            {"slug": "item-1", "nome": "Item 1", "preco": 10.0, "esgotado": False},
            {"slug": "item-2", "nome": "Item 2", "preco": 20.0, "esgotado": False}
        ]
        mock_git_show.return_value = json.dumps(remote_catalog)

        # Localmente: item-1 foi editado, item-2 removido, item-3 novo
        local_catalog = [
            {"slug": "item-1", "nome": "Item 1 Editado", "preco": 15.0, "esgotado": False},
            {"slug": "item-3", "nome": "Item 3 Novo", "preco": 30.0, "esgotado": False}
        ]
        mock_load_prod.return_value = local_catalog

        status = get_pending_batch_status()
        self.assertTrue(status["has_pending"])
        self.assertEqual(status["total_pending"], 3)
        novos_slugs = [x["slug"] for x in status["novos"]]
        editados_slugs = [x["slug"] for x in status["editados"]]
        removidos_slugs = [x["slug"] for x in status["removidos"]]
        self.assertIn("item-3", novos_slugs)
        self.assertIn("item-1", editados_slugs)
        self.assertIn("item-2", removidos_slugs)
        self.assertIn("1 novo", status["summary_text"])
        self.assertIn("1 editado", status["summary_text"])
        self.assertIn("1 removido", status["summary_text"])

if __name__ == "__main__":
    unittest.main()

