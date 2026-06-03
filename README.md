# Ionosfera SAO

Aplicativo desktop simples para consultar dados de ionossonda do INPE/Embrace em arquivos `.SAO`, com foco em radioamadorismo HF.

A versão atual usa Python + Tkinter e não depende de navegador.

## O que ele faz

- Busca online o último `.SAO` disponível da estação configurada.
- Interpreta os campos principais do Grupo 4 do arquivo `.SAO`.
- Mostra frequências críticas, alturas, MUF/modelo, Grupo 4 completo e tendência dos últimos arquivos.
- Mostra uma tabela simples por banda: 80m, 40m, 20m, 15m, 12m e 10m.
- Move detalhes técnicos de coleta para a aba final.
- Permite ler arquivos `.SAO` locais de uma pasta.
- Permite copiar resumo e exportar o Grupo 4 em CSV.

## Uso básico

1. Abra o programa.
2. Confirme a estação. O padrão é `CAJ2M`, Cachoeira Paulista.
3. Clique em **Atualizar online**.
4. Use as abas para consultar:
   - Resumo
   - Frequências críticas
   - Alturas
   - MUF / Modelo
   - Grupo 4 completo
   - Tendência
   - Coleta / Técnico

## Interpretação rápida

A tabela por banda é apenas um auxílio rápido baseado nos dados medidos/calculados:

- 80m e 40m usam principalmente `foF2` e `fmin` como referência local/regional.
- 20m, 15m, 12m e 10m usam principalmente `MUF(3000)` como referência para DX F2.
- `foEs` baixo não deve ser interpretado como abertura de 6m.
- `TEC` é informação complementar; ele não decide a melhor banda sozinho.

A decisão real ainda depende de caminho, horário, antena, ruído, potência e atividade real na banda.

## Observações

- “Ao vivo” significa o último ionograma publicado no servidor, não uma medição instantânea contínua.
- A tabela de MUF por distância é uma estimativa simples para panorama. Para comparação exata com o portal, trate os valores de curta distância como aproximação.
- O campo `9999` do `.SAO` é tratado como “sem dado”.
