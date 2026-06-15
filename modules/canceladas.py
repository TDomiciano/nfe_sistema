import xml.etree.ElementTree as ET
from modules.xml_utils import get_text


def localizar_canceladas(arquivos, ns):

    chaves_canceladas = set()

    for arq in arquivos:

        try:
            arq.seek(0)
            tree = ET.parse(arq)
            root = tree.getroot()

            inf_evento = root.find(".//nfe:infEvento", ns)

            if inf_evento is None:
                continue

            tp_evento = (
                get_text(inf_evento, "nfe:tpEvento", ns) or ""
            ).strip()

            chave = (
                get_text(inf_evento, "nfe:chNFe", ns) or ""
            ).strip()

            print("TP EVENTO:", tp_evento)
            print("CHAVE EVENTO:", chave)

            if tp_evento == "110111" and chave:

                print("ADICIONOU CANCELADA:", chave)

                chaves_canceladas.add(chave)

        except Exception as e:

            print("ERRO CANCELADAS:", e)

    print("SET FINAL:", chaves_canceladas)

    return chaves_canceladas