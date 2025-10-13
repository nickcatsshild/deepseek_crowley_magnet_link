# install_dependencies.py
import subprocess
import sys
import os

def install_packages():
    """Instala todas as dependências necessárias para o crawler"""
    
    # Lista de pacotes necessários
    packages = [
        'requests',
        'beautifulsoup4',
        'lxml',  # Parser mais rápido para BeautifulSoup
        'urllib3',
        'certifi',  # Para SSL
    ]
    
    print("🚀 INSTALANDO DEPENDÊNCIAS DO CRAWLER")
    print("=" * 50)
    
    for package in packages:
        try:
            print(f"📦 Instalando {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ {package} instalado com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar {package}: {e}")
            return False
    
    print("\n" + "=" * 50)
    print("🎉 TODAS AS DEPENDÊNCIAS FORAM INSTALADAS!")
    print("\n📚 Pacotes instalados:")
    for package in packages:
        print(f"   • {package}")
    
    print("\n🚀 Agora você pode executar qualquer um dos scripts:")
    print("   python crawler_profissional.py")
    print("   python deepseek_digite_site.py")
    print("   python deepseek.py")
    
    return True

def verify_installation():
    """Verifica se as dependências estão instaladas corretamente"""
    print("\n🔍 VERIFICANDO INSTALAÇÃO...")
    
    packages_to_check = {
        'requests': 'requests',
        'beautifulsoup4': 'bs4',
        'lxml': 'lxml',
    }
    
    all_ok = True
    for package, import_name in packages_to_check.items():
        try:
            __import__(import_name)
            print(f"✅ {package} - OK")
        except ImportError:
            print(f"❌ {package} - FALTA INSTALAR")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("CRAWLER PROFISSIONAL - INSTALADOR DE DEPENDÊNCIAS")
    print("=" * 60)
    
    # Instalar pacotes
    success = install_packages()
    
    if success:
        # Verificar instalação
        if verify_installation():
            print("\n🎉 Tudo pronto! Seus scripts estão prontos para uso.")
        else:
            print("\n⚠️  Alguns pacotes podem não ter sido instalados corretamente.")
            print("   Execute este script novamente ou instale manualmente.")
    else:
        print("\n❌ Houve erros durante a instalação.")
        print("   Tente executar como administrador ou verifique sua conexão com a internet.")
    
    input("\nPressione Enter para sair...")