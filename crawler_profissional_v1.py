import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import urllib.robotparser
import re
import time
import os
import json
import threading
from queue import Queue, Empty
from collections import deque
import logging

# ==============================================================================
# CONFIGURAÇÃO DO LOG
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,  # Mude para logging.DEBUG para ver informações detalhadas
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log", mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ==============================================================================
# CRAWLER PROFISSIONAL - VERSÃO UNIFICADA
#
# FUNCIONALIDADES PRINCIPAIS:
#
# 1.  **Busca em Múltiplos Sites**: Lê uma lista de sites do arquivo `base_busca.txt`
#     para realizar a varredura em todos eles sequencialmente.
#
# 2.  **Histórico Persistente**: Mantém um registro completo de todos os links magnéticos
#     já encontrados no arquivo `links-magnetic-download.txt`.
#
# 3.  **Detecção de Novidades**: Compara os links encontrados com o histórico para
#     identificar e salvar apenas os que são genuinamente novos.
#
# 4.  **Varredura Profunda e Multi-thread**: Utiliza múltiplas threads para navegar
#     pelas páginas internas de cada site, garantindo uma busca mais rápida e completa.
#
# 5.  **Categorização Automática**: Organiza os novos links em arquivos separados
#     (ex: `links-filmes.txt`, `links-series.txt`) com base em palavras-chave.
# ==============================================================================

