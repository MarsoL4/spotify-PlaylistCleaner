import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (se existir) no diretório do projeto
load_dotenv()

# Obtenha as credenciais a partir das variáveis de ambiente (ou .env)
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')

# Validação simples: se alguma variável obrigatória não estiver definida, avisa e encerra
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    print("As variáveis CLIENT_ID, CLIENT_SECRET ou REDIRECT_URI não estão definidas.")
    print("Crie um arquivo .env na raiz do projeto com as chaves ou exporte as variáveis de ambiente.")
    print("Exemplo (.env):")
    print("CLIENT_ID='seu_id'")
    print("CLIENT_SECRET='seu_secret'")
    print("REDIRECT_URI='seu_redirect_uri'")
    exit(1)

# Escopos necessários para manipular playlists
SCOPE = 'playlist-modify-public playlist-modify-private playlist-read-private'

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE
))

def show_playlists(playlists):
    print("\nPlaylists criadas por você:")
    for idx, playlist in enumerate(playlists):
        print(f"{idx+1}. {playlist['name']}")

def listar_musicas_playlist(playlist_id):
    print("\nMúsicas na playlist:")
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,artists(name))),next", additional_types=['track'])
    while results:
        for idx, item in enumerate(results['items']):
            track = item['track']
            if track:
                artist_names = ', '.join(artist['name'] for artist in track['artists'])
                print(f"{idx + 1}. {track['name']} - {artist_names}")

        if results['next']:
            results = sp.next(results)
        else:
            break

def get_user_playlists_only(user_id):
    playlists = []
    results = sp.user_playlists(user_id)
    # Pagina todas as playlists
    while results:
        # Adiciona apenas playlists cujo owner é igual ao user_id
        playlists.extend([p for p in results['items'] if p['owner']['id'] == user_id])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists

def remove_artist_from_playlist(playlist_id, artist_name):
    tracks_to_remove = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(id,uri,artists(name))),next", additional_types=['track'])
    while results:
        for item in results['items']:
            track = item['track']
            if track and any(artist['name'].lower() == artist_name.lower() for artist in track['artists']):
                tracks_to_remove.append(track['uri'])

        if results['next']:
            results = sp.next(results)
        else:
            break

    if tracks_to_remove:
        try:
            sp.playlist_remove_all_occurrences_of_items(playlist_id, tracks_to_remove)
            print(f"{len(tracks_to_remove)} músicas removidas do artista '{artist_name}'.")
        except Exception as e:
            print("Erro ao remover músicas:", e)
    else:
        print(f"Nenhuma música do artista '{artist_name}' encontrada na playlist selecionada.")

def remove_music_from_playlist(playlist_id, track_name):
    tracks_to_remove = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(id,uri,name,artists(name))),next", additional_types=['track'])
    while results:
        for item in results['items']:
            track = item['track']
            if track and track['name'].lower() == track_name.lower():
                tracks_to_remove.append(track['uri'])

        if results['next']:
            results = sp.next(results)
        else:
            break

    if tracks_to_remove:
        try:
            sp.playlist_remove_all_occurrences_of_items(playlist_id, list(dict.fromkeys(tracks_to_remove)))
            print(f"{len(tracks_to_remove)} ocorrência(s) da música '{track_name}' removida(s).")
        except Exception as e:
            print("Erro ao remover músicas:", e)
    else:
        print(f"Nenhuma música com o nome '{track_name}' encontrada na playlist selecionada.")

