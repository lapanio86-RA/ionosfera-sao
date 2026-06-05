import re
import math
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE_URL = "https://embracedata.inpe.br/ionosonde"
DIAS_PARA_TRAS = 2  # 0 = hoje, 1 = ontem, 2 = anteontem


# ============================================================
# ESTAÇÕES
# ============================================================

ESTACOES = [
    {"station": "BLJ03", "nome": "Belém", "longitude": -48.5013, "latitude": -1.4563},
    {"station": "SAA0K", "nome": "São Luís", "longitude": -44.2097, "latitude": -2.5941},
    {"station": "FZA0M", "nome": "Fortaleza", "longitude": -38.5270, "latitude": -3.7327},
    {"station": "BVJ03", "nome": "Boa Vista", "longitude": -60.7109, "latitude": 2.8701},
    {"station": "CGK21", "nome": "Campo Grande", "longitude": -54.6218, "latitude": -20.4649},
    {"station": "CAJ2M", "nome": "Cachoeira Paulista", "longitude": -45.0093, "latitude": -22.7038},
    {"station": "SMK29", "nome": "Santa Maria", "longitude": -53.8043, "latitude": -29.6897},
    {"station": "JUA0P", "nome": "Juazeirinho", "longitude": -36.6597, "latitude": -7.0973},
]


# ============================================================
# MAPA DO GRUPO 4 - SAO v4.3 Table 6
# ============================================================

