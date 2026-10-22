# Data card – base sintética da APS do Recife

| Item | Descrição |
|---|---|
| Nome | Base sintética da APS do Recife (leiaute PEC e-SUS APS 8.7.0) |
| Versão do gerador | 1.0.0 (`config/cenario_base.yaml`, `versao_gerador`) |
| Responsáveis | Equipe 2 – Nexus Data · Projeto 3 – Dados · CESAR School · 2026.2 |
| Parceiro | Secretaria de Saúde do Recife (SESAU), Gerência de Atenção Primária / políticas de equidade |
| Natureza | **Totalmente sintética.** Produzida por um modelo estatístico gerativo; nenhum registro foi copiado, transformado ou anonimizado de dados reais de pessoas |

## Finalidade

- Desenvolver e testar, sem dado pessoal, o pipeline de monitoramento do registro de orientação sexual, identidade de gênero, raça/cor e deficiência no cadastro individual da APS. O pipeline inclui banco, validações, camada analítica, painel e modelos.
- Avaliar métodos contra uma verdade conhecida, num estudo de simulação: estimativas por equipe, correção de viés, efeito de ações formativas e previsão.
- Servir de material didático das disciplinas do 3º período.

**Usos fora do escopo:** apresentar números da base como estatística do Recife; inferir ou atribuir características autodeclaradas a pessoas reais; treinar modelos para uso em pessoas reais sem nova validação com dados autorizados.

## Composição

| Tabela (núcleo) | Unidade | Observação |
|---|---|---|
| `cidadao` | pessoa cadastrada | Nome, CPF e CNS fictícios, com dígito verificador válido |
| `cadastro_individual` | versão da FCI | Cadeia de versões (uuid / originadora), saídas por óbito e mudança |
| `cadastro_deficiencia` | tipo declarado por versão | |
| `domicilio`, `familia` | FCDT | Setores censitários sintéticos |
| `ficha_atendimento`, `atendimento_individual`, `atendimento_problema` | FAI | CIAP2 e CID-10 |
| `microarea`, `profissional`, `lotacao`, `acao_formativa` | rede | Equipes e unidades **reais** do CNES; profissionais fictícios |
| `controle_defeito` | gabarito | Defeitos de comportamento (Etapa 6) e de processo (Etapa 7) |

A pasta `verdade/` traz os atributos latentes e as probabilidades usadas na geração. Ela existe só para avaliação e não entra no banco.

## Fontes e premissas

As fontes oficiais estão em `dados/parametros/` (Etapa 5) e em `dados/parametros_complementares/`:

- Censo 2022, tabelas SIDRA 9606, 9922/9923, 10061, 10125, 10132, 10145 e 10296;
- PNS 2019;
- CNES (outubro de 2026);
- boletim SESAU 01/2025 (nascidos vivos e óbitos por raça/cor, consultas de pré-natal).

Cada parâmetro de `config/cenario_base.yaml` traz a classe de evidência: [A] oficial, [B] literatura, [C] direção de estudo de serviço, [P] premissa. As premissas mais importantes estão abaixo, e cada uma tem um cenário de sensibilidade:

- Semântica do "Não" sem pergunta (π).
- Não resposta informativa de pessoas LGB+ (λ).
- Dispersão entre equipes (σ).
- Efeito das oficinas.
- Cobertura cadastral.
- Sensibilidade do registro de deficiência.

## Qualidade conhecida (intencional)

Os defeitos são injetados com taxas declaradas e registrados um a um em `controle_defeito`:

1. duplicidade de cidadão;
2. raça/cor em categoria errada (heteroidentificação, excesso de "amarela");
3. raça/cor divergente entre versões;
4. raça/cor vazia em cadastro legado;
5. cadastro desatualizado (óbito ou mudança não registrados);
6. orientação sexual ou identidade de gênero registrada para criança;
7. erro de digitação em nome ou endereço;
8. data de nascimento implausível;
9. escolaridade incompatível com a idade;
10. atraso de digitação;
11. pergunta não feita;
12. "Não" sem a pergunta;
13. "Tem deficiência" sem registro.

## Limites

- **Margens, não microdados.** A base reproduz margens e relações declaradas (Censo, boletim, planilha da SESAU). Combinações que não foram modeladas não têm validade empírica.
- **Raça/cor por bairro.** É estimada: o Censo 2022 não a publica por bairro.
- **Setores censitários.** São sintéticos.
- **Taxas de atendimento.** São premissas de ordem de grandeza.
- **Metas por USF.** Vêm de uma priori enquanto a planilha não for autorizada.

## Privacidade

Nenhum dado pessoal foi usado. Equipes e unidades são públicas (CNES). Nomes vêm das listas do Faker (pt_BR) e endereços são inventados; os endereços ficam só na *staging* e não entram em análise (RN23). A análise é feita por equipe e período (RN28).

## Reprodutibilidade

A mesma configuração e a mesma semente geram arquivos idênticos byte a byte. O `manifesto.json` de cada saída registra o SHA-256 de cada arquivo, e há teste para isso em `tests/test_geracao.py`.