class CrawlerProfissional:
    def __init__(self, config):
        self.config = config
        
        # Arquivos de controle
        self.arquivo_base = "base_busca.txt"
        self.arquivo_novos = "links-novos.txt"
        self.arquivo_baixados = "links-baixados.txt"
        self.arquivo_todos = "links-magnetic-download.txt"
        
        # Controle de links
        self.links_ja_capturados = set()
        self.links_novos_encontrados = set()
        self.links_baixados = set()
        
        # Carregar dados
        self.carregar_links_existentes()
        
        # Sessão de requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    # --- MÉTODOS DE GERENCIAMENTO DE HISTÓRICO (do deepseek.py) ---

    def carregar_links_existentes(self):
        """Carrega todos os links de execuções anteriores para evitar duplicatas."""
        arquivos_para_ler = [self.arquivo_baixados, self.arquivo_novos, self.arquivo_todos]
        for arquivo in arquivos_para_ler:
            if os.path.exists(arquivo):
                with open(arquivo, 'r', encoding='utf-8') as f:
                    for linha in f:
                        linha = linha.strip()
                        if linha.startswith('magnet:'):
                            self.links_ja_capturados.add(linha)
        
        logging.info(f"📚 Total de {len(self.links_ja_capturados)} links únicos na base de dados histórica.")

    def extrair_hash_magnet(self, magnet_link):
        """Extrai o hash BTIH de um link magnético para comparação."""
        hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', magnet_link, re.IGNORECASE)
        return hash_match.group(1).upper() if hash_match else None

    def eh_link_novo(self, magnet_link):
        """Verifica se um link é novo comparando seu hash com os já salvos."""
        novo_hash = self.extrair_hash_magnet(magnet_link)
        if not novo_hash:
            return False  # Link inválido

        for link_existente in self.links_ja_capturados:
            hash_existente = self.extrair_hash_magnet(link_existente)
            if hash_existente and hash_existente == novo_hash:
                return False # Hash já existe
        
        return True

    def salvar_link_novo(self, magnet_link):
        """Salva um novo link magnético se ele não existir no histórico."""
        if not self.eh_link_novo(magnet_link):
            return False
        
        # Adicionar aos sets de controle da execução atual
        self.links_novos_encontrados.add(magnet_link)
        self.links_ja_capturados.add(magnet_link)
        
        # Salvar no arquivo de novos links desta execução
        with open(self.arquivo_novos, 'a', encoding='utf-8') as f:
            f.write(magnet_link + '\n')
        
        # Atualizar o arquivo consolidado com todos os links
        with open(self.arquivo_todos, 'a', encoding='utf-8') as f:
            f.write(magnet_link + '\n')
            
        return True

    # --- MOTOR DE VARREDURA PROFUNDA (adaptado de deepseek_digite_site.py) ---

    def processar_site(self, site_url):
        """Orquestra a varredura completa de um único site."""
        logging.info(f"{'='*20} PROCESSANDO SITE: {site_url} {'='*20}")
        
        scanner = SiteScanner(site_url, self)
        novos_links_site = scanner.iniciar_varredura()
        
        logging.info(f"📊 Site {site_url} finalizado: {novos_links_site} novos links encontrados.")
        return novos_links_site

    # --- GERENCIAMENTO E EXECUÇÃO (do deepseek.py) ---

    def carregar_sites_para_busca(self):
        """Carrega a lista de sites do arquivo base_busca.txt."""
        if not os.path.exists(self.arquivo_base):
            logging.error(f"❌ Arquivo {self.arquivo_base} não encontrado!")
            return []
        
        sites = []
        with open(self.arquivo_base, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith('#') and linha.startswith('http'):
                    sites.append(linha)
        
        logging.info(f"🌐 {len(sites)} sites carregados para a busca.")
        return sites

    def executar_busca(self):
        """Executa a busca em todos os sites da lista."""
        logging.info("🚀 INICIANDO BUSCA PROFISSIONAL")
        
        # Limpar arquivo de links novos da execução anterior
        if os.path.exists(self.arquivo_novos):
            os.remove(self.arquivo_novos)
            
        sites = self.carregar_sites_para_busca()
        if not sites:
            return
            
        total_novos_links = 0
        for site in sites:
            novos_links = self.processar_site(site)
            total_novos_links += novos_links
            logging.info(f"⏰ Aguardando {self.config['delay_entre_sites']}s antes de ir para o próximo site...")
            time.sleep(self.config['delay_entre_sites'])
            
        logging.info("\n" + "=" * 60)
        logging.info("🎉 BUSCA FINALIZADA!")
        logging.info(f"🎯 Total de novos links encontrados nesta execução: {total_novos_links}")
        logging.info(f"🔗 Total de links na base histórica: {len(self.links_ja_capturados)}")
        
        if total_novos_links > 0:
            logging.info("\n📁 ORGANIZANDO NOVOS LINKS POR CATEGORIAS:")
            self.gerar_relatorio_categorias()
            
        logging.info(f"\n💾 Arquivos atualizados:")
        logging.info(f"   • {self.arquivo_novos} - Apenas os links novos desta busca.")
        logging.info(f"   • {self.arquivo_todos} - Todos os links já encontrados.")
        logging.info(f"   • links-*.txt - Links novos organizados por categoria.")

    # --- CATEGORIZAÇÃO E RELATÓRIOS (do deepseek.py) ---

    def extrair_nome_magnet(self, magnet_link):
        """Extrai o nome (dn) de um link magnético."""
        try:
            nome_match = re.search(r'dn=([^&]+)', magnet_link)
            if nome_match:
                return unquote(nome_match.group(1))
        except:
            pass
        return "Sem nome"

    def categorizar_link(self, magnet_link):
        """Categoriza um link baseado em palavras-chave no nome."""
        nome = self.extrair_nome_magnet(magnet_link).lower()
        
        if any(p in nome for p in ['filme', 'movie', '1080p', '720p', 'bluray', 'dvdrip', 'x264', 'x265']):
            return "Filmes"
        if any(p in nome for p in ['serie', 'season', 's01', 's02', 'temporada', 'hdtv']):
            return "Series"
        if any(p in nome for p in ['jogo', 'game', 'repack', 'iso', 'codex', 'cpy']):
            return "Jogos"
        if any(p in nome for p in ['musica', 'album', 'mp3', 'flac']):
            return "Musicas"
        if any(p in nome for p in ['software', 'app', 'windows', 'ativador']):
            return "Software"
        return "Outros"

    def gerar_relatorio_categorias(self):
        """Gera arquivos .txt para cada categoria de link novo encontrado."""
        categorias = { "Filmes": [], "Series": [], "Jogos": [], "Musicas": [], "Software": [], "Outros": [] }
        
        for link in self.links_novos_encontrados:
            categoria = self.categorizar_link(link)
            categorias[categoria].append(link)
            
        for categoria, links in categorias.items():
            if links:
                arquivo_categoria = f"links-{categoria.lower()}.txt"
                with open(arquivo_categoria, 'w', encoding='utf-8') as f:
                    f.write(f"# {categoria} - {len(links)} links novos\n")
                    for link in links:
                        f.write(link + '\n')
                logging.info(f"   • {len(links)} links salvos em {arquivo_categoria}")


class SiteScanner:
    """
    Classe responsável por escanear um único site de forma profunda.
    Adaptada do 'CrawlerProfissional' de deepseek_digite_site.py.
    """
    def __init__(self, site_url, main_crawler):
        self.main_crawler = main_crawler
        self.config = main_crawler.config
        self.site_url = site_url
        self.dominio_parseado = urlparse(site_url)
        
        # Controle de URLs do site atual
        self.urls_para_visitar = Queue()
        self.urls_para_visitar.put(site_url)
        self.urls_visitadas = set()
        self.novos_links_encontrados_site = 0
        
        # Lock para acesso thread-safe
        self.lock = threading.Lock()
        self.running = True
        
        # Robots.txt (do deepseek_1.py)
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.robot_parser.set_url(urljoin(site_url, '/robots.txt'))
        try:
            self.robot_parser.read()
            logging.info("🤖 Robots.txt carregado com sucesso.")
        except Exception as e:
            logging.warning(f"⚠️ Não foi possível carregar robots.txt: {e}")

    def pode_rastrear(self, url):
        """Verifica se a URL pode ser rastreada conforme o robots.txt."""
        try:
            return self.robot_parser.can_fetch(self.main_crawler.session.headers['User-Agent'], url)
        except:
            return True # Falha em favor do rastreamento

    def eh_url_valida(self, url):
        """Verifica se a URL pertence ao mesmo domínio e é um tipo de conteúdo válido."""
        try:
            parsed = urlparse(url)
            if parsed.netloc != self.dominio_parseado.netloc:
                logging.debug(f"URL ignorada (domínio diferente): {url}")
                return False
            if any(url.lower().endswith(ext) for ext in ['.zip', '.rar', '.exe', '.pdf', '.jpg', '.png', '.css', '.js']):
                logging.debug(f"URL ignorada (extensão de arquivo): {url}")
                return False
            return True
        except:
            return False

    def worker(self):
        """Thread de trabalho que processa URLs da fila."""
        while self.running:
            try:
                url = self.urls_para_visitar.get(timeout=5)
                
                with self.lock:
                    if url in self.urls_visitadas:
                        self.urls_para_visitar.task_done()
                        continue
                    self.urls_visitadas.add(url)

                if not self.pode_rastrear(url):
                    logging.info(f"🚫 Bloqueado por robots.txt: {url}")
                    self.urls_para_visitar.task_done()
                    continue

                logging.debug(f"Iniciando processamento de: {url}")
                try:
                    time.sleep(self.config['delay_entre_requests'])
                    response = self.main_crawler.session.get(url, timeout=10)
                    response.raise_for_status()
                    
                    if 'text/html' in response.headers.get('content-type', ''):
                        # Extrai links magnéticos
                        magnets = re.findall(r'magnet:\?[^\s"\']+', response.text, re.IGNORECASE)
                        if magnets:
                            logging.debug(f"Encontrados {len(set(magnets))} magnet(s) em {url}")
                        for magnet in set(magnets):
                            if self.main_crawler.salvar_link_novo(magnet):
                                with self.lock:
                                    self.novos_links_encontrados_site += 1
                                nome = self.main_crawler.extrair_nome_magnet(magnet)
                                logging.info(f"🎯 NOVO LINK: {nome[:60]}...")

                        # Extrai links para outras páginas
                        soup = BeautifulSoup(response.text, 'html.parser')
                        links_encontrados_pagina = 0
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            url_absoluta = urljoin(url, href)
                            if self.eh_url_valida(url_absoluta):
                                with self.lock:
                                    if url_absoluta not in self.urls_visitadas and url_absoluta not in list(self.urls_para_visitar.queue):
                                        self.urls_para_visitar.put(url_absoluta)
                                        links_encontrados_pagina += 1
                        if links_encontrados_pagina > 0:
                            logging.debug(f"{links_encontrados_pagina} novas URLs adicionadas à fila a partir de {url}")

                except requests.exceptions.RequestException as e:
                    logging.error(f"❌ Erro de requisição ao processar {url}: {e}")
                except Exception as e:
                    logging.error(f"❌ Erro inesperado ao processar {url}: {e}", exc_info=True)

                self.urls_para_visitar.task_done()
            except Empty:
                if self.urls_para_visitar.empty():
                    logging.debug("Fila vazia, worker aguardando...")
                    time.sleep(1)
            except Exception as e:
                logging.critical(f"CRITICAL ERRO no worker: {e}", exc_info=True)

    def iniciar_varredura(self):
        """Inicia a varredura com múltiplas threads."""
        self.running = True
        threads = []
        for i in range(self.config['max_threads']):
            t = threading.Thread(target=self.worker, name=f"Worker-{i+1}")
            t.daemon = True
            t.start()
            threads.append(t)
            
        # Monitorar o progresso
        try:
            while any(t.is_alive() for t in threads):
                status = f"\rℹ️  Páginas na fila: {self.urls_para_visitar.qsize()}, Páginas visitadas: {len(self.urls_visitadas)}, Novos Links: {self.novos_links_encontrados_site}"
                print(status, end="")
                time.sleep(2)
        except KeyboardInterrupt:
            logging.warning("\n🛑 Interrupção manual detectada. Finalizando workers...")
            self.running = False

        self.running = False
        for t in threads:
            t.join(timeout=10)
        
        print() # Nova linha após a barra de status
        return self.novos_links_encontrados_site


def criar_arquivo_base_exemplo():
    """Cria o arquivo base_busca.txt se ele não existir."""
    if not os.path.exists("base_busca.txt"):
        with open("base_busca.txt", "w", encoding="utf-8") as f:
            f.write("# ======================================================\n")
            f.write("# LISTA DE SITES PARA BUSCA PROFISSIONAL\n")
            f.write("# Coloque um site por linha.\n")
            f.write("# Linhas com # no início são ignoradas.\n")
            f.write("# ======================================================\n")
            f.write("https://www.starckfilmes.fans\n")
        logging.info("\n📄 Arquivo 'base_busca.txt' não encontrado. Criei um com exemplo.")
        logging.info("✏️  Edite o arquivo com os sites que deseja escanear e execute novamente.")
        return True
    return False

if __name__ == "__main__":
    if criar_arquivo_base_exemplo():
        input("\nPressione Enter para sair...")
    else:
        # --- CONFIGURAÇÕES ---
        config = {
            "max_threads": 5,  # Para "simular um humano", use 1. Para mais velocidade, aumente (5-10).
            "delay_entre_requests": 1,  # Delay em segundos entre cada request (respeite os servidores!)
            "delay_entre_sites": 5, # Delay em segundos para mudar de um site para outro.
        }
        
        logging.info("=" * 60)
        logging.info("🕵️ CRAWLER PROFISSIONAL")
        logging.info(f"⚙️  Configuração: {config['max_threads']} threads, {config['delay_entre_requests']}s de delay por request.")
        logging.info("=" * 60)
        
        crawler = CrawlerProfissional(config)
        crawler.executar_busca()
        
        input("\nPressione Enter para finalizar...")