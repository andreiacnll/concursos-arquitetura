from app.dre import obter_pdf, extrair_texto_pdf, extrair_data_entrega_propostas

url = "https://files.diariodarepublica.pt/cp_hora/2026/07/138/419967796.pdf"

pdf = obter_pdf(url)

texto = extrair_texto_pdf(pdf)

resultado = extrair_data_entrega_propostas(texto)

print("DATA ENCONTRADA:")
print(resultado)
