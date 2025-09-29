import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time
from collections import deque
import json
import urllib.robotparser

class MagnetCrawlerQBittorrent:
    def __init__(self, dominio_base, max_paginas=800, delay=1):
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
        
        # Configurar robots.txt
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.robot_parser.set_url(urljoin(dominio_base, '/robots.txt'))
        try:
            self.robot_parser.read()
            print("Robots.txt carregado com sucesso")
        except:
            print("Não foi possível ler robots.txt")
            
    def pode_rastrear(self, url):
        """Verifica se pode rastrear a URL conforme robots.txt"""
        try:
            return self.robot_parser.can_fetch('*', url)
        except:
            return True  # Se não conseguir verificar, permite por padrão
    
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
            if (self.eh_url_valida(url_absoluta) and 
                url_absoluta not in self.urls_visitadas and
                self.pode_rastrear(url_absoluta)):
                links.append(url_absoluta)
                
        return links
    
    def extrair_links_magneticos(self, html):
        """Extrai links magnéticos do HTML com validação"""
        magnet_links = set()
        
        # Regex mais específica para links magnéticos válidos
        magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}[^\s"\'<>]*'
        found_links = re.findall(magnet_pattern, html, re.IGNORECASE)
        
        for link in found_links:
            # Limpar e validar o link
            clean_link = link.split('"')[0].split("'")[0].split(' ')[0]
            if self.validar_link_magnetico(clean_link):
                magnet_links.add(clean_link)
        
        # Procurar em tags <a>
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('magnet:') and self.validar_link_magnetico(href):
                magnet_links.add(href)
                
        return list(magnet_links)
    
    def validar_link_magnetico(self, link):
        """Valida se o link magnético é válido para qBittorrent"""
        if not link.startswith('magnet:?'):
            return False
        
        # Verificar se tem o hash info (btih)
        if 'xt=urn:btih:' not in link:
            return False
        
        # Verificar se tem hash válido (32-40 caracteres alfanuméricos)
        hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', link)
        if not hash_match:
            return False
            
        return True
    
    def crawler_pagina(self, url):
        """Processa uma única página"""
        try:
            if not self.pode_rastrear(url):
                print(f"Pulando (robots.txt): {url}")
                return
                
            print(f"Visitando: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Extrair links magnéticos
            magnets = self.extrair_links_magneticos(response.text)
            if magnets:
                print(f"✅ Encontrados {len(magnets)} links magnéticos válidos")
                self.links_magneticos.update(magnets)
            
            # Extrair links para outras páginas
            novos_links = self.extrair_links(response.text, url)
            for link in novos_links:
                if link not in self.urls_visitadas and link not in self.urls_para_visitar:
                    self.urls_para_visitar.append(link)
            
            self.urls_visitadas.add(url)
            time.sleep(self.delay)
            
        except Exception as e:
            print(f"❌ Erro ao processar {url}: {e}")
    
    def salvar_para_qbittorrent(self):
        """Salva os links em formatos compatíveis com qBittorrent"""
        
        # Formato 1: Arquivo TXT simples (um link por linha)
        with open('links_qbittorrent.txt', 'w', encoding='utf-8') as f:
            for link in self.links_magneticos:
                f.write(link + '\n')
        
        # Formato 2: Arquivo de download batch (mais organizado)
        with open('downloads_batch.txt', 'w', encoding='utf-8') as f:
            f.write("# Lista de downloads para qBittorrent\n")
            f.write("# Gerado automaticamente\n\n")
            for i, link in enumerate(self.links_magneticos, 1):
                f.write(f"# Download {i}\n")
                f.write(link + '\n\n')
        
        # Formato 3: CSV para referência
        with open('links_detalhados.csv', 'w', encoding='utf-8') as f:
            f.write("Hash,Nome,Link\n")
            for link in self.links_magneticos:
                # Extrair informações do link
                hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', link)
                nome_match = re.search(r'dn=([^&]+)', link)
                
                hash_val = hash_match.group(1) if hash_match else "N/A"
                nome_val = urllib.parse.unquote(nome_match.group(1)) if nome_match else "Sem nome"
                
                f.write(f'"{hash_val}","{nome_val}","{link}"\n')
        
        print(f"Arquivos gerados para qBittorrent:")
        print(f"📄 links_qbittorrent.txt - Lista simples para importar")
        print(f"📄 downloads_batch.txt - Lista organizada")
        print(f"📄 links_detalhados.csv - Lista detalhada com informações")
    
    def iniciar_crawler(self):
        """Inicia o processo de crawling"""
        print(f"🚀 Iniciando crawler no domínio: {self.dominio_base}")
        print(f"📊 Limite de páginas: {self.max_paginas}")
        print(f"⏰ Delay entre requests: {self.delay}s")
        
        while self.urls_para_visitar and len(self.urls_visitadas) < self.max_paginas:
            url = self.urls_para_visitar.popleft()
            self.crawler_pagina(url)
        
        # Salvar resultados
        self.salvar_para_qbittorrent()
        
        # Salvar relatório JSON
        resultados = {
            'dominio': self.dominio_base,
            'paginas_visitadas': list(self.urls_visitadas),
            'total_links_magneticos': len(self.links_magneticos),
            'links_magneticos': list(self.links_magneticos)
        }
        
        with open('relatorio_crawler.json', 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 CRAWLER FINALIZADO!")
        print(f"📈 Páginas visitadas: {len(self.urls_visitadas)}")
        print(f"🔗 Links magnéticos válidos: {len(self.links_magneticos)}")
        print(f"💾 Arquivos salvos:")
        print(f"   - links_qbittorrent.txt (para importar no qBittorrent)")
        print(f"   - downloads_batch.txt")
        print(f"   - links_detalhados.csv")
        print(f"   - relatorio_crawler.json")

# Função de uso simplificado
def crawler_qbittorrent(dominio, max_paginas=50):
    """Função simplificada para uso rápido"""
    crawler = MagnetCrawlerQBittorrent(dominio, max_paginas)
    crawler.iniciar_crawler()

# Exemplo de uso
if __name__ == "__main__":
    # Substitua pelo domínio que deseja escanear
    dominio_alvo = "https://www.starckfilmes.fans"
    
    # Crawler básico
    crawler_qbittorrent(dominio_alvo, max_paginas=50)
    
    # Ou para mais controle:
    # crawler = MagnetCrawlerQBittorrent(dominio_alvo, max_paginas=100, delay=2)
    # crawler.iniciar_crawler()