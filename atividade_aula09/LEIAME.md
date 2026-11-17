# Atividade da Aula 09 – bases proxy por Distrito Sanitário no Neon

> **Dados sintéticos.** Nenhuma linha descreve pessoas reais nem a população do Recife.

Script: `gerar_respostas_neon.py`. Ele gera uma base por DS (10% dos adultos, semente `2026 + id_ds`), grava `respostas_sinteticas` no Neon, valida por SQL e por `binomtest` contra 2,5% (IC de Wilson) e escreve o relatório em `saida/` (fora do Git). Detalhes e resultado de referência: seção 9 do `README.md` da raiz.

## Passo a passo (primeiro uso do Neon)

1. **Criar o projeto.** Em <https://console.neon.tech>, *Create project*, nome livre, região mais próxima. O projeto vem com o branch `main` e o banco `neondb`.
2. **Copiar a connection string.** Botão *Connect*, branch `main`, banco `neondb`. Para criar a tabela, desmarque *Connection pooling* (string *direct*, sem `-pooler` no host). A string contém a senha: não cole em chat, código nem Git.
3. **Definir a variável de ambiente** (PowerShell, na raiz do repositório; vale só para a janela):
   ```powershell
   $env:APS_DSN="<connection string>"
   ```
   Conferir sem mostrar a senha: `if ($env:APS_DSN) { "definida" } else { "VAZIA" }`.
4. **Instalar as dependências:**
   ```powershell
   .\.venv\Scripts\python -m pip install numpy pandas scipy "psycopg[binary]"
   ```
5. **Testar a conexão (opcional) e rodar:**
   ```powershell
   .\.venv\Scripts\python -c "import os, psycopg; print(psycopg.connect(os.environ['APS_DSN']).execute('select version()').fetchone()[0])"
   .\.venv\Scripts\python atividade_aula09\gerar_respostas_neon.py
   ```
6. **Conferir no Neon** (*SQL Editor*):
   ```sql
   SELECT id_ds, COUNT(*) FROM respostas_sinteticas GROUP BY id_ds ORDER BY id_ds;
   ```
   Esperado: 8 distritos com 5.793, 16.511, 10.225, 22.145, 19.324, 19.198, 13.640 e 10.094 linhas.
7. **Se a string vazar**, redefina a senha do role em *Branches › main › Roles* e atualize o `APS_DSN`.

Sem banco: `python atividade_aula09\gerar_respostas_neon.py --sem-banco`.
