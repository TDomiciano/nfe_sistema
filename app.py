import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

# =========================
# CONFIG PAGINA
# =========================
st.set_page_config(layout="wide")

# =========================
# CSS
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)

# =========================
# TITULO
# =========================
st.title("📄 Leitor Fiscal NF-e")

st.info(
    "⚠️ O sistema suporta XML e ZIP contendo XMLs."
)

# =========================
# NAMESPACE XML
# =========================
ns = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

# =========================
# CARREGA REGRAS
# =========================
@st.cache_data
def carregar_regras():

    regras = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config Fiscal"
    )

    regras_st = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config ST"
    )

    # =========================
    # TABELA ICMS
    # =========================
    try:

        tabela_icms = pd.read_excel(
            "aliquotas.xlsx"
        )

        # primeira coluna vira indice
        tabela_icms = tabela_icms.set_index(
            tabela_icms.columns[0]
        )

        # limpa colunas
        tabela_icms.columns = (
            tabela_icms.columns
            .astype(str)
            .str.upper()
            .str.strip()
        )

        # limpa index
        tabela_icms.index = (
            tabela_icms.index
            .astype(str)
            .str.upper()
            .str.strip()
        )

        # converte tudo para numero
        tabela_icms = tabela_icms.apply(
            pd.to_numeric,
            errors="coerce"
        )

    except Exception as e:

        st.error(
            f"Erro ao carregar aliquotas.xlsx: {e}"
        )

        st.stop()

    regras_dict = {}
    regras_st_dict = {}

    # =========================
    # REGRAS FISCAIS
    # =========================
    for _, row in regras.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_dict[chave] = row.to_dict()

    # =========================
    # REGRAS ST
    # =========================
    for _, row in regras_st.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_st_dict[chave] = row.to_dict()

    return regras_dict, regras_st_dict, tabela_icms


regras_dict, regras_st_dict, tabela_icms = carregar_regras()

# =========================
# DEBUG TABELA
# =========================
st.write(tabela_icms)

# =========================
# FUNÇÃO SEGURA XML
# =========================
def txt(elemento, tag):

    if elemento is None:
        return ""

    achou = elemento.find(tag, ns)

    return achou.text if achou is not None else ""


# =========================
# BUSCA REGRA
# =========================
def buscar_regra(dicionario, ncm, origem, destino):

    chave = (
        str(ncm).replace(".0", "").strip(),
        str(origem).upper().strip(),
        str(destino).upper().strip()
    )

    return dicionario.get(chave)

# =========================
# BUSCA ALIQUOTAS
# =========================
def buscar_aliquotas(origem, destino):

    try:

        origem = str(origem).upper().strip()
        destino = str(destino).upper().strip()

        aliq_inter = float(
            tabela_icms.loc[origem, destino]
        )

        aliq_interna = float(
            tabela_icms.loc[destino, destino]
        )

        return aliq_inter, aliq_interna

    except Exception as e:

        st.error(
            f"Erro aliquota {origem}->{destino}: {e}"
        )

        return 0, 0


# =========================
# UPLOAD
# =========================
arquivos = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

# =========================
# LISTA XMLS
# =========================
xmls = []

if arquivos:

    for arq in arquivos:

        # XML
        if arq.name.lower().endswith(".xml"):

            xmls.append(arq)

        # ZIP
        elif arq.name.lower().endswith(".zip"):

            try:

                zip_file = zipfile.ZipFile(arq)

                for nome in zip_file.namelist():

                    if nome.lower().endswith(".xml"):

                        xml_bytes = zip_file.read(nome)

                        xmls.append(
                            io.BytesIO(xml_bytes)
                        )

            except Exception as e:

                st.error(
                    f"Erro ao abrir ZIP {arq.name}: {e}"
                )

# =========================
# PROCESSAMENTO
# =========================
dados = []

canceladas = set()

if xmls:

    total = len(xmls)

    st.success(
        f"📦 {total} XMLs encontrados"
    )

    barra = st.progress(0)

    # =========================
    # PROCESSA XML
    # =========================
    for i, arq in enumerate(xmls):

        try:

            arq.seek(0)

            conteudo = arq.read()

            root = ET.fromstring(conteudo)

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            emit_end = (
                emit.find('nfe:enderEmit', ns)
                if emit is not None
                else None
            )

            dest_end = (
                dest.find('nfe:enderDest', ns)
                if dest is not None
                else None
            )

            uf_origem = txt(
                emit_end,
                'nfe:UF'
            )

            uf_destino = txt(
                dest_end,
                'nfe:UF'
            )

            itens = root.findall(
                './/nfe:det',
                ns
            )

            for item in itens:

                prod = item.find(
                    'nfe:prod',
                    ns
                )

                imposto = item.find(
                    'nfe:imposto',
                    ns
                )

                # =========================
                # DIFAL XML
                # =========================
                icmsufdest = (
                    imposto.find(
                        './/nfe:ICMSUFDest',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                try:

                    difal_xml = float(
                        txt(icmsufdest, 'nfe:vICMSUFDest') or 0
                    )

                except:

                    difal_xml = 0

                # =========================
                # DIFAL CALCULADO
                # =========================
                difal_calculado = 0

                try:

                    aliq_inter, aliq_interna = buscar_aliquotas(
                        uf_origem,
                        uf_destino
                    )

                    base = float(
                        txt(prod, 'nfe:vProd') or 0
                    )

                    aliq_inter = aliq_inter / 100
                    aliq_interna = aliq_interna / 100

                    if aliq_interna > aliq_inter:

                        difal_calculado = round(
                            (
                                base *
                                (
                                    aliq_interna - aliq_inter
                                )
                            )
                            /
                            (
                                1 - aliq_interna
                            ),
                            2
                        )

                except Exception as e:

                    st.error(
                        f"Erro calculo DIFAL: {e}"
                    )

                # =========================
                # DIVERGENCIAS
                # =========================
                divergencias = []

                diferenca = abs(
                    difal_xml - difal_calculado
                )

                if diferenca > 1:

                    divergencias.append(
                        f"DIFAL XML ({difal_xml}) diferente do calculado ({difal_calculado})"
                    )

                # =========================
                # DADOS
                # =========================
                dados.append({

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Produto": txt(
                        prod,
                        'nfe:xProd'
                    ),

                    "Valor Produto": float(
                        txt(prod, 'nfe:vProd') or 0
                    ),

                    "Aliquota Interna": aliq_interna * 100,

                    "Aliquota Interestadual": aliq_inter * 100,

                    "DIFAL XML": difal_xml,

                    "DIFAL Calculado": difal_calculado,

                    "Validacao": (
                        "OK"
                        if len(divergencias) == 0
                        else "DIVERGENTE"
                    ),

                    "Divergencias": (
                        " | ".join(divergencias)
                    )

                })

            barra.progress((i + 1) / total)

        except Exception as e:

            st.error(
                f"Erro no arquivo: {e}"
            )

# =========================
# RESULTADO
# =========================
if dados:

    df = pd.DataFrame(dados)

    st.success(
        f"✅ {len(df)} registros processados"
    )

    csv = df.to_csv(
        index=False,
        sep=";"
    ).encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar CSV",
        csv,
        "relatorio_fiscal.csv",
        "text/csv"
    )

    st.dataframe(df)

else:

    st.info(
        "Envie XMLs ou ZIPs para iniciar."
    )