def _chunked_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def remove_duplicates_from_playlist(playlist_id):
    """
    Encontra músicas duplicadas na playlist considerando TANTO o nome quanto os artistas
    (caso-insensitivo). Para cada grupo de duplicatas exibe todas as ocorrências e permite
    que o usuário escolha qual ocorrência (1,2,3...) deseja excluir.
    Implementa chunking ao remover ocorrências específicas para evitar limitações da API.
    """
    print("\nEscaneando playlist em busca de duplicatas (mesmo nome E mesmos artistas)...")
    items = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,artists(name),uri)),next", additional_types=['track'])
    position = 0
    while results:
        for item in results['items']:
            track = item['track']
            if track:
                # Normaliza artistas como string para comparação
                artist_list = [a['name'].strip() for a in track.get('artists', [])]
                artist_key = ','.join(artist_list).lower()
                items.append({
                    'position': position,
                    'added_at': item.get('added_at'),
                    'name': track['name'],
                    'artists': ', '.join(artist_list),
                    'artist_key': artist_key,
                    'uri': track['uri']
                })
                position += 1
        if results['next']:
            results = sp.next(results)
        else:
            break

    # Agrupa por nome de faixa e artistas (caso-insensitivo) para evitar agrupar músicas com mesmo nome mas artistas diferentes
    groups = {}
    for it in items:
        key = f"{it['name'].strip().lower()}||{it['artist_key']}"
        groups.setdefault(key, []).append(it)

    # Filtra apenas grupos com duplicatas
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    if not duplicates:
        print("Nenhuma música duplicada (mesmo nome e mesmos artistas) encontrada nesta playlist.")
        return

    print(f"Foram encontradas {len(duplicates)} música(s) com duplicatas (considerando artistas):")
    to_remove_items = []
    for idx, (group_key, occurrences) in enumerate(duplicates.items(), start=1):
        print(f"\n{idx}) '{occurrences[0]['name']}' - {len(occurrences)} ocorrências (mesmos artistas).")
        # mostra cada ocorrência com índice, posição e data adicionada
        for i, occ in enumerate(occurrences, start=1):
            print(f"   [{i}] Posição: {occ['position']}, Adicionada em: {occ['added_at']}, Artistas: {occ['artists']}")

        # pede para usuário escolher qual ocorrência remover
        while True:
            escolha = input(f"Digite o número da ocorrência que deseja excluir para '{occurrences[0]['name']}' (1-{len(occurrences)}) ou 0 para pular: ").strip()
            if not escolha.isdigit():
                print("Entrada inválida. Digite um número.")
                continue
            escolha_int = int(escolha)
            if escolha_int == 0:
                print("Pulando esta música.")
                break
            if 1 <= escolha_int <= len(occurrences):
                selected = occurrences[escolha_int - 1]
                # adiciona ao lote de remoção com a posição exata
                to_remove_items.append({'uri': selected['uri'], 'positions': [selected['position']]})
                print(f"Selecionada ocorrência na posição {selected['position']} para remoção.")
                break
            else:
                print("Número fora do intervalo. Tente novamente.")

    if not to_remove_items:
        print("Nenhuma remoção selecionada.")
        return

    # Para evitar enviar muitos itens em uma única requisição (e possíveis limites da API),
    # fazemos chunking dos itens de remoção. Usamos um tamanho conservador.
    BATCH_SIZE = 50
    removed_count = 0
    for chunk in _chunked_list(to_remove_items, BATCH_SIZE):
        while True:
            try:
                sp.playlist_remove_specific_occurrences_of_items(playlist_id, chunk)
                removed_count += len(chunk)
                break
            except SpotifyException as e:
                http_status = getattr(e, 'http_status', None)
                headers = getattr(e, 'headers', {}) or {}
                if http_status == 429:
                    retry_after = int(headers.get('Retry-After', '5'))
                    print(f"Rate limit atingido. Aguardando {retry_after} segundos antes de tentar novamente...")
                    time.sleep(retry_after)
                    continue
                else:
                    print("Erro ao remover lote de ocorrências (tentando fallback item-a-item):", e)
                    # fallback item-a-item
                    for item in chunk:
                        try:
                            sp.playlist_remove_specific_occurrences_of_items(playlist_id, [item])
                            removed_count += 1
                        except Exception as e2:
                            print(f"  Falha ao remover posição(s) {item['positions']} da URI {item['uri']}: {e2}")
                    break
            except Exception as e:
                print("Erro inesperado ao remover lote de ocorrências (tentando fallback item-a-item):", e)
                for item in chunk:
                    try:
                        sp.playlist_remove_specific_occurrences_of_items(playlist_id, [item])
                        removed_count += 1
                    except Exception as e2:
                        print(f"  Falha ao remover posição(s) {item['positions']} da URI {item['uri']}: {e2}")
                break

    print(f"{removed_count} ocorrência(s) removida(s) de duplicatas.")

