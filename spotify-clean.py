import io
import os
import threading
import time
from contextlib import redirect_stdout
import tkinter as tk

import customtkinter as ctk
import spotipy
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

sp = None


def load_spotify_client():
    load_dotenv()

    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = os.getenv('REDIRECT_URI')

    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError(
            'As variáveis CLIENT_ID, CLIENT_SECRET ou REDIRECT_URI não estão definidas.\n\n'
            'Crie um arquivo .env na raiz do projeto com as chaves ou exporte as variáveis de ambiente.\n\n'
            'Exemplo (.env):\n'
            "CLIENT_ID='seu_id'\n"
            "CLIENT_SECRET='seu_secret'\n"
            "REDIRECT_URI='seu_redirect_uri'"
        )

    scope = 'playlist-modify-public playlist-modify-private playlist-read-private'
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope
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


def collect_tracks_by_artist(playlist_id, artist_name):
    tracks = []
    seen_uris = set()
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,uri,artists(name))),next", additional_types=['track'])

    while results:
        for item in results['items']:
            track = item['track']
            if not track:
                continue

            if any(artist['name'].lower() == artist_name.lower() for artist in track.get('artists', [])):
                uri = track['uri']
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)
                tracks.append({
                    'uri': uri,
                    'name': track['name'],
                    'artists': ', '.join(artist['name'] for artist in track.get('artists', [])),
                    'added_at': item.get('added_at'),
                })

        if results['next']:
            results = sp.next(results)
        else:
            break

    return tracks

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


def collect_tracks_by_name(playlist_id, track_name):
    tracks = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,uri,artists(name))),next", additional_types=['track'])

    while results:
        for item in results['items']:
            track = item['track']
            if not track or track['name'].lower() != track_name.lower():
                continue

            tracks.append({
                'uri': track['uri'],
                'name': track['name'],
                'artists': ', '.join(artist['name'] for artist in track.get('artists', [])),
                'added_at': item.get('added_at'),
            })

        if results['next']:
            results = sp.next(results)
        else:
            break

    return tracks

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


def collect_duplicate_groups(playlist_id):
    items = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,artists(name),uri)),next", additional_types=['track'])
    position = 0

    while results:
        for item in results['items']:
            track = item['track']
            if track:
                artist_list = [artist['name'].strip() for artist in track.get('artists', [])]
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

    groups = {}
    for item in items:
        key = f"{item['name'].strip().lower()}||{item['artist_key']}"
        groups.setdefault(key, []).append(item)

    duplicates = []
    for occurrences in groups.values():
        if len(occurrences) <= 1:
            continue

        ordered = sorted(
            occurrences,
            key=lambda occ: ((occ.get('added_at') or ''), occ['position'])
        )
        duplicates.append({
            'name': ordered[0]['name'],
            'artists': ordered[0]['artists'],
            'keep': ordered[-1],
            'remove': ordered[:-1],
        })

    return duplicates


def remove_selected_duplicate_occurrences(playlist_id, occurrences_to_remove):
    if not occurrences_to_remove:
        print("Nenhuma remoção selecionada.")
        return

    batch_size = 50
    removed_count = 0
    for chunk in _chunked_list(occurrences_to_remove, batch_size):
        while True:
            try:
                sp.playlist_remove_specific_occurrences_of_items(playlist_id, chunk)
                removed_count += len(chunk)
                break
            except SpotifyException as exc:
                http_status = getattr(exc, 'http_status', None)
                headers = getattr(exc, 'headers', {}) or {}
                if http_status == 429:
                    retry_after = int(headers.get('Retry-After', '5'))
                    print(f"Rate limit atingido. Aguardando {retry_after} segundos antes de tentar novamente...")
                    time.sleep(retry_after)
                    continue

                print("Erro ao remover lote de ocorrências (tentando fallback item-a-item):", exc)
                for item in chunk:
                    try:
                        sp.playlist_remove_specific_occurrences_of_items(playlist_id, [item])
                        removed_count += 1
                    except Exception as item_exc:
                        print(f"  Falha ao remover posição(s) {item['positions']} da URI {item['uri']}: {item_exc}")
                break
            except Exception as exc:
                print("Erro inesperado ao remover lote de ocorrências (tentando fallback item-a-item):", exc)
                for item in chunk:
                    try:
                        sp.playlist_remove_specific_occurrences_of_items(playlist_id, [item])
                        removed_count += 1
                    except Exception as item_exc:
                        print(f"  Falha ao remover posição(s) {item['positions']} da URI {item['uri']}: {item_exc}")
                break

    print(f"{removed_count} ocorrência(s) removida(s) de duplicatas.")


