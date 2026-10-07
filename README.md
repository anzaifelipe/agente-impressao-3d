# agente-impressao-3d

Sistema determinístico de análise de modelos STL para impressão 3D FDM. Ele produz fatos geométricos, interpreta escala declarada, verifica volume de construção, mede overhang, compara orientações e gera uma recomendação explicável.

Os cálculos determinísticos são separados de uma futura camada de IA: um agente poderá explicar resultados e ajudar com políticas, mas não substitui os contratos reproduzíveis do pacote.

## Arquitetura

- `domain`: modelos imutáveis, configurações, resultados JSON-friendly e portas; não depende de `trimesh`.
- `application`: casos de uso e políticas determinísticas; não importa `trimesh`.
- `infrastructure`: adapters `trimesh` e catálogos embutidos, implementando portas do domínio.
- `cli`: adapter de entrada com `argparse`, responsável por argumentos, dependências e apresentação.
- `tools`: adapters estruturados para futuras integrações de agentes; não são um agente e não dependem da CLI.

```text
       AnalyzeStl
            │
            ▼
 AnalyzeScaleAndUnit
            │
            ▼
 AnalyzeBuildVolume
            │
            ├─────────────────┐
            │                 │
            ▼                 ▼
 AnalyzeOrientation     AnalyzeOverhang
            │                 │
            ▼                 │
 AnalyzePrintRecommendation  │
            │                 │
            └────────┬────────┘
                     ▼
            AnalyzePrintPlan
                     │
                     ▼
          SummarizePrintPlan
                     │
                     ├─────────────┐
                     ▼             ▼
                    CLI      Futuro Agente/API/UI
```

## Tool Layer

A Tool Layer explícita adapta capabilities selecionadas da aplicação para consumidores estruturados, como um futuro adapter para Hermes ou outro orquestrador. Ela não implementa Hermes, LLM, rede, API ou memória de agente.

Cada ferramenta expõe `name`, `description`, `input_schema` e `handler`. O registro é estático e pode ser obtido por `build_tools(...)`; a execução ocorre por `execute_tool(tools, name, arguments)`.

Ferramentas disponíveis:

- `list_printer_profiles`
- `get_cli_configuration`
- `set_default_printer_profile`
- `analyze_print_plan`
- `analyze_surface_quality`

O contrato de sucesso é:

```json
{"ok": true, "result": {}}
```

E erros previsíveis usam:

```json
{"ok": false, "error": {"code": "INVALID_TOOL_ARGUMENTS", "message": "..."}}
```

Os schemas são validados de forma mínima e explícita para as ferramentas: campos obrigatórios, tipos básicos e propriedades inesperadas. Erros conhecidos da aplicação, como perfil inexistente e configuração ausente, recebem códigos estruturados; erros inesperados continuam visíveis ao integrador em vez de serem mascarados como sucesso.

`analyze_print_plan` recebe ao menos `{"path": "..."}` e pode receber `printer_profile`, `scale_factor`, `physical_unit`, `overhang_threshold`, `batch_size`, `max_recommended_overhang`, `nozzle_diameter`, `minimum_layer_height`, `maximum_layer_height`, `target_normal_step` e `surface_region_count`. Ele chama a orquestração de aplicação que reutiliza `AnalyzeStl`, escala/unidade, volume, overhang, orientação, recomendação, qualidade de superfície e `AnalyzePrintPlan`; não chama a CLI ou subprocessos.

`analyze_surface_quality` aceita `path` e controles de escala, batch, nozzle e alturas de camada. Para faces inclinadas, a métrica é `estimated_normal_step = layer_height × abs(normal_z)`: uma aproximação determinística de discretização, não uma medida de curvatura CAD ou defeito visual. Faces quase horizontais e verticais são excluídas; o desvio-padrão ponderado de `abs(normal_z)` é apenas um proxy de variação de orientação. As candidatas padrão 0,16 / 0,12 / 0,10 / 0,08 mm são filtradas pelos limites informados do nozzle.

A saída preserva `regions` como faixas fixas de Z de fallback e acrescenta `critical_regions`: patches de células espaciais adjacentes de alta severidade. Cada patch contém limites espaciais, área afetada, severidade, recomendação e as faixas de fallback que ele atravessa. `cost_benefit` estima equivalentes de camada por patch e resolve sobreposições Z na agenda agregada; isso é uma estimativa geométrica, não previsão de tempo de slicer, movimento ou fluxo.

A versão 3 mantém `estimated_normal_step = layer_height × abs(normal_z)` somente como diagnóstico legado. A seleção principal usa `estimated_geometric_error = curvature_z_proxy × layer_height² / 8`; `curvature_z_proxy` é a variação local estimada de `normal_z` em relação a Z numa grade espacial compacta, não curvatura CAD exata. A grade tem `maximum_spatial_cells` configurável (2.000.000 por padrão), limitando a memória adicional pelo número de células, não pelo número de arestas ou triângulos. Planos e paredes de normal constante não são selecionados apenas por inclinação.