def remove_tracks_before_year_from_playlist(playlist_id, year_cutoff):
    """
    Remove músicas na playlist que tenham release year (álbum) anterior ao year_cutoff.
    Exibe as músicas encontradas antes de confirmar a remoção.
    Faz remoção em lotes (chunking) para evitar erro "Too many ids requested" e trata 429.
    """
    print(f"\nProcurando músicas lançadas antes de {year_cutoff}...")
    matches = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,artists(name),uri,album(release_date))),next", additional_types=['track'])

    # Coleta URIs únicos das músicas que atendem ao critério de ano (remoção por URI será aplicada)
    while results:
        for item in results['items']:
            track = item['track']
            if not track:
                continue
            release_date = track.get('album', {}).get('release_date')
            if not release_date:
                continue
            try:
                release_year = int(release_date[:4])
            except Exception:
                continue
            if release_year < year_cutoff:
                matches.append({
                    'uri': track['uri'],
                    'name': track['name'],
                    'artists': ', '.join(a['name'] for a in track.get('artists', [])),
                    'release_date': release_date,
                })
        if results['next']:
            results = sp.next(results)
        else:
            break

    if not matches:
        print(f"Nenhuma música lançada antes de {year_cutoff} encontrada nesta playlist.")
        return

    # Mostrar as músicas encontradas (agrupando por URI único)
    unique_by_uri = {}
    for m in matches:
        unique_by_uri.setdefault(m['uri'], {'name': m['name'], 'artists': m['artists'], 'release_date': m['release_date']})

    print("\nMúsicas que serão removidas (por álbum com release antes do ano informado):")
    for idx, (uri, info) in enumerate(unique_by_uri.items(), start=1):
        print(f"{idx}. {info['name']} - {info['artists']} (lançado: {info['release_date']})")

    confirm = input("Tem certeza que deseja remover TODAS as ocorrências dessas músicas desta playlist? (s/n): ").strip().lower()
    if confirm != 's':
        print("Operação cancelada.")
        return

    uris_to_remove = list(unique_by_uri.keys())
    if not uris_to_remove:
        print("Nada para remover.")
        return

    # Spotify limita quantos ids podem ser enviados; removemos em batches e tratamos 429 (rate limit).
    BATCH_SIZE = 100  # geralmente seguro; reduzir se necessário
    removed_total = 0

    for chunk in _chunked_list(uris_to_remove, BATCH_SIZE):
        while True:
            try:
                sp.playlist_remove_all_occurrences_of_items(playlist_id, chunk)
                removed_total += len(chunk)
                break  # chunk removido com sucesso
            except SpotifyException as e:
                http_status = getattr(e, 'http_status', None)
                headers = getattr(e, 'headers', {}) or {}
                if http_status == 429:
                    retry_after = int(headers.get('Retry-After', '5'))
                    print(f"Rate limit atingido. Aguardando {retry_after} segundos antes de tentar novamente...")
                    time.sleep(retry_after)
                    continue
                else:
                    # erro não-429: faz fallback item-a-item no chunk e segue em frente
                    print("Erro ao remover o lote de músicas (tentando fallback item-a-item):", e)
                    for uri in chunk:
                        try:
                            sp.playlist_remove_all_occurrences_of_items(playlist_id, [uri])
                            removed_total += 1
                        except Exception as e2:
                            print(f"  Falha ao remover {uri}: {e2}")
                    break
            except Exception as e:
                # erro genérico (p.ex. conexão), tentar fallback item-a-item
                print("Erro inesperado ao remover o lote (tentando fallback item-a-item):", e)
                for uri in chunk:
                    try:
                        sp.playlist_remove_all_occurrences_of_items(playlist_id, [uri])
                        removed_total += 1
                    except Exception as e2:
                        print(f"  Falha ao remover {uri}: {e2}")
                break

    print(f"{removed_total} faixa(s) removida(s) desta playlist.")

