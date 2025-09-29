import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time
from collections import deque
import threading
from queue import Queue
import json

class MagnetCrawler:
    def __init__(self, dominio_base, max_paginas=100, delay=1):
        self.dominio_base = dominio_base
        self.dominio_parseado = urlparse(dominio_base)
        self.urls_visitadas = set()
        self.urls_para_visitar = deque([dominio_base])
        self.links_magneticos = set()
        self.max_paginas = max_paginas
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def eh_url_valida(self, url):
        """Verifica se a URL pertence ao domínio base"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.dominio_parseado.netloc
        except:
            return False
            
    def extrair_links(self, html, url_base):
        """Extrai todos os links válidos da página"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            # Converter URL relativa para absoluta
            url_absoluta = urljoin(url_base, href)
            if self.eh_url_valida(url_absoluta) and url_absoluta not in self.urls_visitadas:
                links.append(url_absoluta)
                
        return links
    
    def extrair_links_magneticos(self, html):
        """Extrai links magnéticos do HTML"""
        # Regex para links magnéticos
        magnet_links = re.findall(r'magnet:\?[^\s"\'<>]+', html, re.IGNORECASE)
        
        # Procurar em tags <a>
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('magnet:'):
                magnet_links.append(href)
                
        return list(set(magnet_links))  # Remover duplicatas
    
    def crawler_pagina(self, url):
        """Processa uma única página"""
        try:
            print(f"Visitando: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Extrair links magnéticos
            magnets = self.extrair_links_magneticos(response.text)
            if magnets:
                print(f"Encontrados {len(magnets)} links magnéticos em {url}")
                self.links_magneticos.update(magnets)
            
            # Extrair links para outras páginas
            novos_links = self.extrair_links(response.text, url)
            for link in novos_links:
                if link not in self.urls_visitadas and link not in self.urls_para_visitar:
                    self.urls_para_visitar.append(link)
            
            self.urls_visitadas.add(url)
            time.sleep(self.delay)  # Respeitar o site
            
        except Exception as e:
            print(f"Erro ao processar {url}: {e}")
    
    def iniciar_crawler(self):
        """Inicia o processo de crawling"""
        print(f"Iniciando crawler no domínio: {self.dominio_base}")
        print(f"Limite de páginas: {self.max_paginas}")
        
        while self.urls_para_visitar and len(self.urls_visitadas) < self.max_paginas:
            url = self.urls_para_visitar.popleft()
            self.crawler_pagina(url)
        
        self.salvar_resultados()
    
    def salvar_resultados(self):
        """Salva os resultados em arquivos"""
        # Salvar em arquivo de texto
        with open('links_magneticos.txt', 'w', encoding='utf-8') as f:
            for link in self.links_magneticos:
                f.write(link + '\n')
        
        # Salvar em JSON com metadados
        resultados = {
            'dominio': self.dominio_base,
            'paginas_visitadas': len(self.urls_visitadas),
            'total_links_magneticos': len(self.links_magneticos),
            'links': list(self.links_magneticos)
        }
        
        with open('resultado_crawler.json', 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== RESULTADOS ===")
        print(f"Páginas visitadas: {len(self.urls_visitadas)}")
        print(f"Links magnéticos encontrados: {len(self.links_magneticos)}")
        print(f"Arquivos salvos: links_magneticos.txt e resultado_crawler.json")

# Versão Multithreaded para maior velocidade
class MagnetCrawlerMultiThreaded(MagnetCrawler):
    def __init__(self, dominio_base, max_paginas=100, max_threads=5):
        super().__init__(dominio_base, max_paginas)
        self.max_threads = max_threads
        self.lock = threading.Lock()
        self.queue = Queue()
        
    def worker(self):
        """Thread worker para processar URLs"""
        while True:
            try:
                url = self.queue.get(timeout=10)
                if url is None or len(self.urls_visitadas) >= self.max_paginas:
                    self.queue.task_done()
                    break
                    
                self.crawler_pagina(url)
                self.queue.task_done()
                
            except:
                break
    
    def iniciar_crawler(self):
        """Inicia crawler com múltiplas threads"""
        print(f"Iniciando crawler multithreaded...")
        
        # Adicionar URLs iniciais à fila
        for url in list(self.urls_para_visitar):
            self.queue.put(url)
        
        # Iniciar threads
        threads = []
        for i in range(self.max_threads):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Aguardar conclusão
        self.queue.join()
        
        # Parar threads
        for _ in range(self.max_threads):
            self.queue.put(None)
        
        for t in threads:
            t.join()
        
        self.salvar_resultados()

# Função de uso simples
def crawler_simples(dominio, max_paginas=50):
    """Função simplificada para uso rápido"""
    crawler = MagnetCrawler(dominio, max_paginas)
    crawler.iniciar_crawler()

# Exemplo de uso
if __name__ == "__main__":
    # Exemplo 1: Crawler básico
    dominio = "https://www.starckfilmes.fans"  # Substitua pelo domínio desejado
    crawler_simples(dominio, max_paginas=50)
    
    # Exemplo 2: Crawler multithreaded (mais rápido)
    # crawler = MagnetCrawlerMultiThreaded(dominio, max_paginas=100, max_threads=3)
    # crawler.iniciar_crawler()