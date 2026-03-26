# Spotify Playlist Cleaner

Script em Python para limpar playlists **criadas por você** no Spotify, com opções para remover músicas por artista, por nome, duplicadas e faixas lançadas antes de um ano definido.

## Requisitos

- Python **3.10+** (recomendado: 3.11)
- Conta Spotify
- App criado no **Spotify for Developers**
- Dependências do projeto (arquivo `requirements.txt`)

## 1) Criar app no Spotify for Developers

1. Acesse: https://developer.spotify.com  
2. Faça login e clique em **Create app**  
3. Preencha nome/descrição e crie o app  
4. No app criado, copie:
   - **Client ID**
   - **Client Secret**
5. Em **Edit Settings**, adicione um Redirect URI (exemplo):
   - `http://127.0.0.1:8888/callback`
6. Salve as alterações

> O Redirect URI configurado no painel deve ser exatamente o mesmo usado no arquivo `.env`.

## 2) Clonar projeto e preparar ambiente

```bash
git clone https://github.com/MarsoL4/spotify-PlaylistCleaner.git
cd spotify-PlaylistCleaner
```

### (Opcional, recomendado) Criar ambiente virtual

No Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3) Instalar dependências

```bash
pip install -r requirements.txt
```

## 4) Criar arquivo `.env` com credenciais

Crie um arquivo `.env` na raiz do projeto com este conteúdo:

```env
CLIENT_ID='seu_client_id'
CLIENT_SECRET='seu_client_secret'
REDIRECT_URI='seu_redirect_uri'
```

## 5) Executar o programa

```bash
python spotify-clean.py
```

Na primeira execução, o Spotify pedirá autenticão com a sua conta no navegador.  
Após autorizar, volte ao terminal para usar o menu.

## Funcionalidades do menu

1. **Remover músicas de um artista específico**  
2. **Remover uma música específica (por nome)**  
3. **Remover músicas duplicadas** (mesmo nome + mesmos artistas)  
4. **Remover músicas lançadas antes de um ano**  
5. **Sair**

## Observações importantes

- O script lista e manipula apenas playlists **criadas pela sua conta**.
- Em algumas operações o programa pede confirmação antes de remover.
- O projeto já trata paginação de playlist e tentativas em caso de limite da API (rate limit).

## Solução rápida de problemas

- **“As variáveis CLIENT_ID, CLIENT_SECRET ou REDIRECT_URI não estão definidas.”**  
  Verifique se o `.env` existe na raiz e se as chaves estão corretas.

- **Erro de redirect URI**  
  Confirme se o `REDIRECT_URI` no `.env` é idêntico ao URI cadastrado no Spotify Developer Dashboard.

- **Módulo não encontrado (`spotipy` / `dotenv`)**  
  Reinstale as dependências com:
  ```bash
  pip install -r requirements.txt
  ```