CAMPOS_GRUPO4 = [
    {"posicao_sao": 1,  "campo": "foF2",       "unidade": "MHz",        "descricao": "Frequência crítica da camada F2"},
    {"posicao_sao": 2,  "campo": "foF1",       "unidade": "MHz",        "descricao": "Frequência crítica da camada F1"},
    {"posicao_sao": 3,  "campo": "M(D)",       "unidade": "",           "descricao": "Fator M(D) = MUF(D) / foF2"},
    {"posicao_sao": 4,  "campo": "MUF(D)",     "unidade": "MHz",        "descricao": "Máxima frequência utilizável para distância D"},
    {"posicao_sao": 5,  "campo": "fmin",       "unidade": "MHz",        "descricao": "Menor frequência com eco no ionograma"},
    {"posicao_sao": 6,  "campo": "foEs",       "unidade": "MHz",        "descricao": "Frequência crítica da camada E esporádica"},
    {"posicao_sao": 7,  "campo": "fminF",      "unidade": "MHz",        "descricao": "Menor frequência dos ecos da camada F"},
    {"posicao_sao": 8,  "campo": "fminE",      "unidade": "MHz",        "descricao": "Menor frequência dos ecos da camada E"},
    {"posicao_sao": 9,  "campo": "foE",        "unidade": "MHz",        "descricao": "Frequência crítica da camada E"},
    {"posicao_sao": 10, "campo": "fxI",        "unidade": "MHz",        "descricao": "Maior frequência do traço F"},
    {"posicao_sao": 11, "campo": "h'F",        "unidade": "km",         "descricao": "Altura virtual mínima do traço F"},
    {"posicao_sao": 12, "campo": "h'F2",       "unidade": "km",         "descricao": "Altura virtual mínima do traço F2"},
    {"posicao_sao": 13, "campo": "h'E",        "unidade": "km",         "descricao": "Altura virtual mínima do traço E"},
    {"posicao_sao": 14, "campo": "h'Es",       "unidade": "km",         "descricao": "Altura virtual mínima do traço Es"},
    {"posicao_sao": 15, "campo": "zmE",        "unidade": "km",         "descricao": "Altura de pico da camada E"},
    {"posicao_sao": 16, "campo": "yE",         "unidade": "km",         "descricao": "Semi-espessura da camada E"},
    {"posicao_sao": 17, "campo": "QF",         "unidade": "km",         "descricao": "Espalhamento médio de alcance da camada F"},
    {"posicao_sao": 18, "campo": "QE",         "unidade": "km",         "descricao": "Espalhamento médio de alcance da camada E"},
    {"posicao_sao": 19, "campo": "DownF",      "unidade": "km",         "descricao": "Abaixamento do traço F até a borda principal"},
    {"posicao_sao": 20, "campo": "DownE",      "unidade": "km",         "descricao": "Abaixamento do traço E até a borda principal"},
    {"posicao_sao": 21, "campo": "DownEs",     "unidade": "km",         "descricao": "Abaixamento do traço Es até a borda principal"},
    {"posicao_sao": 22, "campo": "FF",         "unidade": "MHz",        "descricao": "Espalhamento em frequência entre fxF2 e fxI"},
    {"posicao_sao": 23, "campo": "FE",         "unidade": "MHz",        "descricao": "Espalhamento em frequência além de foE"},
    {"posicao_sao": 24, "campo": "D",          "unidade": "km",         "descricao": "Distância usada para cálculo de MUF"},
    {"posicao_sao": 25, "campo": "fMUF",       "unidade": "MHz",        "descricao": "MUF / fator de obliquidade"},
    {"posicao_sao": 26, "campo": "h'(fMUF)",   "unidade": "km",         "descricao": "Altura virtual na frequência fMUF"},
    {"posicao_sao": 27, "campo": "delta_foF2", "unidade": "MHz",        "descricao": "Ajuste aplicado ao foF2 durante inversão de perfil"},
    {"posicao_sao": 28, "campo": "foEp",       "unidade": "MHz",        "descricao": "Valor previsto de foE"},
    {"posicao_sao": 29, "campo": "f(h'F)",     "unidade": "MHz",        "descricao": "Frequência onde ocorre h'F"},
    {"posicao_sao": 30, "campo": "f(h'F2)",    "unidade": "MHz",        "descricao": "Frequência onde ocorre h'F2"},
    {"posicao_sao": 31, "campo": "foF1p",      "unidade": "MHz",        "descricao": "Valor previsto de foF1"},
    {"posicao_sao": 32, "campo": "hmF2",       "unidade": "km",         "descricao": "Altura de pico da camada F2"},
    {"posicao_sao": 33, "campo": "hmF1",       "unidade": "km",         "descricao": "Altura de pico da camada F1"},
    {"posicao_sao": 34, "campo": "zhalfNm",    "unidade": "km",         "descricao": "Altura verdadeira em metade da densidade máxima na F2"},
    {"posicao_sao": 35, "campo": "foF2p",      "unidade": "MHz",        "descricao": "Valor previsto de foF2"},
    {"posicao_sao": 36, "campo": "fminEs",     "unidade": "MHz",        "descricao": "Frequência mínima da camada Es"},
    {"posicao_sao": 37, "campo": "yF2",        "unidade": "km",         "descricao": "Semi-espessura da camada F2"},
    {"posicao_sao": 38, "campo": "yF1",        "unidade": "km",         "descricao": "Semi-espessura da camada F1"},
    {"posicao_sao": 39, "campo": "TEC",        "unidade": "10^16 m^-2", "descricao": "Conteúdo total de elétrons"},
    {"posicao_sao": 40, "campo": "H_F2_peak",  "unidade": "km",         "descricao": "Altura de escala no pico da F2"},
    {"posicao_sao": 41, "campo": "B0",         "unidade": "km",         "descricao": "Parâmetro de espessura IRI B0"},
    {"posicao_sao": 42, "campo": "B1",         "unidade": "",           "descricao": "Parâmetro de forma do perfil IRI B1"},
    {"posicao_sao": 43, "campo": "D1",         "unidade": "",           "descricao": "Parâmetro de forma do perfil IRI D1, camada F1"},
    {"posicao_sao": 44, "campo": "foEa",       "unidade": "MHz",        "descricao": "Frequência crítica da camada E auroral"},
    {"posicao_sao": 45, "campo": "h'Ea",       "unidade": "km",         "descricao": "Altura virtual mínima da camada E auroral"},
    {"posicao_sao": 46, "campo": "foP",        "unidade": "MHz",        "descricao": "Maior frequência crítica ordinária de patch na região F"},
    {"posicao_sao": 47, "campo": "h'P",        "unidade": "km",         "descricao": "Altura virtual mínima do traço usado para determinar foP"},
    {"posicao_sao": 48, "campo": "fbEs",       "unidade": "MHz",        "descricao": "Frequência de blanketing da camada Es"},
    {"posicao_sao": 49, "campo": "TypeEs",     "unidade": "",           "descricao": "Tipo de Es codificado conforme tabela SAO"},
]


# ============================================================
# FUNÇÕES - COLETA
# ============================================================

