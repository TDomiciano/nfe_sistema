import streamlit as st
from supabase import create_client


@st.cache_resource
def conectar_supabase():

    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(
        url,
        key
    )


def testar_supabase():

    supabase = conectar_supabase()

    resposta = (
        supabase
        .table("vendas_historico")
        .select("*")
        .limit(1)
        .execute()
    )

    return resposta.data


def salvar_vendas_historico(df):

    if df is None or df.empty:
        return 0

    supabase = conectar_supabase()

    registros = []

    for _, linha in df.iterrows():

        status = str(
            linha.get("Status", "")
        ).strip().upper()

        if status != "AUTORIZADA":
            continue

        cfop = str(
            linha.get("CFOP", "")
        ).strip()

        # Não salva devoluções como venda original
        if cfop in {
            "1201", "1202",
            "1410", "1411",
            "2201", "2202",
            "2410", "2411"
        }:
            continue

        numero_item = linha.get(
            "NUMERO ITEM",
            0
        )

        try:
            numero_item = int(numero_item)
        except:
            numero_item = 0

        registro = {

            "chave": str(
                linha.get("Chave", "")
            ).strip(),

            "nf": str(
                linha.get("NF", "")
            ).strip(),

            "serie": str(
                linha.get("SERIE", "")
            ).strip(),

            "emissao": (
                str(
                    linha.get("EMISSÃO", "")
                ).strip()
                or None
            ),

            "cpf_cnpj": str(
                linha.get("CPF/CNPJ", "")
            ).strip(),

            "razao_social": str(
                linha.get("RAZÃO SOCIAL", "")
            ).strip(),

            "uf_destino": str(
                linha.get("UF Destino", "")
            ).strip(),

            "numero_item": numero_item,

            "codigo_produto": str(
                linha.get("CÓDIGO DO PRODUTO", "")
            ).strip(),

            "produto": str(
                linha.get("PRODUTO", "")
            ).strip(),

            "ncm": str(
                linha.get("NCM", "")
            ).strip(),

            "cfop": cfop,

            "valor_produto": float(
                linha.get(
                    "VALOR DO PRODUTO",
                    0
                ) or 0
            ),

            "desconto": float(
                linha.get(
                    "DESCONTO",
                    0
                ) or 0
            ),

            "base_icms": float(
                linha.get(
                    "BASE ICMS",
                    0
                ) or 0
            ),

            "icms": float(
                linha.get(
                    "ICMS",
                    0
                ) or 0
            ),

            "difal": float(
                linha.get(
                    "DIFAL XML",
                    0
                ) or 0
            ),

            "fcp": float(
                linha.get(
                    "FCP XML",
                    0
                ) or 0
            ),

            "ibs": float(
                linha.get(
                    "IBS",
                    0
                ) or 0
            ),

            "cbs": float(
                linha.get(
                    "CBS",
                    0
                ) or 0
            )
        }

        if registro["chave"]:
            registros.append(registro)

    if not registros:
        return 0

    resposta = (
        supabase
        .table("vendas_historico")
        .upsert(
            registros,
            on_conflict="chave,numero_item"
        )
        .execute()
    )

    return len(resposta.data or [])

def buscar_venda_historico(chave):

    if not chave:
        return []

    supabase = conectar_supabase()

    resposta = (
        supabase
        .table("vendas_historico")
        .select("*")
        .eq(
            "chave",
            str(chave).strip()
        )
        .execute()
    )

    return resposta.data

def buscar_vendas_historico_lote(chaves):

    if not chaves:
        return[]

    chaves = list({
        str(chave).strip()
        for chave in chaves
        if chave and str(chave).strip()
    })

    if not chaves:
        return[]

    supabase = conectar_supabase()

    resposta = (
        supabase
        .table("vendas_historico")
        .select("*")
        .in_("chave", chaves)
        .execute()
    )

    return resposta.data or []