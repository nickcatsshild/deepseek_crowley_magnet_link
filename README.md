# DeepSeek Crowley Magnet Link - Crawler Profissional

Este projeto contém um crawler avançado de links magnéticos, projetado para ser robusto, configurável e eficiente. O script principal e recomendado para uso é o `crawler_profissional.py`.

## 🚀 Script Principal: `crawler_profissional.py`

Este script é a versão unificada e aprimorada, combinando as melhores características dos scripts legados. Ele foi projetado para realizar uma busca completa e inteligente em múltiplos sites.

### Funcionalidades Principais

- **Busca em Múltiplos Sites**: Lê uma lista de sites do arquivo `base_busca.txt` para escanear.
- **Histórico Persistente**: Mantém um registro de todos os links já encontrados (`links-magnetic-download.txt`) para evitar a adição de duplicatas.
- **Detecção de Novidades**: Ao re-escanear um site, ele identifica e salva apenas os links que ainda não estão no histórico.
- **Varredura Profunda**: Navega por todas as páginas internas de cada site para garantir uma busca completa.
- **Comportamento Configurável**: Permite ajustar o número de `threads` e `delays` para controlar a velocidade, podendo operar de forma lenta e cuidadosa ("como um humano") ou de forma rápida e agressiva.
- **Rastreamento Ético**: Respeita as regras definidas no arquivo `robots.txt` de cada site.
- **Categorização Automática**: Organiza os novos links encontrados em arquivos de texto separados por categoria (Filmes, Séries, Jogos, etc.), prontos para importação.

### Como Usar

1.  **Configure os Sites**: Abra o arquivo `base_busca.txt` e adicione a lista de sites que você deseja escanear (um site por linha).
2.  **Ajuste as Configurações (Opcional)**: Abra o `crawler_profissional.py` e, no final do arquivo (dentro de `if __name__ == "__main__":`), você pode alterar as configurações de `max_threads` e `delay_entre_requests` para se adequar às suas necessidades.
    *   `max_threads`: Para um comportamento mais lento e cuidadoso, use `1`. Para mais velocidade, aumente para `5` ou `10`.
    *   `delay_entre_requests`: Tempo em segundos entre cada requisição. É recomendado manter em `1` ou mais para não sobrecarregar os servidores dos sites.
3.  **Execute o Script**: Abra seu terminal e execute o comando:
    ```sh
    python crawler_profissional.py
    ```
4.  **Verifique os Resultados**: Ao final da execução, os novos links serão salvos em:
    *   `links-novos.txt`: Contém apenas os links encontrados na última execução.
    *   `links-<categoria>.txt`: Arquivos separados para cada categoria (ex: `links-filmes.txt`).
    *   `links-magnetic-download.txt`: O arquivo com o histórico completo de todos os links já encontrados.

---

## Legacy Scripts (Versões Antigas)

Os scripts a seguir foram usados para construir a versão profissional e são mantidos como referência, mas **não são recomendados para uso regular**.

-   **`deepseek_1.py`**: Um crawler básico de thread única para um único domínio.
-   **`deepseek.py`**: Um crawler multi-site com histórico e categorização, mas com um motor de busca superficial.
-   **`deepseek_digite_site.py`**: Um crawler multi-thread rápido e profundo, mas apenas para um único site e sem histórico persistente.