def interpretar_nome_sao(nome_arquivo):
    padrao = r"^([A-Z0-9]+)_(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})\.SAO$"
    match = re.match(padrao, nome_arquivo)

    if match is None:
        return None

    station, ano_txt, doy_txt, hora_txt, minuto_txt, segundo_txt = match.groups()

    ano = int(ano_txt)
    doy = int(doy_txt)
    hora = int(hora_txt)
    minuto = int(minuto_txt)
    segundo = int(segundo_txt)

    data_base = datetime(ano, 1, 1, tzinfo=timezone.utc)
    utc = data_base + timedelta(days=doy - 1)
    utc = utc.replace(hour=hora, minute=minuto, second=segundo)

    return {
        "station_arquivo": station,
        "ano": ano,
        "dia_juliano": doy,
        "hora": hora,
        "minuto": minuto,
        "segundo": segundo,
        "utc": utc,
    }


def classificar_status(idade_minutos):
    if idade_minutos <= 60:
        return "OK"
    elif idade_minutos <= 6 * 60:
        return "ATRASADA"
    elif idade_minutos <= 24 * 60:
        return "MUITO ATRASADA"
    return "OFFLINE"


def criar_url_pasta(station, data_busca):
    ano = data_busca.year
    doy = str(data_busca.timetuple().tm_yday).zfill(3)
    return f"{BASE_URL}/{station}/{ano}/{doy}/"


def buscar_arquivos_sao_na_pasta(station, nome, url_pasta):
    try:
        resposta = requests.get(url_pasta, timeout=20)
    except requests.RequestException:
        return []

    if resposta.status_code != 200:
        return []

    arquivos = re.findall(rf"{station}_\d{{13}}\.SAO", resposta.text)
    arquivos = sorted(set(arquivos))

    linhas = []

    for arquivo in arquivos:
        info = interpretar_nome_sao(arquivo)
        if info is None:
            continue

        linhas.append({
            "station": station,
            "nome": nome,
            "arquivo": arquivo,
            "url": url_pasta + arquivo,
            "utc": info["utc"],
            "ano": info["ano"],
            "dia_juliano": info["dia_juliano"],
            "hora": info["hora"],
            "minuto": info["minuto"],
            "segundo": info["segundo"],
        })

    return linhas


def coletar_arquivos_recentes(df_estacoes, agora_utc, dias_para_tras=2):
    todos_arquivos = []

    for _, linha in df_estacoes.iterrows():
        station = linha["station"]
        nome = linha["nome"]

        for offset in range(dias_para_tras + 1):
            data_busca = agora_utc - timedelta(days=offset)
            url_pasta = criar_url_pasta(station, data_busca)

            ano_busca = data_busca.year
            doy_busca = str(data_busca.timetuple().tm_yday).zfill(3)

            print(f"verificando {station} ({nome}) - {ano_busca}/{doy_busca}")

            arquivos = buscar_arquivos_sao_na_pasta(station, nome, url_pasta)
            todos_arquivos.extend(arquivos)

    df_arq = pd.DataFrame(todos_arquivos)

    if df_arq.empty:
        return df_arq

    return df_arq.sort_values("utc", ascending=False).reset_index(drop=True)


def montar_status_estacoes(df_estacoes, df_arq, agora_utc):
    if df_arq.empty:
        df_status = df_estacoes.copy()
        df_status["ultimo_arquivo"] = None
        df_status["ultimo_utc"] = None
        df_status["idade_minutos"] = None
        df_status["idade_legivel"] = "sem dados"
        df_status["status"] = "SEM DADOS"
        df_status["url"] = None
        df_status["ordem_status"] = 4
        return df_status

    df_mais_recente = (
        df_arq
        .sort_values("utc", ascending=False)
        .groupby("station", as_index=False)
        .first()
    )

    df_status = df_estacoes.merge(
        df_mais_recente[["station", "arquivo", "url", "utc"]],
        on="station",
        how="left"
    )

    df_status["idade_minutos"] = (
        (agora_utc - df_status["utc"]).dt.total_seconds() / 60
    )

    df_status["status"] = df_status["idade_minutos"].apply(
        lambda x: "SEM DADOS" if pd.isna(x) else classificar_status(x)
    )

    df_status["idade_legivel"] = df_status["idade_minutos"].apply(
        lambda x: "sem dados" if pd.isna(x) else f"{x:.1f} min"
    )

    df_status = df_status.rename(columns={
        "arquivo": "ultimo_arquivo",
        "utc": "ultimo_utc"
    })

    ordem_status = {
        "OK": 0,
        "ATRASADA": 1,
        "MUITO ATRASADA": 2,
        "OFFLINE": 3,
        "SEM DADOS": 4,
    }

    df_status["ordem_status"] = df_status["status"].map(ordem_status)

    return (
        df_status
        .sort_values(["ordem_status", "idade_minutos"], ascending=[True, True])
        .reset_index(drop=True)
    )


