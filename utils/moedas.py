PREMIO_REAIS = 330
TOTAL_JOGADORES = 40
MOEDAS_POR_JOGADOR = 100

TOTAL_MOEDAS_SISTEMA = TOTAL_JOGADORES * MOEDAS_POR_JOGADOR

def calcular_valor_moeda():
    return PREMIO_REAIS / TOTAL_MOEDAS_SISTEMA

def calcular_valor_pix(moedas_gastas):
    valor_por_moeda = calcular_valor_moeda()
    return round(moedas_gastas * valor_por_moeda, 2)