V3.1 preserva os patches em `critical_regions` e publica `consolidated_regions` como uma visão derivada para automação. A consolidação compara apenas bounds de patches, sem conectividade de triângulos: layer recomendado deve ser igual, a razão de severidade deve respeitar `region_merge_severity_ratio` e a distância Euclidiana entre bounds, incluindo a lacuna Z, deve respeitar `region_merge_distance`. Cada região consolidada lista os índices de patches auditáveis, área, bounds, severidade e erro geométrico máximo/médio. `consolidated_cost_benefit` compara a agenda geométrica formada pelos bounds consolidados com a agenda dos patches originais.

## Orquestração determinística

Esta camada não é um agente de IA: não utiliza LLM, prompts, memória, planejamento, rede ou Hermes. Ela recebe uma intenção estruturada, faz uma única seleção determinística de ferramenta, executa-a e trata o retorno como uma observation.

```text
Request → Action Selection → Tool Selection → Tool Execution → Observation → Result
```

O contrato de request é `{"action": "...", "arguments": {...}}`. As ações disponíveis e seu mapeamento explícito são:

- `list_printer_profiles` → `list_printer_profiles`
- `get_configuration` → `get_cli_configuration`
- `set_default_printer_profile` → `set_default_printer_profile`
- `analyze_model` → `analyze_print_plan`
- `analyze_surface_quality` → `analyze_surface_quality`

O resultado preserva a intenção e a ferramenta selecionada:

```json
{"ok": true, "action": "analyze_model", "tool": "analyze_print_plan", "result": {}}
```

Uma ação desconhecida retorna `UNKNOWN_ACTION` antes de chamar a Tool Layer. Para ações conhecidas, erros estruturados da ferramenta, como `INVALID_TOOL_ARGUMENTS` ou `UNKNOWN_PRINTER_PROFILE`, são preservados no resultado. A camada é preparada para um futuro adapter de orquestração baseado em IA, como Hermes, sem acoplar o núcleo a esse framework.

## Funcionalidades

### Análise STL

`AnalyzeStl` produz `StlAnalysisResult` com contagem de triângulos, bounding box, dimensões, watertightness e volume quando confiável. Assumptions e warnings estruturados, como `MESH_NOT_WATERTIGHT`, fazem parte do contrato.

### Escala e unidade

`AnalyzeScaleAndUnit` reutiliza `StlAnalysisResult`. Expõe dimensões observadas, `scale_factor`, dimensões físicas e unidade física declarada. O sistema não tenta detectar unidade formalmente ausente no STL.

### Volume de construção

`PrinterProfile` descreve fabricante, modelo, volume e unidade. `AnalyzeBuildVolume` compara por eixo e informa `fits`, `fits_x`, `fits_y`, `fits_z`, `remaining_space` e `overflow`. Igualdade exata cabe; excessos geram `MODEL_EXCEEDS_BUILD_VOLUME`.

### Perfis de impressora reutilizáveis

O catálogo embutido resolve identificadores estáveis para `PrinterProfile`, sem rede, banco de dados ou arquivos externos. O domínio permanece independente de fabricantes e do catálogo concreto; o catálogo é apenas uma conveniência na infraestrutura.

Perfis disponíveis inicialmente:

- `bambu-lab-a1-mini` — Bambu Lab A1 Mini, 180 × 180 × 180 mm.

### Configuração persistente da CLI

`CliConfiguration` contém somente a versão do schema e o perfil padrão de impressora. Ela é persistida pela infraestrutura em JSON; domínio e application não conhecem JSON, caminhos do sistema ou `argparse`.

Inicialize a configuração uma única vez e escolha um perfil padrão:

```bash
uv run agente-impressao-3d config init
uv run agente-impressao-3d config set-printer bambu-lab-a1-mini
```

Consulte a configuração atual em JSON:

```bash
uv run agente-impressao-3d config show
```

`config init` não sobrescreve uma configuração existente. `config set-printer` valida o identificador no catálogo embutido e cria a configuração caso ela ainda não exista; ao atualizar, preserva os demais campos para evolução futura.

### Overhang

`AnalyzeOverhang` processa faces em batches vetorizados. Informa contagens, área total, área de overhang e percentual usando um threshold configurável. A condição é equivalente a:

```text
dot(face_normal, build_direction) < 0
and dot(face_normal, build_direction) <= -sin(threshold_degrees)
```

O limite é inclusivo. Como normais derivam do winding, o resultado inclui `NORMAL_ORIENTATION_UNVERIFIED`.

### Orientação

`AnalyzeOrientation` avalia seis candidatas ortogonais: `positive_x`, `negative_x`, `positive_y`, `negative_y`, `positive_z` e `negative_z`.

Cada candidata informa dimensões físicas, fit no volume, altura, espaço/excesso por eixo, overhang e contato estimado com a mesa. O contato exige face voltada para baixo com os três vértices no plano mínimo dentro da tolerância configurada.

O ranking é determinístico:

1. cabe no volume;
2. menor área de overhang;
3. menor altura;
4. maior contato estimado;
5. nome como desempate estável.

Não há busca de rotações arbitrárias.

### Recomendação de impressão

