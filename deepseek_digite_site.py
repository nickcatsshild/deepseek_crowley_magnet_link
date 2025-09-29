import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlencode
import re
import time
import threading
from queue import Queue, Empty
import json
import os
from collections import defaultdict
import hashlib

class CrawlerProfissional:
    def __init__(self, dominio_base, max_threads=10, delay=0.5):
        self.dominio_base = dominio_base
        self.dominio_parseado = urlparse(dominio_base)
        self.base_netloc = self.dominio_parseado.netloc
        
        # Controle de URLs
        self.urls_visitadas = set()
        self.urls_para_visitar = Queue()
        self.urls_para_visitar.put(dominio_base)
        self.lock = threading.Lock()
        
        # Resultados
        self.links_magneticos = set()
        self.paginas_por_diretorio = defaultdict(list)
        self.estatisticas = {
            'total_paginas': 0,
            'total_magnets': 0,
            'erros': 0,
            'inicio': time.time()
        }
        
        # Configurações
        self.max_threads = max_threads
        self.delay = delay
        self.running = True
        
        # Session com configurações profissionais
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Padrões de exclusão
        self.extensiones_excluidas = {
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.mp4', '.avi', '.mkv', '.mov', '.wmv',
            '.mp3', '.wav', '.flac', '.ogg',
            '.exe', '.msi', '.dmg', '.deb', '.rpm',
            '.css', '.js', '.json', '.xml'
        }
        
        print(f"🚀 CRAWLER PROFISSIONAL INICIADO")
        print(f"📍 Domínio: {self.dominio_base}")
        print(f"🧵 Threads: {self.max_threads}")
        print(f"⏰ Delay: {self.delay}s")
        print("-" * 60)
    
    def eh_url_valida(self, url):
        """Verifica se a URL é válida para crawling"""
        try:
            parsed = urlparse(url)
            
            # Verificar domínio
            if parsed.netloc != self.base_netloc:
                return False
            
            # Verificar extensões excluídas
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in self.extensiones_excluidas):
                return False
            
            # Excluir URLs muito longas (possível conteúdo dinâmico)
            if len(url) > 250:
                return False
            
            # Excluir URLs com muitos parâmetros
            if len(parsed.query) > 100:
                return False
            
            return True
            
        except Exception:
            return False
    
    def normalizar_url(self, url):
        """Normaliza a URL para evitar duplicatas"""
        parsed = urlparse(url)
        
        # Remover fragmentos e ordenar parâmetros
        query_params = []
        if parsed.query:
            params = parse_qs(parsed.query)
            for key in sorted(params.keys()):
                for value in sorted(params[key]):
                    query_params.append(f"{key}={value}")
        
        normalized_query = "&".join(query_params)
        normalized_path = parsed.path.rstrip('/') or '/'
        
        if normalized_query:
            return f"{parsed.scheme}://{parsed.netloc}{normalized_path}?{normalized_query}"
        else:
            return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
    
    def extrair_links_completos(self, html, url_base):
        """Extrai todos os links possíveis do HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        links_encontrados = set()
        
        # Tags que podem conter URLs
        tags_com_href = ['a', 'link', 'area', 'base']
        tags_com_src = ['script', 'img', 'iframe', 'frame', 'embed', 'source']
        meta_tags = ['meta', 'og:url', 'twitter:url']
        
        # Extrair de tags com href
        for tag_name in tags_com_href:
            for tag in soup.find_all(tag_name, href=True):
                href = tag['href']
                if href and not href.startswith(('javascript:', 'mailto:', 'tel:')):
                    url_absoluta = urljoin(url_base, href)
                    if self.eh_url_valida(url_absoluta):
                        links_encontrados.add(self.normalizar_url(url_absoluta))
        
        # Extrair de tags com src
        for tag_name in tags_com_src:
            for tag in soup.find_all(tag_name, src=True):
                src = tag['src']
                if src:
                    url_absoluta = urljoin(url_base, src)
                    if self.eh_url_valida(url_absoluta):
                        links_encontrados.add(self.normalizar_url(url_absoluta))
        
        # Extrair de meta tags
        for meta in soup.find_all('meta', content=True):
            content = meta.get('content', '')
            if 'http' in content:
                url_match = re.search(r'(https?://[^\s<>"]+)', content)
                if url_match:
                    url_absoluta = url_match.group(1)
                    if self.eh_url_valida(url_absoluta):
                        links_encontrados.add(self.normalizar_url(url_absoluta))
        
        # Extrair URLs do texto (para casos de links não taggeados)
        texto_pagina = soup.get_text()
        urls_texto = re.findall(r'https?://[^\s<>"]+', texto_pagina)
        for url in urls_texto:
            if self.eh_url_valida(url):
                links_encontrados.add(self.normalizar_url(url))
        
        return list(links_encontrados)
    
    def extrair_magnets_avancado(self, html, url):
        """Extrai links magnéticos com técnicas avançadas"""
        magnets_encontrados = set()
        
        # Regex mais abrangente para magnets
        padroes_magnet = [
            r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}[^\s"\'<>]*',
            r'magnet:\?[^\s"\'<>]{10,500}',  # Pattern genérico
        ]
        
        for padrao in padroes_magnet:
            magnets = re.findall(padrao, html, re.IGNORECASE)
            for magnet in magnets:
                # Limpar e validar
                magnet_limpo = magnet.split('"')[0].split("'")[0].split(' ')[0]
                if self.validar_magnet(magnet_limpo):
                    magnets_encontrados.add(magnet_limpo)
        
        # Procurar em atributos data-*, info-*, etc.
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(True):  # Todas as tags
            for attr, value in tag.attrs.items():
                if isinstance(value, str) and 'magnet:' in value:
                    magnet_match = re.search(r'magnet:\?[^\s"\'<>]+', value)
                    if magnet_match:
                        magnet_limpo = magnet_match.group(0)
                        if self.validar_magnet(magnet_limpo):
                            magnets_encontrados.add(magnet_limpo)
        
        return list(magnets_encontrados)
    
    def validar_magnet(self, magnet_link):
        """Valida se o link magnético é válido"""
        if not magnet_link.startswith('magnet:?'):
            return False
        
        # Verificar componentes mínimos
        if 'xt=urn:btih:' not in magnet_link:
            return False
        
        # Verificar hash
        hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', magnet_link)
        if not hash_match:
            return False
        
        # Tamanho razoável
        if len(magnet_link) > 1000:
            return False
        
        return True
    
    def processar_pagina(self, url):
        """Processa uma página individual"""
        try:
            with self.lock:
                if url in self.urls_visitadas:
                    return []
                self.urls_visitadas.add(url)
            
            # Delay para respeitar o servidor
            time.sleep(self.delay)
            
            print(f"🌐 [{threading.current_thread().name}] Processando: {url}")
            
            # Fazer request
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            # Verificar se é HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return []
            
            html = response.text
            
            # Extrair magnets
            magnets = self.extrair_magnets_avancado(html, url)
            if magnets:
                with self.lock:
                    self.links_magneticos.update(magnets)
                    self.estatisticas['total_magnets'] += len(magnets)
                print(f"🎯 [{threading.current_thread().name}] Encontrados {len(magnets)} magnets!")
            
            # Extrair links
            novos_links = self.extrair_links_completos(html, url)
            
            # Registrar estatísticas
            with self.lock:
                self.estatisticas['total_paginas'] += 1
                diretorio = urlparse(url).path.rsplit('/', 1)[0] if '/' in urlparse(url).path else '/'
                self.paginas_por_diretorio[diretorio].append(url)
            
            return novos_links
            
        except Exception as e:
            with self.lock:
                self.estatisticas['erros'] += 1
            print(f"❌ [{threading.current_thread().name}] Erro em {url}: {e}")
            return []
    
    def worker(self):
        """Thread worker para processamento paralelo"""
        while self.running:
            try:
                url = self.urls_para_visitar.get(timeout=10)
                
                # Processar página
                novos_links = self.processar_pagina(url)
                
                # Adicionar novos links à fila
                for link in novos_links:
                    if link not in self.urls_visitadas:
                        self.urls_para_visitar.put(link)
                
                self.urls_para_visitar.task_done()
                
            except Empty:
                continue
            except Exception as e:
                print(f"❌ Erro no worker: {e}")
    
    def iniciar_varredura_completa(self):
        """Inicia a varredura completa do site"""
        print("🚀 INICIANDO VARREDURA COMPLETA DO SITE")
        print("⏳ Isso pode levar vários minutos...")
        
        # Criar e iniciar threads
        threads = []
        for i in range(self.max_threads):
            t = threading.Thread(target=self.worker, name=f"Thread-{i+1}")
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Aguardar processamento
        try:
            while not self.urls_para_visitar.empty() or threading.active_count() > 1:
                time.sleep(1)
                
                # Mostrar progresso a cada 30 segundos
                if int(time.time()) % 30 == 0:
                    self.mostrar_progresso()
                    
        except KeyboardInterrupt:
            print("\n⏹️  Varredura interrompida pelo usuário")
            self.running = False
        
        # Finalizar
        self.running = False
        self.finalizar_varredura()
    
    def mostrar_progresso(self):
        """Mostra o progresso atual da varredura"""
        with self.lock:
            stats = self.estatisticas.copy()
            magnets = len(self.links_magneticos)
            visitadas = len(self.urls_visitadas)
            na_fila = self.urls_para_visitar.qsize()
        
        tempo_decorrido = time.time() - stats['inicio']
        paginas_por_minuto = stats['total_paginas'] / (tempo_decorrido / 60) if tempo_decorrido > 0 else 0
        
        print(f"\n📊 PROGRESSO - {time.strftime('%H:%M:%S')}")
        print(f"📄 Páginas processadas: {stats['total_paginas']}")
        print(f"🔗 Links magnéticos: {magnets}")
        print(f"📂 URLs na fila: {na_fila}")
        print(f"⚡ Velocidade: {paginas_por_minuto:.1f} páginas/minuto")
        print(f"⏱️  Tempo decorrido: {tempo_decorrido/60:.1f} minutos")
        print(f"❌ Erros: {stats['erros']}")
        print("-" * 50)
    
    def finalizar_varredura(self):
        """Finaliza a varredura e salva resultados"""
        print("\n🎉 VARREDURA FINALIZADA!")
        
        # Estatísticas finais
        tempo_total = time.time() - self.estatisticas['inicio']
        
        print(f"\n📈 ESTATÍSTICAS FINAIS:")
        print(f"⏱️  Tempo total: {tempo_total/60:.2f} minutos")
        print(f"📄 Páginas processadas: {self.estatisticas['total_paginas']}")
        print(f"🔗 Links magnéticos encontrados: {len(self.links_magneticos)}")
        print(f"📂 Diretórios explorados: {len(self.paginas_por_diretorio)}")
        print(f"❌ Erros: {self.estatisticas['erros']}")
        
        # Salvar resultados
        self.salvar_resultados_completos()
    
    def salvar_resultados_completos(self):
        """Salva todos os resultados em arquivos organizados"""
        if not self.links_magneticos:
            print("❌ Nenhum link magnético encontrado")
            return
        
        # Criar diretório para resultados
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        pasta_resultados = f"resultados_{self.base_netloc}_{timestamp}"
        os.makedirs(pasta_resultados, exist_ok=True)
        
        # 1. Arquivo principal para qBittorrent
        arquivo_principal = os.path.join(pasta_resultados, "links_magneticos.txt")
        with open(arquivo_principal, 'w', encoding='utf-8') as f:
            for magnet in sorted(self.links_magneticos):
                f.write(magnet + '\n')
        
        # 2. Arquivo com metadados
        arquivo_detalhado = os.path.join(pasta_resultados, "detalhes_magneticos.csv")
        with open(arquivo_detalhado, 'w', encoding='utf-8') as f:
            f.write("Hash,Nome,Tamanho,Link\n")
            for magnet in self.links_magneticos:
                # Extrair informações
                hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', magnet)
                nome_match = re.search(r'dn=([^&]+)', magnet)
                tamanho_match = re.search(r'xl=(\d+)', magnet)
                
                hash_val = hash_match.group(1) if hash_match else "N/A"
                nome_val = requests.utils.unquote(nome_match.group(1)) if nome_match else "Sem nome"
                tamanho_val = tamanho_match.group(1) if tamanho_match else "N/A"
                
                f.write(f'"{hash_val}","{nome_val}","{tamanho_val}","{magnet}"\n')
        
        # 3. Relatório completo em JSON
        relatorio = {
            'dominio': self.dominio_base,
            'timestamp': timestamp,
            'estatisticas': self.estatisticas,
            'diretorios_explorados': dict(self.paginas_por_diretorio),
            'total_links_magneticos': len(self.links_magneticos),
            'links_magneticos': list(self.links_magneticos)
        }
        
        with open(os.path.join(pasta_resultados, "relatorio_completo.json"), 'w', encoding='utf-8') as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 RESULTADOS SALVOS EM: {pasta_resultados}/")
        print(f"📄 links_magneticos.txt - Para importar no qBittorrent")
        print(f"📊 detalhes_magneticos.csv - Informações detalhadas")
        print(f"📋 relatorio_completo.json - Relatório completo da varredura")

# Função de uso simplificado
def varredura_completa_site():
    """Interface simples para o usuário"""
    print("🌐 CRAWLER PROFISSIONAL - VARREDURA COMPLETA")
    print("=" * 60)
    
    # Solicitar URL
    url = input("Digite a URL completa do site: ").strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    # Configurações
    try:
        threads = int(input("Número de threads (padrão 10): ") or "10")
        delay = float(input("Delay entre requests em segundos (padrão 0.5): ") or "0.5")
    except:
        threads = 10
        delay = 0.5
    
    print(f"\n⚙️  Configurações:")
    print(f"   URL: {url}")
    print(f"   Threads: {threads}")
    print(f"   Delay: {delay}s")
    print(f"\n⏳ Iniciando varredura completa...")
    
    # Iniciar crawler
    crawler = CrawlerProfissional(url, max_threads=threads, delay=delay)
    crawler.iniciar_varredura_completa()

if __name__ == "__main__":
    varredura_completa_site()