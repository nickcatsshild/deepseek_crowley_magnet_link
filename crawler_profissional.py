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
    """
    Classe principal que orquestra todo o processo de crawling.
    Gerencia a lista de sites, o histórico de links e a geração de relatórios.
    """
    def __init__(self, config):
        self.config = config
        self.arquivo_base = "base_busca.txt"
        self.arquivo_novos = "links-novos.txt"
        self.arquivo_baixados = "links-baixados.txt"
        self.arquivo_todos = "links-magnetic-download.txt"
        
        self.links_ja_capturados = set()
        self.carregar_links_existentes()
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    # --- MÉTODOS DE GERENCIAMENTO DE HISTÓRICO E FILTRAGEM ---

    def carregar_links_existentes(self):
        """Carrega todos os links de execuções anteriores para evitar duplicatas."""
        for arquivo in [self.arquivo_baixados, self.arquivo_todos]:
            if os.path.exists(arquivo):
                with open(arquivo, 'r', encoding='utf-8') as f:
                    for linha in f:
                        if linha.strip().startswith('magnet:'):
                            self.links_ja_capturados.add(linha.strip())
        logging.info(f"📚 Total de {len(self.links_ja_capturados)} links únicos na base de dados histórica.")

    def extrair_hash_magnet(self, magnet_link):
        """Extrai o hash BTIH de um link magnético para comparação."""
        hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', magnet_link, re.IGNORECASE)
        return hash_match.group(1).upper() if hash_match else None

    def eh_link_novo(self, magnet_link):
        """Verifica se um link é novo comparando seu hash com os já salvos."""
        novo_hash = self.extrair_hash_magnet(magnet_link)
        if not novo_hash: return False
        return not any(self.extrair_hash_magnet(link) == novo_hash for link in self.links_ja_capturados)

    def deve_ignorar_link(self, nome_link):
        """Verifica se o link deve ser ignorado com base em palavras-chave de baixa qualidade."""
        # Removemos a restrição de \b (palavra exata) para pegar variações como 'camrip'
        # Palavras-chave que geralmente indicam baixa qualidade de vídeo/áudio.
        # A verificação é feita em minúsculas para ser case-insensitive.
        # Removemos a restrição de `\b` (fronteira de palavra) para capturar variações como 'camrip'.
        palavras_para_ignorar = ['cam', 'hdcam', 'ts', 'hdts', 'telesync', 'subbed']
        nome_lower = nome_link.lower()
        return any(palavra in nome_lower for palavra in palavras_para_ignorar)

    def salvar_link_novo(self, magnet_link, links_novos_encontrados):
        """Salva um novo link magnético se ele não existir no histórico."""
        if not self.eh_link_novo(magnet_link): return False
        
        links_novos_encontrados.add(magnet_link)
        self.links_ja_capturados.add(magnet_link)
        
        with open(self.arquivo_novos, 'a', encoding='utf-8') as f: f.write(magnet_link + '\n')
        with open(self.arquivo_todos, 'a', encoding='utf-8') as f: f.write(magnet_link + '\n')
        return True

    # --- MOTOR DE VARREDURA PROFUNDA ---

    def processar_site(self, site_url):
        """Orquestra a varredura completa de um único site."""
        """
        Orquestra a varredura completa de um único site.
        Cria uma instância de SiteScanner e inicia o processo de varredura.
        """
        logging.info(f"{ '='*20} PROCESSANDO SITE: {site_url} { '='*20}")
        scanner = SiteScanner(site_url, self)
        novos_links_count, todos_links_site = scanner.iniciar_varredura()
        logging.info(f"📊 Site {site_url} finalizado: {novos_links_count} novos links encontrados.")
        return novos_links_count, todos_links_site

    # --- GERENCIAMENTO E EXECUÇÃO ---

    def carregar_sites_para_busca(self):
        """Carrega a lista de sites do arquivo base_busca.txt."""
        if not os.path.exists(self.arquivo_base):
            logging.error(f"❌ Arquivo {self.arquivo_base} não encontrado!")
            return []
        sites = []
        with open(self.arquivo_base, 'r', encoding='utf-8') as f:
            for linha in f:
                if linha.strip() and not linha.startswith('#') and linha.startswith('http'):
                    sites.append(linha.strip())
        logging.info(f"🌐 {len(sites)} sites carregados para a busca.")
        return sites

    def executar_busca(self):
        """Executa a busca em todos os sites da lista."""
        """
        Método principal que executa a busca em todos os sites da lista.
        Limpa arquivos antigos, processa cada site sequencialmente e, ao final,
        chama a função para gerar os relatórios de categorias.
        """
        logging.info("🚀 INICIANDO BUSCA PROFISSIONAL")
        if os.path.exists(self.arquivo_novos): os.remove(self.arquivo_novos)
        
        sites = self.carregar_sites_para_busca()
        if not sites: return

        links_novos_geral = set()
        todos_os_links_da_execucao = set()
        
        for site in sites:
            novos_links_count, todos_links_site = self.processar_site(site)
            # A função salvar_link_novo já adiciona em links_novos_geral, mas fazemos aqui para garantir consistência
            # Na verdade, a responsabilidade deveria ser de quem chama, vamos ajustar
            todos_os_links_da_execucao.update(todos_links_site)
            logging.info(f"⏰ Aguardando {self.config['delay_entre_sites']}s antes de ir para o próximo site...")
            time.sleep(self.config['delay_entre_sites'])

        # Carrega os links novos do arquivo para garantir que temos todos
        if os.path.exists(self.arquivo_novos):
            with open(self.arquivo_novos, 'r', encoding='utf-8') as f:
                links_novos_geral = {line.strip() for line in f}

        logging.info("\n" + "=" * 60)
        logging.info("🎉 BUSCA FINALIZADA!")
        logging.info(f"🎯 Total de novos links encontrados nesta execução: {len(links_novos_geral)}")
        logging.info(f"🔗 Total de links na base histórica: {len(self.links_ja_capturados)}")
        
        if todos_os_links_da_execucao:
            logging.info("\n📁 ORGANIZANDO TODOS OS LINKS ENCONTRADOS POR CATEGORIAS:")
            self.gerar_relatorio_categorias(todos_os_links_da_execucao)
        
        logging.info(f"\n💾 Arquivos atualizados:")
        logging.info(f"   • {self.arquivo_novos} - Apenas os links novos desta busca.")
        logging.info(f"   • {self.arquivo_todos} - Todos os links já encontrados.")
        logging.info(f"   • links-*.txt - Links encontrados nesta busca, organizados por categoria.")

    # --- CATEGORIZAÇÃO E RELATÓRIOS ---

    def extrair_nome_magnet(self, magnet_link):
        """
        Extrai o nome do arquivo (parâmetro 'dn') de um link magnético.
        Decodifica o nome para lidar com caracteres especiais (ex: %20 para espaço).
        """
        try:
            nome_match = re.search(r'dn=([^&]+)', magnet_link)
            return unquote(nome_match.group(1)) if nome_match else "Sem nome"
        except: return "Sem nome"

    def categorizar_link(self, magnet_link):
        """
        Categoriza um link magnético com base em palavras-chave encontradas em seu nome.
        As categorias são focadas no tipo de áudio (Dual Audio, Dublado, Legendado).
        """
        nome = self.extrair_nome_magnet(magnet_link).lower()
        if any(p in nome for p in ['dual audio', 'dual.audio', 'dual-audio']): return "Dual-Audio"
        if any(p in nome for p in ['dublado', 'dub', 'pt-br', 'pt br']): return "Dublado"
        if any(p in nome for p in ['legendado', 'leg']): return "Legendado"
        return "Outros"

    def gerar_relatorio_categorias(self, links_para_categorizar):
        """Gera arquivos .txt para cada categoria, usando a lista de links fornecida."""
        """
        Gera arquivos .txt separados para cada categoria de áudio.
        Utiliza a lista de links encontrados na execução atual para criar os relatórios,
        incluindo um cabeçalho com informações úteis em cada arquivo.
        """
        logging.info(f"Gerando relatórios para {len(links_para_categorizar)} links.")
        categorias = { "Dual-Audio": [], "Dublado": [], "Legendado": [], "Outros": [] }
        
        for link in links_para_categorizar:
            categoria = self.categorizar_link(link)
            if categoria not in categorias: categorias[categoria] = []
            categorias[categoria].append(link)
            
        for categoria, links in categorias.items():
            if links:
                arquivo_categoria = f"links-{categoria.lower().replace(' ', '-')}.txt"
                with open(arquivo_categoria, 'w', encoding='utf-8') as f:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    cabecalho = f"# Categoria: {categoria}\n# Total de links: {len(links)}\n# Gerado em: {timestamp}\n\n"
                    f.write(cabecalho)
                    for link in links:
                        f.write(link + '\n')
                logging.info(f"✅ Categoria [{categoria}] salva em '{arquivo_categoria}' com {len(links)} links.")



