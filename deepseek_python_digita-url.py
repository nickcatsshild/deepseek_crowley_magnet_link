import requests
from bs4 import BeautifulSoup
import re

def teste_rapido(url):
    """Teste super simples para ver se funciona"""
    print(f"🔍 Testando: {url}")
    
    try:
        # Fazer request
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        print(f"✅ Conexão OK - Status: {response.status_code}")
        
        # Procurar links magnéticos
        magnets = re.findall(r'magnet:\?[^\s"\'<>]+', response.text, re.IGNORECASE)
        
        if magnets:
            print(f"🎯 ENCONTRADOS {len(magnets)} LINKS MAGNÉTICOS!")
            for i, magnet in enumerate(magnets[:3]):  # Mostrar apenas 3
                print(f"   {i+1}. {magnet[:100]}...")
            
            # Salvar
            with open('magnets.txt', 'w') as f:
                for magnet in magnets:
                    f.write(magnet + '\n')
            print(f"💾 Salvos em magnets.txt")
        else:
            print("❌ Nenhum link magnético encontrado na página inicial")
            print("💡 Dica: Talvez os links estejam em páginas internas")
            
    except Exception as e:
        print(f"❌ ERRO: {e}")

# Teste imediato
if __name__ == "__main__":
    url = input("Digite a URL para testar: ").strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    teste_rapido(url)