def collect_tracks_before_year(playlist_id, year_cutoff):
    matches = []
    results = sp.playlist_items(playlist_id, fields="items(added_at,track(name,artists(name),uri,album(release_date))),next", additional_types=['track'])

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
                    'artists': ', '.join(artist['name'] for artist in track.get('artists', [])),
                    'release_date': release_date,
                })

        if results['next']:
            results = sp.next(results)
        else:
            break

    unique_by_uri = {}
    for match in matches:
        unique_by_uri.setdefault(match['uri'], {
            'name': match['name'],
            'artists': match['artists'],
            'release_date': match['release_date']
        })

    return unique_by_uri


def build_removal_summary(items):
    lines = []
    for index, item in enumerate(items, start=1):
        parts = [f"{index}. {item['name']}"]
        if item.get('artists'):
            parts.append(f"- {item['artists']}")
        if item.get('release_date'):
            parts.append(f"(lançada em: {item['release_date']})")
        elif item.get('added_at'):
            parts.append(f"(adicionada em: {item['added_at']})")
        lines.append(' '.join(parts))
    return '\n'.join(lines)


def review_track_removals(app, title, intro_text, candidates):
    selected = []
    skipped = []

    if not candidates:
        app.show_text_window(title, 'Nenhuma música encontrada para essa remoção.')
        return [], []

    for item in candidates:
        decision = {'value': None}

        dialog = ctk.CTkToplevel(app)
        dialog.title(title)
        dialog.geometry('700x320')
        dialog.minsize(640, 280)
        dialog.transient(app)
        dialog.grab_set()

        header = ctk.CTkLabel(dialog, text=intro_text, wraplength=640, justify='left')
        header.pack(padx=18, pady=(18, 10), anchor='w')

        details = ctk.CTkTextbox(dialog, height=110, wrap='word')
        details.pack(fill='both', expand=True, padx=18, pady=(0, 12))
        details.insert('1.0', f"Música: {item['name']}\nArtistas: {item.get('artists', '-')}")
        if item.get('release_date'):
            details.insert('end', f"\nLançada em: {item['release_date']}")
        elif item.get('added_at'):
            details.insert('end', f"\nAdicionada em: {item['added_at']}")
        details.configure(state='disabled')

        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill='x', padx=18, pady=(0, 18))

        def choose_remove():
            decision['value'] = True
            dialog.destroy()

        def choose_keep():
            decision['value'] = False
            dialog.destroy()

        remove_button = ctk.CTkButton(button_frame, text='Remover', command=choose_remove)
        remove_button.pack(side='left', padx=(0, 10))

        keep_button = ctk.CTkButton(button_frame, text='Manter', command=choose_keep)
        keep_button.pack(side='right')

        app.wait_window(dialog)

        if decision['value'] is True:
            selected.append(item)
        else:
            skipped.append(item)

    return selected, skipped


def confirm_removal_summary(app, title, selected_items):
    if not selected_items:
        app.show_text_window(title, 'Nenhuma remoção foi selecionada.')
        return False

    summary = build_removal_summary(selected_items)
    return app.ask_confirmation(
        title,
        f'As seguintes alterações serão feitas:\n\n{summary}\n\nDeseja confirmar?',
        yes_text='Confirmar remoção',
        no_text='Cancelar'
    )


