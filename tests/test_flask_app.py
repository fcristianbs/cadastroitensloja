import unittest
from unittest.mock import patch
from app import create_app

class FlaskAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_index_page(self):
        """Testa carregamento da página inicial do painel."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VOXEL LAB', response.data)
        self.assertIn(b'Cadastrar Novo Produto', response.data)
        self.assertIn(b'RN05', response.data)

    def test_produtos_page(self):
        """Testa listagem de produtos existentes."""
        response = self.client.get('/produtos')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Produtos Cadastrados', response.data)
        self.assertIn(b'suporte-starlink', response.data)

    def test_git_status_page(self):
        """Testa página de diagnóstico Git."""
        response = self.client.get('/git-status')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Diagn', response.data)

    def test_api_check_slug(self):
        """Testa API de verificação de slug em tempo real."""
        # Slug existente
        res_existing = self.client.get('/api/check-slug?slug=suporte-starlink-mini-veicular')
        self.assertEqual(res_existing.status_code, 200)
        data = res_existing.get_json()
        self.assertFalse(data['available'])

        # Slug inexistente
        res_new = self.client.get('/api/check-slug?slug=peca-totalmente-inedita-xyz-999')
        self.assertEqual(res_new.status_code, 200)
        data_new = res_new.get_json()
        self.assertTrue(data_new['available'])

    def test_api_produtos_list(self):
        """Testa endpoint de produtos em JSON."""
        res = self.client.get('/api/produtos')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_api_git_status_and_push_endpoint(self):
        """Testa endpoints de git status."""
        res_status = self.client.get('/api/git/status')
        self.assertEqual(res_status.status_code, 200)
        data = res_status.get_json()
        self.assertTrue(data.get('is_git_repo'))

    def test_api_categorias(self):
        """Testa endpoint de categorias dinâmicas em JSON."""
        res = self.client.get('/api/categorias')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        slugs = [c.get('slug') for c in data]
        self.assertIn('engenharia', slugs)
        self.assertIn('setup-games', slugs)
        self.assertIn('presentes', slugs)

    def test_editar_page(self):
        """Testa carregamento da página de edição de um produto existente."""
        response = self.client.get('/editar/suporte-starlink-mini-veicular')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Modo Edi', response.data)
        self.assertIn(b'suporte-starlink-mini-veicular', response.data)
        self.assertIn(b'Salvar Altera', response.data)

    def test_produtos_page_has_actions_and_modals(self):
        """Testa se a página de produtos contém os botões de ação e modais."""
        response = self.client.get('/produtos')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'btn-toggle-esgotado', response.data)
        self.assertIn(b'btn-excluir-produto', response.data)
        self.assertIn(b'modal-confirm-delete', response.data)
        self.assertIn(b'modal-confirm-toggle', response.data)
        self.assertIn(b'filtro-status', response.data)

    @patch('app.routes.run_delete_pipeline')
    def test_post_excluir_produto_ajax(self, mock_delete_pipe):
        """Testa chamada AJAX para exclusão de produto."""
        mock_delete_pipe.return_value = {
            'success': True,
            'commit_hash': 'a1b2c3d',
            'commit_message': 'feat(catalogo): remover produto Teste (teste-slug)',
            'pushed': True,
            'logs': [{'step': 'JSON_DELETE', 'status': 'SUCCESS', 'message': 'Removido'}]
        }
        res = self.client.post(
            '/produtos/teste-slug/excluir',
            data={'auto_push': 'true'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['commit_hash'], 'a1b2c3d')
        mock_delete_pipe.assert_called_once_with('teste-slug', auto_push=True)

    @patch('app.routes.run_toggle_esgotado_pipeline')
    def test_post_toggle_esgotado_ajax(self, mock_toggle_pipe):
        """Testa chamada AJAX para alternar status de esgotado."""
        mock_toggle_pipe.return_value = {
            'success': True,
            'esgotado': True,
            'commit_hash': 'e5f6g7h',
            'commit_message': 'feat(catalogo): marcar produto como esgotado',
            'pushed': True,
            'logs': [{'step': 'STATUS_UPDATE', 'status': 'SUCCESS', 'message': 'Esgotado'}]
        }
        res = self.client.post(
            '/produtos/teste-slug/toggle-esgotado',
            data={'auto_push': 'true'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['esgotado'])
        mock_toggle_pipe.assert_called_once_with('teste-slug', auto_push=True)

    @patch('app.routes.run_delete_pipeline')
    @patch('app.routes.run_toggle_esgotado_pipeline')
    def test_api_endpoints_excluir_and_toggle(self, mock_toggle, mock_delete):
        """Testa endpoints da API JSON /api/produtos/<slug>/..."""
        mock_delete.return_value = {'success': True, 'commit_hash': '111'}
        mock_toggle.return_value = {'success': True, 'esgotado': False, 'commit_hash': '222'}

        res_del = self.client.post('/api/produtos/item-x/excluir', json={'auto_push': False})
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()['success'])
        mock_delete.assert_called_once_with('item-x', auto_push=False)

        res_tog = self.client.post('/api/produtos/item-x/toggle-esgotado', json={'auto_push': True})
        self.assertEqual(res_tog.status_code, 200)
        self.assertTrue(res_tog.get_json()['success'])
        mock_toggle.assert_called_once_with('item-x', auto_push=True)

if __name__ == '__main__':
    unittest.main()

