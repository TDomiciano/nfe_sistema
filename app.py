import os
import re
from pypdf import PdfReader
import pandas as pd

def extrair_todos_dados_relatorio(caminho_pdf):
    lista_clientes = []
    # Expressão regular precisa para identificar CPFs e CNPJs ao longo do texto
    padrao_doc = r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})"
    nome_arquivo = os.path.basename(caminho_pdf)

    try:
        reader = PdfReader(caminho_pdf)
        total_paginas = len(reader.pages)
        print(f"Lendo {nome_arquivo} ({total_paginas} páginas)... Aguarde o processamento.")

        for num_pag, pagina in enumerate(reader.pages):
            texto = pagina.extract_text()
            if not texto:
                continue

            # Divide o texto por quebras de linha puras do sistema
            linhas = texto.split("\n")
            for linha in linhas:
                match_doc = re.search(padrao_doc, linha)
                
                if match_doc:
                    documento = match_doc.group(0)
                    
                    # Separa o texto dividindo a linha de forma segura
                    partes = linha.split(documento)
                    parte_anterior = partes[0].strip() if partes else ""
                    
                    # Limpa os códigos numéricos iniciais do cliente (ex: "19438 - ")
                    razao_social = re.sub(r"^\d+\s*-\s*", "", parte_anterior).strip()
                    
                    # Remove resíduos textuais de cabeçalhos repetidos
                    razao_social = re.sub(r"^(CLIENTE|CPF/CNPJ|VENDEDOR|ÁREA)\s*:?", "", razao_social, flags=re.IGNORECASE).strip()
                    
                    # Valida se é um cliente real e adiciona na listagem
                    if razao_social and len(razao_social) > 2 and not razao_social.upper().startswith("PÁGINA"):
                        lista_clientes.append({
                            "Arquivo": nome_arquivo,
                            "Página": num_pag + 1,
                            "Documento (CPF/CNPJ)": documento,
                            "Razão Social": razao_social
                        })
                        
    except Exception as e:
        print(f"Erro ao processar o arquivo {nome_arquivo}: {e}")
        
    return lista_clientes

def iniciar_processamento(pasta_origem, planilha_saida="resultado_extracao.xlsx"):
    todos_os_dados = []
    
    if not os.path.exists(pasta_origem):
        print(f"A pasta '{pasta_origem}' não foi localizada.")
        return
        
    arquivos = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.pdf')]
    if not arquivos:
        print("Nenhum arquivo PDF encontrado na pasta informada.")
        return

    for arquivo in arquivos:
        caminho_completo = os.path.join(pasta_origem, arquivo)
        dados_extraidos = extrair_todos_dados_relatorio(caminho_completo)
        todos_os_dados.extend(dados_extraidos)

    if todos_os_dados:
        df = pd.DataFrame(todos_os_dados)
        df = df[["Arquivo", "Página", "Documento (CPF/CNPJ)", "Razão Social"]]
        
        # Elimina duplicados de quebra de página
        df.drop_duplicates(subset=["Documento (CPF/CNPJ)"], keep="first", inplace=True)
        
        df.to_excel(planilha_saida, index=False)
        print(f"\nSucesso total! Foram extraídos {len(df)} clientes únicos.")
        print(f"Planilha salva com sucesso na sua pasta TESTE!")
    else:
        print("\nNenhum cliente ou documento foi identificado no relatório.")

PASTA_DOCUMENTOS = "./documentos_fiscais"
iniciar_processamento(PASTA_DOCUMENTOS)