def remove_uris_from_playlist(playlist_id, uris, batch_size=100):
    removed_total = 0
    for chunk in _chunked_list(uris, batch_size):
        while True:
            try:
                sp.playlist_remove_all_occurrences_of_items(playlist_id, chunk)
                removed_total += len(chunk)
                break
            except SpotifyException as exc:
                http_status = getattr(exc, 'http_status', None)
                headers = getattr(exc, 'headers', {}) or {}
                if http_status == 429:
                    retry_after = int(headers.get('Retry-After', '5'))
                    print(f"Rate limit atingido. Aguardando {retry_after} segundos antes de tentar novamente...")
                    time.sleep(retry_after)
                    continue

                print("Erro ao remover o lote de músicas (tentando fallback item-a-item):", exc)
                for uri in chunk:
                    try:
                        sp.playlist_remove_all_occurrences_of_items(playlist_id, [uri])
                        removed_total += 1
                    except Exception as item_exc:
                        print(f"  Falha ao remover {uri}: {item_exc}")
                break
            except Exception as exc:
                print("Erro inesperado ao remover o lote (tentando fallback item-a-item):", exc)
                for uri in chunk:
                    try:
                        sp.playlist_remove_all_occurrences_of_items(playlist_id, [uri])
                        removed_total += 1
                    except Exception as item_exc:
                        print(f"  Falha ao remover {uri}: {item_exc}")
                break

    print(f"{removed_total} faixa(s) removida(s) desta playlist.")


class SpotifyCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Spotify Playlist Cleaner')
        self.geometry('720x520')
        self.minsize(680, 500)

        self.playlists = []
        self.playlist_map = {}
        self.selected_playlist_var = tk.StringVar(value='Carregando playlists...')
        self.status_var = tk.StringVar(value='Inicializando...')

        self.title_label = ctk.CTkLabel(self, text='Spotify Playlist Cleaner', font=ctk.CTkFont(size=24, weight='bold'))
        self.title_label.pack(pady=(18, 8))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text='Gerencie apenas playlists criadas por você, com uma interface simples e segura.',
            wraplength=620,
        )
        self.subtitle_label.pack(pady=(0, 10))

        selector_frame = ctk.CTkFrame(self)
        selector_frame.pack(fill='x', padx=18, pady=(6, 10))

        selector_label = ctk.CTkLabel(selector_frame, text='Playlist do usuário:')
        selector_label.pack(anchor='w', padx=14, pady=(12, 4))

        self.playlist_menu = ctk.CTkOptionMenu(selector_frame, variable=self.selected_playlist_var, values=['Carregando...'])
        self.playlist_menu.pack(fill='x', padx=12, pady=(0, 12))

        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var, wraplength=660)
        self.status_label.pack(pady=(0, 10))

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(fill='both', expand=True, padx=18, pady=(0, 18))

        self.buttons = []
        actions = [
            ('Atualizar playlists', self.refresh_playlists),
            ('Listar músicas da playlist', self.action_list_tracks),
            ('Remover por artista', self.action_remove_artist),
            ('Remover por nome', self.action_remove_music),
            ('Remover duplicadas', self.action_remove_duplicates),
            ('Remover lançadas antes de um ano', self.action_remove_before_year),
            ('Sair', self.destroy),
        ]

        for index, (label, command) in enumerate(actions):
            button = ctk.CTkButton(self.button_frame, text=label, command=command)
            button.grid(row=index, column=0, sticky='ew', padx=16, pady=6)
            self.buttons.append(button)

        self.button_frame.grid_columnconfigure(0, weight=1)

        self.after(50, self.bootstrap)

    def bootstrap(self):
        try:
            global sp
            sp = load_spotify_client()
        except Exception as exc:
            self.status_var.set('Falha ao iniciar a aplicação.')
            self.show_text_window('Erro de configuração', str(exc))
            self.set_buttons_state('disabled')
            return

        self.refresh_playlists()

    def set_buttons_state(self, state):
        for button in self.buttons:
            button.configure(state=state)

    def show_text_window(self, title, text):
        window = ctk.CTkToplevel(self)
        window.title(title)
        window.geometry('760x520')
        window.minsize(600, 420)
        window.transient(self)

        textbox = ctk.CTkTextbox(window, wrap='word')
        textbox.pack(fill='both', expand=True, padx=12, pady=12)
        textbox.insert('1.0', text)
        textbox.configure(state='disabled')

        close_button = ctk.CTkButton(window, text='Fechar', command=window.destroy)
        close_button.pack(pady=(0, 12))

    def ask_text(self, title, text):
        dialog = ctk.CTkInputDialog(title=title, text=text)
        value = dialog.get_input()
        if value is None:
            return None
        value = value.strip()
        return value if value else None

    def ask_confirmation(self, title, text, yes_text='Sim', no_text='Cancelar'):
        result = {'value': False}

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry('560x240')
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        label = ctk.CTkLabel(dialog, text=text, wraplength=500, justify='left')
        label.pack(padx=20, pady=(22, 14), anchor='w')

        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill='x', padx=20, pady=(0, 18))

        def accept():
            result['value'] = True
            dialog.destroy()

        def reject():
            dialog.destroy()

        yes_button = ctk.CTkButton(button_frame, text=yes_text, command=accept)
        yes_button.pack(side='left', padx=(0, 10))

        no_button = ctk.CTkButton(button_frame, text=no_text, command=reject)
        no_button.pack(side='right')

        self.wait_window(dialog)
        return result['value']

    def run_background(self, task, title='Resultado', on_success=None, busy_text='Processando...'):
        self.status_var.set(busy_text)

        def worker():
            buffer = io.StringIO()
            result = None
            error = None
            try:
                with redirect_stdout(buffer):
                    result = task()
            except Exception as exc:
                error = exc

            output = buffer.getvalue().strip()
            if error is not None:
                if output:
                    output += '\n\n'
                output += f'Erro: {error}'

            def finish():
                self.status_var.set('Pronto')
                if error is not None:
                    self.show_text_window('Erro', output or str(error))
                    return
                if on_success is not None:
                    on_success(result, output)
                    return
                self.show_text_window(title, output or 'Operação concluída.')

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def current_playlist(self):
        return self.playlist_map.get(self.selected_playlist_var.get())

    def refresh_playlists(self):
        if sp is None:
            return

        def on_success(playlists, _output):
            self.playlists = playlists or []
            self.playlist_map = {}

            if not self.playlists:
                self.selected_playlist_var.set('Nenhuma playlist encontrada')
                self.playlist_menu.configure(values=['Nenhuma playlist encontrada'])
                self.playlist_menu.set('Nenhuma playlist encontrada')
                self.status_var.set('Nenhuma playlist criada por você foi encontrada.')
                return

            values = []
            for index, playlist in enumerate(self.playlists, start=1):
                label = f'{index}. {playlist["name"]}'
                values.append(label)
                self.playlist_map[label] = playlist

            self.playlist_menu.configure(values=values)
            self.selected_playlist_var.set(values[0])
            self.playlist_menu.set(values[0])
            self.status_var.set(f'{len(self.playlists)} playlist(s) carregada(s).')

        self.run_background(
            lambda: get_user_playlists_only(sp.current_user()['id']),
            title='Playlists',
            on_success=on_success,
            busy_text='Carregando playlists criadas por você...'
        )

    def require_playlist(self):
        playlist = self.current_playlist()
        if not playlist:
            self.show_text_window('Atenção', 'Selecione uma playlist criada por você para continuar.')
            return None
        return playlist

    def action_list_tracks(self):
        playlist = self.require_playlist()
        if not playlist:
            return

        self.run_background(
            lambda: listar_musicas_playlist(playlist['id']),
            title=f"Músicas - {playlist['name']}",
            busy_text='Carregando músicas da playlist...'
        )

    def action_remove_artist(self):
        playlist = self.require_playlist()
        if not playlist:
            return

        artist_name = self.ask_text('Remover por artista', 'Digite o nome do artista que deseja remover:')
        if not artist_name:
            return

        def task():
            return collect_tracks_by_artist(playlist['id'], artist_name)

        def on_success(candidates, _output):
            selected, _skipped = review_track_removals(
                self,
                'Remover por artista',
                f'Você escolheu remover faixas do artista "{artist_name}". Revise faixa por faixa:',
                candidates
            )

            if not confirm_removal_summary(self, 'Confirmar remoção por artista', selected):
                return

            self.run_background(
                lambda: remove_uris_from_playlist(playlist['id'], [item['uri'] for item in selected]),
                title='Remoção por artista',
                busy_text='Removendo músicas do artista...'
            )

        self.run_background(task, title='Remover por artista', on_success=on_success, busy_text='Buscando músicas do artista...')

    def action_remove_music(self):
        playlist = self.require_playlist()
        if not playlist:
            return

        track_name = self.ask_text('Remover por nome', 'Digite o nome da música que deseja remover:')
        if not track_name:
            return

        def task():
            return collect_tracks_by_name(playlist['id'], track_name)

        def on_success(candidates, _output):
            selected, _skipped = review_track_removals(
                self,
                'Remover por nome',
                f'Você escolheu remover a música "{track_name}". Revise ocorrência por ocorrência:',
                candidates
            )

            if not confirm_removal_summary(self, 'Confirmar remoção por nome', selected):
                return

            self.run_background(
                lambda: remove_uris_from_playlist(playlist['id'], [item['uri'] for item in selected]),
                title='Remoção por nome',
                busy_text='Removendo músicas pelo nome...'
            )

        self.run_background(task, title='Remover por nome', on_success=on_success, busy_text='Buscando músicas pelo nome...')

    def action_remove_duplicates(self):
        playlist = self.require_playlist()
        if not playlist:
            return

        def on_success(duplicate_groups, _output):
            if not duplicate_groups:
                self.show_text_window('Duplicatas', 'Nenhuma música duplicada (mesmo nome e mesmos artistas) foi encontrada nesta playlist.')
                return

            candidates = []
            for group in duplicate_groups:
                candidates.extend(group['remove'])

            selected, _skipped = review_track_removals(
                self,
                'Remover duplicatas',
                'Foi encontrada uma duplicata. A ocorrência mais recente será mantida automaticamente. Revise faixa por faixa:',
                candidates
            )

            if not confirm_removal_summary(self, 'Confirmar remoção de duplicatas', selected):
                return

            self.run_background(
                lambda: remove_selected_duplicate_occurrences(playlist['id'], [
                    {'uri': item['uri'], 'positions': [item['position']]}
                    for item in selected
                ]),
                title='Duplicatas removidas',
                busy_text='Removendo duplicatas antigas...'
            )

        self.run_background(
            lambda: collect_duplicate_groups(playlist['id']),
            title='Duplicatas',
            on_success=on_success,
            busy_text='Escaneando duplicatas da playlist...'
        )

    def action_remove_before_year(self):
        playlist = self.require_playlist()
        if not playlist:
            return

        year_text = self.ask_text('Remover por ano', 'Digite o ano. Serão removidas músicas lançadas ANTES deste ano:')
        if not year_text or not year_text.isdigit():
            return

        year_cutoff = int(year_text)

        def on_success(unique_by_uri, _output):
            if not unique_by_uri:
                self.show_text_window('Remover por ano', f'Nenhuma música lançada antes de {year_cutoff} foi encontrada nesta playlist.')
                return

            candidates = []
            for uri, info in unique_by_uri.items():
                candidates.append({
                    'uri': uri,
                    'name': info['name'],
                    'artists': info['artists'],
                    'release_date': info['release_date'],
                })

            selected, _skipped = review_track_removals(
                self,
                'Remover por ano',
                f'Estas músicas foram lançadas antes de {year_cutoff}. Revise faixa por faixa:',
                candidates
            )

            if not confirm_removal_summary(self, 'Confirmar remoção por ano', selected):
                return

            self.run_background(
                lambda: remove_uris_from_playlist(playlist['id'], [item['uri'] for item in selected]),
                title='Remoção por ano concluída',
                busy_text='Removendo músicas anteriores ao ano informado...'
            )

        self.run_background(
            lambda: collect_tracks_before_year(playlist['id'], year_cutoff),
            title='Remover por ano',
            on_success=on_success,
            busy_text='Buscando músicas anteriores ao ano informado...'
        )

if __name__ == "__main__":
    ctk.set_appearance_mode('System')
    ctk.set_default_color_theme('blue')

    app = SpotifyCleanerApp()
    app.mainloop()