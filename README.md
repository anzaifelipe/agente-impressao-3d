# agente-impressao-3d

Sistema determinístico de análise de modelos STL para impressão 3D FDM. Ele produz fatos geométricos, interpreta escala declarada, verifica volume de construção, mede overhang, compara orientações e gera uma recomendação explicável.

Os cálculos determinísticos são separados de uma futura camada de IA: um agente poderá explicar resultados e ajudar com políticas, mas não substitui os contratos reproduzíveis do pacote.

## Arquitetura

- `domain`: modelos imutáveis, configurações, resultados JSON-friendly e portas; não depende de `trimesh`.
- `application`: casos de uso e políticas determinísticas; não importa `trimesh`.
- `infrastructure`: adapters de leitura baseados em `trimesh`.
- `cli`: adapter de entrada com `argparse`, responsável apenas por argumentos, dependências e JSON.

```text
                         STL
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
     AnalyzeStl     AnalyzeOverhang  AnalyzeOrientation
          │                                │
          ▼                                │
 AnalyzeScaleAndUnit                       │
          │                                │
          ▼                                │
 AnalyzeBuildVolume                        │
          └────────────────┬───────────────┘
                           ▼
              AnalyzePrintRecommendation
                           │
                           ▼
                  AnalyzePrintPlan
                           │
                           ▼
                          JSON
```

## Funcionalidades

### Análise STL

`AnalyzeStl` produz `StlAnalysisResult` com contagem de triângulos, bounding box, dimensões, watertightness e volume quando confiável. Assumptions e warnings estruturados, como `MESH_NOT_WATERTIGHT`, fazem parte do contrato.

### Escala e unidade

`AnalyzeScaleAndUnit` reutiliza `StlAnalysisResult`. Expõe dimensões observadas, `scale_factor`, dimensões físicas e unidade física declarada. O sistema não tenta detectar unidade formalmente ausente no STL.

### Volume de construção

`PrinterProfile` descreve fabricante, modelo, volume e unidade. `AnalyzeBuildVolume` compara por eixo e informa `fits`, `fits_x`, `fits_y`, `fits_z`, `remaining_space` e `overflow`. Igualdade exata cabe; excessos geram `MODEL_EXCEEDS_BUILD_VOLUME`.

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

`AnalyzePrintPlan` é um envelope composicional de STL, escala/unidade, volume, orientação e recomendação. Ele valida a fonte comum e não recalcula fatos ou decisões.

## CLI

Use a CLI baseada somente em `argparse`:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer-manufacturer "Bambu Lab" \
  --printer-model "A1 Mini" \
  --build-volume 180 180 180 \
  --build-volume-unit mm \
  --scale-factor 100 \
  --physical-unit mm \
  --overhang-threshold 45 \
  --batch-size 100000 \
  --max-recommended-overhang 25
```

Sem `--output`, o JSON completo é escrito em `stdout`. Para salvar:

```bash
uv run agente-impressao-3d analyze /caminho/modelo.stl \
  --printer-manufacturer "Bambu Lab" \
  --printer-model "A1 Mini" \
  --build-volume 180 180 180 \
  --output resultado.json
```

Alternativamente:

```bash
uv run python -m agente_impressao_3d.cli.main analyze /caminho/modelo.stl ...
```

Erros previsíveis, como arquivo ausente, extensão inválida, valores numéricos inválidos, unidades incompatíveis e volume inválido, retornam código diferente de zero sem traceback de uso normal.

## Resultado

Cada capability possui `to_dict()`. A CLI serializa o envelope final:

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
    "print_recommendation": {}
  }
}
```

O contrato de `PrintPlanAnalysisResult` permanece focado em seus cinco subresultados. A CLI acrescenta o resultado especializado de overhang ao JSON final por meio de `OverhangAnalysisResult.to_dict()`, sem recalcular ou copiar fatos manualmente.

## Performance e limitações

- STLs podem ter milhões de triângulos.
- Overhang e orientação usam processamento NumPy por batches e não criam objetos Python por triângulo.
- As seis orientações usam os mesmos dados de cada batch, sem seis cópias da malha.
- Os adapters `trimesh` ainda carregam a malha em memória; não há leitura STL completamente streaming.
- Apenas seis orientações ortogonais são avaliadas; não há rotação arbitrária.
- O sistema não gera suportes, G-code ou configurações de slicer e não substitui um slicer.
- A orientação de normais depende do winding e permanece explicitamente não verificada.
- Contato com a mesa é uma estimativa geométrica, não uma garantia de adesão física.
