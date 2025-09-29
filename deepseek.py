import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import re
import time
import os
from datetime import datetime

class CrawlerInteligente:
    def __init__(self):
        # Arquivos de configuração
        self.arquivo_base = "base_busca.txt"
        self.arquivo_novos = "links-novos.txt"
        self.arquivo_baixados = "links-baixados.txt"
        self.arquivo_todos = "links-magnetic-download.txt"
        
        # Listas de controle
        self.links_ja_capturados = set()  # Todos os links já vistos
        self.links_novos_encontrados = set()  # Novos nesta execução
        self.links_baixados = set()  # Marcados como baixados
        
        # Carregar dados existentes
        self.carregar_links_existentes()
        
        # Configuração do requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def carregar_links_existentes(self):
        """Carrega todos os links já capturados anteriormente"""
        
        # Carregar links já baixados
        if os.path.exists(self.arquivo_baixados):
            with open(self.arquivo_baixados, 'r', encoding='utf-8') as f:
                for linha in f:
                    linha = linha.strip()
                    if linha.startswith('magnet:'):
                        self.links_ja_capturados.add(linha)
                        self.links_baixados.add(linha)
            print(f"📥 {len(self.links_baixados)} links já baixados carregados")
        
        # Carregar links novos de execuções anteriores
        if os.path.exists(self.arquivo_novos):
            with open(self.arquivo_novos, 'r', encoding='utf-8') as f:
                for linha in f:
                    linha = linha.strip()
                    if linha.startswith('magnet:'):
                        self.links_ja_capturados.add(linha)
            print(f"📋 {len(self.links_ja_capturados) - len(self.links_baixados)} links novos pendentes")
        
        # Carregar arquivo consolidado (se existir)
        if os.path.exists(self.arquivo_todos):
            with open(self.arquivo_todos, 'r', encoding='utf-8') as f:
                for linha in f:
                    linha = linha.strip()
                    if linha.startswith('magnet:'):
                        self.links_ja_capturados.add(linha)
            print(f"📚 Total de {len(self.links_ja_capturados)} links únicos na base")
    
    def carregar_sites_para_busca(self):
        """Carrega a lista de sites do arquivo base_busca.txt"""
        if not os.path.exists(self.arquivo_base):
            print(f"❌ Arquivo {self.arquivo_base} não encontrado!")
            return []
        
        sites = []
        with open(self.arquivo_base, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith('#') and linha.startswith('http'):
                    sites.append(linha)
        
        print(f"🌐 {len(sites)} sites carregados para busca")
        return sites
    
    def extrair_hash_magnet(self, magnet_link):
        """Extrai o hash do link magnético para comparação"""
        hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]{32,40})', magnet_link)
        return hash_match.group(1) if hash_match else None
    
    def eh_link_novo(self, magnet_link):
        """Verifica se o link é novo comparando hashes"""
        novo_hash = self.extrair_hash_magnet(magnet_link)
        if not novo_hash:
            return False  # Link inválido
        
        # Comparar com todos os links já capturados
        for link_existente in self.links_ja_capturados:
            hash_existente = self.extrair_hash_magnet(link_existente)
            if hash_existente and hash_existente.upper() == novo_hash.upper():
                return False  # Já existe
        
        return True  # É novo!
    
    def salvar_link_novo(self, magnet_link, categoria="Geral"):
        """Salva link novo se for realmente novo"""
        if not self.eh_link_novo(magnet_link):
            return False  # Já existe, ignorar
        
        self.links_novos_encontrados.add(magnet_link)
        self.links_ja_capturados.add(magnet_link)
        
        # Salvar no arquivo de novos links
        with open(self.arquivo_novos, 'a', encoding='utf-8') as f:
            f.write(magnet_link + '\n')
        
        # Atualizar arquivo consolidado
        with open(self.arquivo_todos, 'a', encoding='utf-8') as f:
            f.write(magnet_link + '\n')
        
        return True
    
    def extrair_links_pagina(self, html, url_base):
        """Extrai links de uma página"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            if href.startswith('http'):
                url_absoluta = href
            else:
                url_absoluta = urljoin(url_base, href)
            
            # Verificar se é do mesmo domínio
            if urlparse(url_absoluta).netloc == urlparse(url_base).netloc:
                links.append(url_absoluta)
        
        return links
    
    def extrair_links_magneticos(self, html):
        """Extrai links magnéticos do HTML"""
        magnets = re.findall(r'magnet:\?[^\s"\'<>]+', html, re.IGNORECASE)
        return list(set(magnets))
    
    def extrair_nome_magnet(self, magnet_link):
        """Extrai o nome do arquivo do magnet link"""
        try:
            nome_match = re.search(r'dn=([^&]+)', magnet_link)
            if nome_match:
                return unquote(nome_match.group(1))
        except:
            pass
        return "Sem nome"
    
    def categorizar_link(self, magnet_link):
        """Categoriza o link baseado no nome"""
        nome = self.extrair_nome_magnet(magnet_link).lower()
        
        if any(palavra in nome for palavra in ['filme', 'movie', '1080p', '720p', 'bluray', 'dvdrip']):
            return "Filmes"
        elif any(palavra in nome for palavra in ['serie', 'season', 's01', 's02', 'temporada']):
            return "Series"
        elif any(palavra in nome for palavra in ['jogo', 'game', 'repack', 'iso']):
            return "Jogos"
        elif any(palavra in nome for palavra in ['musica', 'album', 'mp3', 'flac']):
            return "Musicas"
        elif any(palavra in nome for palavra in ['software', 'app', 'windows', 'mac']):
            return "Software"
        else:
            return "Outros"
    
    def processar_site(self, url):
        """Processa um site completo, procurando por novos links"""
        print(f"\n🌐 Processando: {url}")
        novos_links_site = 0
        
        try:
            # Fazer request para a página inicial
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            print(f"✅ Site acessível - Status: {response.status_code}")
            
            # Extrair links magnéticos da página inicial
            magnets = self.extrair_links_magneticos(response.text)
            if magnets:
                for magnet in magnets:
                    if self.salvar_link_novo(magnet):
                        novos_links_site += 1
                        nome = self.extrair_nome_magnet(magnet)
                        categoria = self.categorizar_link(magnet)
                        print(f"🎯 NOVO [{categoria}]: {nome[:50]}...")
            
            # Extrair links internos para explorar (buscar mais conteúdo)
            links_internos = self.extrair_links_pagina(response.text, url)
            print(f"📎 {len(links_internos)} links internos encontrados")
            
            # Explorar páginas internas (busca por novos conteúdos)
            paginas_exploradas = 0
            for link in links_internos:
                if paginas_exploradas >= 3:  # Limitar para não demorar muito
                    break
                    
                try:
                    print(f"   🔍 Explorando: {link[:50]}...")
                    response_interna = self.session.get(link, timeout=8)
                    
                    if response_interna.status_code == 200:
                        magnets_internos = self.extrair_links_magneticos(response_interna.text)
                        if magnets_internos:
                            for magnet in magnets_internos:
                                if self.salvar_link_novo(magnet):
                                    novos_links_site += 1
                                    nome = self.extrair_nome_magnet(magnet)
                                    categoria = self.categorizar_link(magnet)
                                    print(f"   🎯 NOVO [{categoria}]: {nome[:40]}...")
                        
                        paginas_exploradas += 1
                        time.sleep(1)  # Delay entre páginas
                    
                except Exception as e:
                    print(f"   ❌ Erro na página interna: {e}")
                    continue
            
            print(f"📊 Site finalizado: {novos_links_site} novos links encontrados")
            return novos_links_site
            
        except Exception as e:
            print(f"❌ Erro ao processar {url}: {e}")
            return 0
    
    def gerar_relatorio_categorias(self):
        """Gera relatório por categorias"""
        categorias = {
            "Filmes": [],
            "Series": [],
            "Jogos": [],
            "Musicas": [],
            "Software": [],
            "Outros": []
        }
        
        # Classificar os novos links por categoria
        for link in self.links_novos_encontrados:
            categoria = self.categorizar_link(link)
            categorias[categoria].append(link)
        
        # Gerar arquivos por categoria
        for categoria, links in categoritas.items():
            if links:
                arquivo_categoria = f"links-{categoria.lower()}.txt"
                with open(arquivo_categoria, 'w', encoding='utf-8') as f:
                    f.write(f"# {categoria} - {len(links)} links\n")
                    for link in links:
                        f.write(link + '\n')
                print(f"📂 {categoria}: {len(links)} links salvos em {arquivo_categoria}")
    
    def executar_busca(self):
        """Executa a busca em todos os sites da lista"""
        print("🚀 INICIANDO BUSCA INTELIGENTE")
        print("=" * 60)
        
        # Carregar lista de sites
        sites = self.carregar_sites_para_busca()
        if not sites:
            return
        
        print(f"🔗 Links já conhecidos: {len(self.links_ja_capturados)}")
        print(f"📥 Links baixados: {len(self.links_baixados)}")
        print("=" * 60)
        
        total_novos_links = 0
        sites_processados = 0
        
        for site in sites:
            sites_processados += 1
            print(f"\n📊 Progresso: {sites_processados}/{len(sites)}")
            
            novos_links = self.processar_site(site)
            total_novos_links += novos_links
            
            # Delay entre sites
            time.sleep(2)
        
        # Resultado final e organização
        print("\n" + "=" * 60)
        print("🎉 BUSCA FINALIZADA!")
        print(f"📊 Sites processados: {sites_processados}")
        print(f"🎯 Novos links encontrados: {total_novos_links}")
        print(f"🔗 Total na base: {len(self.links_ja_capturados)}")
        
        # Gerar categorias se encontrou novos links
        if total_novos_links > 0:
            print("\n📁 ORGANIZANDO POR CATEGORIAS:")
            self.gerar_relatorio_categorias()
        
        print(f"\n💾 Arquivos gerados:")
        print(f"   • {self.arquivo_novos} - Links novos desta busca")
        print(f"   • {self.arquivo_todos} - Todos os links consolidados")
        print(f"   • links-*.txt - Links organizados por categoria")
        print("=" * 60)

# Função para criar arquivo base_busca.txt se não existir
def criar_arquivo_base_exemplo():
    if not os.path.exists("base_busca.txt"):
        with open("base_busca.txt", "w", encoding="utf-8") as f:
            f.write("# Lista de sites para busca\n")
            f.write("# Coloque um site por linha\n")
            f.write("# Exemplo:\n")
            f.write("https://www.starckfilmes.fans\n")
            f.write("https://www.exemplo1.com\n")
            f.write("https://www.exemplo2.com\n")
        print("📄 Arquivo base_busca.txt criado com exemplo!")
        return True
    return False

# Interface principal
def main():
    print("🔍 CRAWLER INTELIGENTE - BUSCA COM CATEGORIAS")
    print("=" * 60)
    
    # Verificar/criar arquivo base
    if criar_arquivo_base_exemplo():
        print("✏️  Edite o arquivo base_busca.txt com os sites que deseja escanear")
        print("💡 Depois execute o script novamente")
        input("Pressione Enter para sair...")
        return
    
    # Iniciar busca
    crawler = CrawlerInteligente()
    
    print("\n⚙️  Configuração Inteligente:")
    print("   • REvisita TODOS os sites (não ignora sites visitados)")
    print("   • IGNORA apenas links duplicados (compara por hash)")
    print("   • Organiza automaticamente por categorias")
    print("   • Mantém histórico completo")
    print("\n🚀 Iniciando busca em 3 segundos...")
    time.sleep(3)
    
    crawler.executar_busca()
    
    input("\nPressione Enter para sair...")

if __name__ == "__main__":
    main()