# ============================================================
# FUNÇÕES - LEITURA SAO
# ============================================================

def baixar_texto_sao(url_sao):
    resposta = requests.get(url_sao, timeout=20)
    resposta.raise_for_status()
    return resposta.text


def ler_data_index(linhas_sao):
    linha_1 = linhas_sao[0].ljust(120)
    linha_2 = linhas_sao[1].ljust(120)
    texto_index = linha_1 + linha_2

    valores = []

    for i in range(0, 240, 3):
        pedaco = texto_index[i:i + 3]
        valores.append(int(pedaco))

    df_index = pd.DataFrame({
        "grupo": range(1, 81),
        "qtd_elementos": valores
    })

    idx = [None] + valores

    return df_index, idx


def ler_fixed_float(linhas, pos, qtd_elementos, largura, por_linha):
    qtd_linhas = math.ceil(qtd_elementos / por_linha)

    texto = ""
    for linha in linhas[pos:pos + qtd_linhas]:
        texto += linha.ljust(largura * por_linha)

    valores = []

    for i in range(qtd_elementos):
        inicio = i * largura
        fim = inicio + largura
        pedaco = texto[inicio:fim]
        valores.append(float(pedaco))

    nova_pos = pos + qtd_linhas

    return valores, nova_pos


def ler_texto_chars(linhas, pos, qtd_chars):
    qtd_linhas = math.ceil(qtd_chars / 120)

    texto = ""
    for linha in linhas[pos:pos + qtd_linhas]:
        texto += linha.ljust(120)

    texto = texto[:qtd_chars]
    nova_pos = pos + qtd_linhas

    return texto, nova_pos


def parsear_sao_principal(texto_sao):
    linhas_sao = texto_sao.splitlines()

    df_index, idx = ler_data_index(linhas_sao)

    pos = 2

    grupo1, pos = ler_fixed_float(
        linhas=linhas_sao,
        pos=pos,
        qtd_elementos=idx[1],
        largura=7,
        por_linha=16
    )

    grupo2_linhas = linhas_sao[pos:pos + idx[2]]
    grupo2_texto = "\n".join(grupo2_linhas).strip()
    pos = pos + idx[2]

    grupo3_texto, pos = ler_texto_chars(
        linhas=linhas_sao,
        pos=pos,
        qtd_chars=idx[3]
    )

    grupo4, pos = ler_fixed_float(
        linhas=linhas_sao,
        pos=pos,
        qtd_elementos=idx[4],
        largura=8,
        por_linha=15
    )

    df_grupo4_cru = pd.DataFrame({
        "posicao_sao": range(1, len(grupo4) + 1),
        "valor_cru": grupo4
    })

    df_grupo4 = interpretar_grupo4(df_grupo4_cru)

    return {
        "linhas_sao": linhas_sao,
        "df_index": df_index,
        "idx": idx,
        "grupo1": grupo1,
        "grupo2_texto": grupo2_texto,
        "grupo3_texto": grupo3_texto,
        "grupo4": grupo4,
        "df_grupo4_cru": df_grupo4_cru,
        "df_grupo4": df_grupo4,
    }


def interpretar_grupo4(df_grupo4_cru):
    df_mapa = pd.DataFrame(CAMPOS_GRUPO4)

    df = df_grupo4_cru.merge(
        df_mapa,
        on="posicao_sao",
        how="left"
    )

    df["valor"] = df["valor_cru"].apply(
        lambda x: None if abs(x - 9999.0) < 1e-9 else x
    )

    return df