`AnalyzePrintRecommendation` apenas interpreta resultados já calculados. Seus status são `RECOMMENDED`, `PRINTABLE_WITH_WARNINGS`, `NOT_RECOMMENDED` e `NOT_FIT`. Não existe score opaco ou `printable` simplista; a recomendação respeita o ranking existente e preserva warnings com origem.

### Print Plan

`AnalyzePrintPlan` é o envelope canônico de STL, escala/unidade, volume, overhang, orientação e recomendação. Ele valida a fonte comum e não recalcula fatos ou decisões.

### Print Plan Summary

`SummarizePrintPlan` recebe exclusivamente um `PrintPlanAnalysisResult` e produz um `PrintPlanSummaryResult` compacto, JSON-friendly e independente da CLI. Ele organiza dimensões físicas, compatibilidade com o volume, orientação e altura recomendadas, overhang, status da recomendação e warnings com origem explícita.

O `PrintPlanAnalysisResult` continua sendo o resultado técnico completo, com todos os subresultados especializados. O `PrintPlanSummaryResult` é uma visão para pessoas e interfaces: não acessa arquivos, não recalcula geometria, overhang ou ranking, não cria uma recomendação nova e não substitui o plano técnico.

## CLI

Use a CLI baseada somente em `argparse`. Liste os perfis reutilizáveis disponíveis com:

```bash
uv run agente-impressao-3d printers
```

Sem uma opção de saída técnica, a análise mostra no terminal um resumo humano baseado em `PrintPlanSummaryResult`. Um perfil embutido elimina a necessidade de repetir seus dados:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer bambu-lab-a1-mini \
  --scale-factor 100 \
  --physical-unit mm
```

Perfis manuais continuam suportados e exigem fabricante, modelo e volume:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer-manufacturer "Custom Printer" \
  --printer-model "Example" \
  --build-volume 220 220 250 \
  --build-volume-unit mm \
  --scale-factor 100 \
  --physical-unit mm \
  --overhang-threshold 45 \
  --batch-size 100000 \
  --max-recommended-overhang 25
```

O resumo apresenta status, dimensões físicas, compatibilidade com o volume, orientação e altura recomendadas, overhang e avisos. Ele é apenas uma apresentação e não recalcula resultados.

Quando nenhum perfil é informado no comando `analyze`, a CLI usa o `default_printer_profile` persistido. A precedência é: `--printer` explícito, perfil manual completo, configuração persistente e, por fim, erro previsível. Argumentos explícitos nunca modificam a configuração. `--printer` continua incompatível com argumentos manuais de perfil.

### JSON técnico

Para emitir o contrato técnico completo `PrintPlanAnalysisResult` no `stdout`, use `--json`:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer bambu-lab-a1-mini \
  --json
```

Esse JSON é apropriado para automação, scripts, API, agentes e interfaces. Para salvar o mesmo JSON técnico completo em arquivo:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer bambu-lab-a1-mini \
  --output resultado.json
```

Nesse modo o terminal mostra somente uma confirmação curta com o status. `--json` e `--output` não podem ser usados juntos: ambos destinam o mesmo resultado técnico completo. Também não é permitido combinar `--printer` com argumentos manuais de perfil; escolha exatamente um modo.

Alternativamente:

```bash
uv run python -m agente_impressao_3d.cli.main analyze /caminho/modelo.stl ...
```

Erros previsíveis, como arquivo ausente, extensão inválida, valores numéricos inválidos, unidades incompatíveis e volume inválido, retornam código diferente de zero sem traceback de uso normal.

## Resultado

Cada capability possui `to_dict()`. `PrintPlanAnalysisResult` é o envelope técnico canônico e contém todos os resultados especializados:

```json
{
  "schema_version": "1.0",
  "source": {"path": "/caminho/modelo.stl", "format": "stl"},
  "analyses": {
    "stl": {},
    "scale_and_unit": {},
    "build_volume": {},
    "overhang": {},
    "orientation": {},
    "print_recommendation": {},
    "surface_quality": {}
  }
}
```

`PrintPlanSummaryResult` é o resumo compacto para apresentação na CLI e futuro consumo humano. Ele não substitui o `PrintPlanAnalysisResult`, não altera recomendações e não recalcula análises. O plano técnico permanece o contrato para automação, API, agentes e integração entre capabilities.

## Performance e limitações

- STLs podem ter milhões de triângulos.
- Overhang e orientação usam processamento NumPy por batches e não criam objetos Python por triângulo.
- As seis orientações usam os mesmos dados de cada batch, sem seis cópias da malha.
- Os adapters `trimesh` ainda carregam a malha em memória; não há leitura STL completamente streaming.
- Apenas seis orientações ortogonais são avaliadas; não há rotação arbitrária.
- O sistema não gera suportes, G-code ou configurações de slicer e não substitui um slicer.
- A orientação de normais depende do winding e permanece explicitamente não verificada.
- A análise de qualidade de superfície usa orientação de facetas e faixas de Z; não reconstrói curvatura nem reconhece semanticamente cabeças, caudas ou outros recursos do modelo.
- Contato com a mesa é uma estimativa geométrica, não uma garantia de adesão física.