class SiteScanner:
    """
    Classe responsável por escanear um único site de forma profunda e multi-thread.
    Gerencia a fila de URLs a visitar, o respeito ao `robots.txt` e a extração de links.
    """
    def __init__(self, site_url, main_crawler):
        self.main_crawler = main_crawler
        self.config = main_crawler.config
        self.site_url = site_url
        self.dominio_parseado = urlparse(site_url)
        
        self.urls_para_visitar = Queue()
        self.urls_para_visitar.put(site_url)
        self.urls_visitadas = set()
        self.novos_links_encontrados_site = 0
        self.todos_links_encontrados_site = set()
        
        self.lock = threading.Lock()
        self.running = True
        
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.robot_parser.set_url(urljoin(site_url, '/robots.txt'))
        try:
            self.robot_parser.read()
            logging.info("🤖 Robots.txt carregado com sucesso.")
        except Exception as e:
            logging.warning(f"⚠️ Não foi possível carregar robots.txt: {e}")

    def pode_rastrear(self, url):
        """Verifica se a URL pode ser rastreada de acordo com as regras do `robots.txt` do site."""
        try: return self.robot_parser.can_fetch(self.main_crawler.session.headers['User-Agent'], url)
        except: return True

    def eh_url_valida(self, url):
        try:
        """
        Verifica se uma URL é válida para o crawling.
        - Garante que a URL pertence ao mesmo domínio do site inicial.
        - Ignora links que apontam para arquivos (zip, rar, pdf, etc.) para focar em páginas HTML.
        """
        try: # Envolve em try-except para lidar com URLs malformadas
            parsed = urlparse(url)
            if parsed.netloc != self.dominio_parseado.netloc: return False
            if any(url.lower().endswith(ext) for ext in ['.zip', '.rar', '.exe', '.pdf', '.jpg', '.png', '.css', '.js']): return False
            return True
        except: return False

    def worker(self):
        """Thread de trabalho que processa URLs da fila até que self.running seja False."""
        """
        Função executada por cada thread. Pega uma URL da fila, baixa a página,
        procura por links magnéticos e por novos links de páginas para adicionar à fila,
        respeitando as regras de `robots.txt` e os delays configurados.
        """
        while self.running:
            try:
                url = self.urls_para_visitar.get(timeout=1)
                
                with self.lock:
                    if url in self.urls_visitadas: 
                        self.urls_para_visitar.task_done()
                        continue
                    self.urls_visitadas.add(url)

                if not self.pode_rastrear(url): 
                    logging.debug(f"🚫 Bloqueado por robots.txt: {url}")
                    self.urls_para_visitar.task_done()
                    continue

                try:
                    time.sleep(self.config['delay_entre_requests'])
                    response = self.main_crawler.session.get(url, timeout=10)
                    response.raise_for_status()
                    
                    if 'text/html' in response.headers.get('content-type', ''):
                        magnets = set(re.findall(r'magnet:\?[^\s"\']+', response.text, re.IGNORECASE))
                        links_novos_nesta_pagina = set()
                        for magnet in magnets:
                            nome_magnet = self.main_crawler.extrair_nome_magnet(magnet)
                            if self.main_crawler.deve_ignorar_link(nome_magnet): continue
                            
                            self.todos_links_encontrados_site.add(magnet)

                            if self.main_crawler.salvar_link_novo(magnet, links_novos_nesta_pagina):
                                logging.info(f"🎯 NOVO LINK ({self.main_crawler.categorizar_link(magnet)}): {nome_magnet[:60]}...")
                        
                        with self.lock: self.novos_links_encontrados_site += len(links_novos_nesta_pagina)

                        soup = BeautifulSoup(response.text, 'html.parser')
                        for link in soup.find_all('a', href=True):
                            url_absoluta = urljoin(url, link['href'])
                            if self.eh_url_valida(url_absoluta):
                                with self.lock:
                                    if url_absoluta not in self.urls_visitadas and url_absoluta not in list(self.urls_para_visitar.queue):
                                        self.urls_para_visitar.put(url_absoluta)
                except requests.exceptions.RequestException as e:
                    logging.error(f"❌ Erro de requisição ao processar {url}: {e}")
                except Exception as e:
                    logging.error(f"❌ Erro inesperado ao processar {url}", exc_info=True)
                
                self.urls_para_visitar.task_done()
            except Empty:
                # A fila está vazia, o worker continua no loop até self.running ser False.
                continue
            except Exception as e:
                logging.critical(f"CRITICAL ERRO no worker: {e}", exc_info=True)

    def iniciar_varredura(self):
        """Inicia e gerencia as threads de varredura de forma robusta."""
        """
        Inicia e gerencia as threads de varredura para o site.
        Cria as threads, aguarda a conclusão do processamento da fila de URLs
        e lida com interrupções manuais (Ctrl+C) de forma segura.
        """
        threads = [threading.Thread(target=self.worker, name=f"Worker-{i+1}", daemon=True) for i in range(self.config['max_threads'])]
        for t in threads: t.start()

        # Bloco principal de monitoramento: espera a fila esvaziar.
        try:
            self.urls_para_visitar.join()
            logging.info("Fila de URLs processada. Finalizando workers...")
        except KeyboardInterrupt:
            logging.warning("\n🛑 Interrupção manual detectada. Finalizando workers...")
            self.running = False # Sinaliza para as threads pararem

        # Sinaliza para as threads pararem e espera por elas
        self.running = False
        for t in threads: t.join(timeout=5)
        
        print() # Nova linha para limpar a barra de status
        return self.novos_links_encontrados_site, self.todos_links_encontrados_site



def criar_arquivo_base_exemplo():
    """
    Cria o arquivo `base_busca.txt` com um exemplo se ele não existir.
    Facilita o primeiro uso do script pelo usuário.
    """
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
        config = {
            "max_threads": 5,
            "delay_entre_requests": 1,
            "delay_entre_sites": 5,
        }
        logging.info("=" * 60)
        logging.info("🕵️ CRAWLER PROFISSIONAL")
        logging.info(f"⚙️  Configuração: {config['max_threads']} threads, {config['delay_entre_requests']}s de delay por request.")
        logging.info("=" * 60)
        crawler = CrawlerProfissional(config)
        crawler.executar_busca()
        input("\nPressione Enter para finalizar...")