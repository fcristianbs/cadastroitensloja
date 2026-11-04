import unittest
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

    def test_editar_page(self):
        """Testa carregamento da página de edição de um produto existente."""
        response = self.client.get('/editar/suporte-starlink-mini-veicular')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Modo Edi', response.data)
        self.assertIn(b'suporte-starlink-mini-veicular', response.data)
        self.assertIn(b'Salvar Altera', response.data)

if __name__ == '__main__':
    unittest.main()

