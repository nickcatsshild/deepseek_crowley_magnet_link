# install_simple.py
import os
import sys

def install_dependencies_simple():
    """Instalação simples e direta"""
    
    dependencies = [
        'requests',
        'beautifulsoup4', 
        'lxml'
    ]
    
    print("Instalando dependências...")
    
    for package in dependencies:
        os.system(f'"{sys.executable}" -m pip install {package}')
    
    print("Instalação concluída!")

if __name__ == "__main__":
    install_dependencies_simple()
    input("Pressione Enter para sair...")