if __name__ == "__main__":

    user_id = sp.current_user()['id']
    playlists = get_user_playlists_only(user_id)

    if not playlists:
        print("Nenhuma playlist criada por você foi encontrada!")
        exit()

    while True:
        print("* Spotify Playlist Cleaner *")
        print("-------------------------------------------------------------------------------")
        print("""
            1 - Remover músicas de um artista específico
            2 - Remover uma música específica
            3 - Remover músicas duplicadas (mesmo nome E mesmos artistas) de uma playlist
            4 - Remover músicas lançadas antes de um certo ano
            5 - Sair
            """)
        try:
            opcao = int(input("Digite o número da opção que deseja: "))
        except ValueError:
            print("Opção inválida.")
            exit()

        match opcao:
            case 1:
                show_playlists(playlists)

                while True:
                    try:
                        escolha = int(input("\nDigite o número da playlist desejada ou 0 para voltar: "))
                        if escolha == 0: break
                        elif 1 <= escolha <= len(playlists):
                            playlist_escolhida = playlists[escolha - 1]
                            
                            artist_name = input("Nome do artista para remover: ")
                            
                            print(f"\nRemovendo músicas de '{artist_name}' da playlist '{playlist_escolhida['name']}'...\n")
                            remove_artist_from_playlist(playlist_escolhida['id'], artist_name)     
                            break
                        else:
                            print("Número inválido. Tente novamente.")         
                    except ValueError:
                        print("Por favor, digite um número válido.")

            case 2:
                show_playlists(playlists)

                while True:
                    try:
                        escolha = int(input("\nDigite o número da playlist desejada ou 0 para voltar: "))
                        if escolha == 0:
                            break
                        if 1 <= escolha <= len(playlists):
                            playlist_escolhida = playlists[escolha - 1]
                            break
                        else:
                            print("Número inválido. Tente novamente.")
                    except ValueError:
                        print("Por favor, digite um número válido.")

                # Se o usuário digitou 0 acima, volta ao menu principal
                try:
                    playlist_escolhida
                except NameError:
                    # usuário escolheu voltar
                    continue

                print("Deseja listar as musicas dessa playlist? (s/n)")
                listar = str(input()).strip().lower()
                if listar == 's':
                    listar_musicas_playlist(playlist_escolhida['id'])
                    print("-------------------------------")

                track_name = input("Nome da música para remover: ")

                print(f"\nRemovendo músicas '{track_name}' da playlist '{playlist_escolhida['name']}'...\n")
                remove_music_from_playlist(playlist_escolhida['id'], track_name)

            case 3:
                show_playlists(playlists)

                while True:
                    try:
                        escolha = int(input("\nDigite o número da playlist desejada ou 0 para voltar: "))
                        if escolha == 0:
                            break
                        if 1 <= escolha <= len(playlists):
                            playlist_escolhida = playlists[escolha - 1]
                            break
                        else:
                            print("Número inválido. Tente novamente.")
                    except ValueError:
                        print("Por favor, digite um número válido.")

                # Se o usuário digitou 0 acima, volta ao menu principal
                try:
                    playlist_escolhida
                except NameError:
                    continue

                remove_duplicates_from_playlist(playlist_escolhida['id'])

            case 4:
                show_playlists(playlists)

                while True:
                    try:
                        escolha = int(input("\nDigite o número da playlist desejada ou 0 para voltar: "))
                        if escolha == 0:
                            break
                        if 1 <= escolha <= len(playlists):
                            playlist_escolhida = playlists[escolha - 1]
                            break
                        else:
                            print("Número inválido. Tente novamente.")
                    except ValueError:
                        print("Por favor, digite um número válido.")

                # Se o usuário digitou 0 acima, volta ao menu principal
                try:
                    playlist_escolhida
                except NameError:
                    continue

                while True:
                    ano_str = input("Digite o ano (ex: 2010) - remover músicas lançadas ANTES deste ano: ").strip()
                    try:
                        ano = int(ano_str)
                        break
                    except ValueError:
                        print("Por favor, digite um ano válido (ex: 2010).")

                remove_tracks_before_year_from_playlist(playlist_escolhida['id'], ano)

            case 5:
                exit()

            case _:
                print("Opção inválida.")