def extrair_parametros_hf(df_grupo4):
    serie = df_grupo4.set_index("campo")["valor"]

    parametros = {
        "foF2": serie.get("foF2"),
        "foF1": serie.get("foF1"),
        "foE": serie.get("foE"),
        "foEs": serie.get("foEs"),
        "fmin": serie.get("fmin"),
        "M(D)": serie.get("M(D)"),
        "MUF(D)": serie.get("MUF(D)"),
        "fxI": serie.get("fxI"),
        "h'F": serie.get("h'F"),
        "h'F2": serie.get("h'F2"),
        "h'E": serie.get("h'E"),
        "h'Es": serie.get("h'Es"),
        "hmF2": serie.get("hmF2"),
        "hmF1": serie.get("hmF1"),
        "TEC": serie.get("TEC"),
        "B0": serie.get("B0"),
        "B1": serie.get("B1"),
    }

    return pd.DataFrame(
        [{"campo": k, "valor": v} for k, v in parametros.items()]
    )


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def main():
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 100)

    agora_utc = datetime.now(timezone.utc)
    df_estacoes = pd.DataFrame(ESTACOES)

    df_arq = coletar_arquivos_recentes(
        df_estacoes=df_estacoes,
        agora_utc=agora_utc,
        dias_para_tras=DIAS_PARA_TRAS
    )

    if df_arq.empty:
        print("\nNenhum arquivo SAO encontrado.")
        return

    df_status = montar_status_estacoes(
        df_estacoes=df_estacoes,
        df_arq=df_arq,
        agora_utc=agora_utc
    )

    colunas_status = [
        "station",
        "nome",
        "status",
        "idade_legivel",
        "ultimo_utc",
        "ultimo_arquivo",
        "url",
    ]

    print("\n=== STATUS DAS ESTAÇÕES ===")
    print(df_status[colunas_status])

    print("\n=== TODOS OS ARQUIVOS SAO COLETADOS ===")
    print(df_arq[["station", "nome", "arquivo", "utc", "url"]].head(20))

    print("\nResumo:")
    print(f"Estações cadastradas: {len(df_estacoes)}")
    print(f"Arquivos SAO encontrados: {len(df_arq)}")
    print(f"Estações com dados: {df_status['ultimo_arquivo'].notna().sum()}")
    print(f"Hora da verificação UTC: {agora_utc}")

    df_disponiveis = df_status[df_status["ultimo_arquivo"].notna()].copy()
    df_disponiveis = df_disponiveis.reset_index(drop=True)

    print("\n=== ESTAÇÕES COM DADOS DISPONÍVEIS ===")

    for i, linha in df_disponiveis.iterrows():
        print(
            f"[{i}] {linha['station']} - {linha['nome']} | "
            f"{linha['status']} | "
            f"idade: {linha['idade_legivel']} | "
            f"último: {linha['ultimo_arquivo']}"
        )

    escolha = int(input("\nEscolha o número da estação que deseja usar: "))
    estacao_escolhida = df_disponiveis.iloc[escolha]

    print("\n=== ESTAÇÃO ESCOLHIDA ===")
    print("station:", estacao_escolhida["station"])
    print("nome:", estacao_escolhida["nome"])
    print("status:", estacao_escolhida["status"])
    print("último arquivo:", estacao_escolhida["ultimo_arquivo"])
    print("url:", estacao_escolhida["url"])

    texto_sao = baixar_texto_sao(estacao_escolhida["url"])

    resultado_sao = parsear_sao_principal(texto_sao)

    print("\n=== DATA INDEX ===")
    print(resultado_sao["df_index"])

    print("\n=== GRUPOS PRESENTES ===")
    print(resultado_sao["df_index"][resultado_sao["df_index"]["qtd_elementos"] > 0])

    print("\n=== GRUPO 1 - GEOFÍSICO ===")
    print(resultado_sao["grupo1"])

    print("\n=== GRUPO 2 - DESCRIÇÃO DO SISTEMA ===")
    print(resultado_sao["grupo2_texto"])

    print("\n=== GRUPO 3 - TIMESTAMP / SETTINGS ===")
    print(resultado_sao["grupo3_texto"])

    print("\n=== GRUPO 4 CRU ===")
    print(resultado_sao["df_grupo4_cru"])

    print("\n=== GRUPO 4 INTERPRETADO COMPLETO ===")
    print(resultado_sao["df_grupo4"][["posicao_sao", "campo", "valor_cru", "valor", "unidade", "descricao"]])

    df_parametros_hf = extrair_parametros_hf(resultado_sao["df_grupo4"])

    print("\n=== PRINCIPAIS PARÂMETROS HF ===")
    print(df_parametros_hf)


if __name__ == "__main__":
    main()
