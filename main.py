def validar_tweet(texto):
    if not texto: return False
    texto_limpo = texto.lower()
    
    # 1. LISTA NEGRA (Apenas o que realmente é lixo)
    # Removi 'likes' e 'rt' porque os analistas pedem isso no mesmo post da pick
    palavras_proibidas = ['recap', 'cash', 'green', 'deposit', 'sign up', 'bonus', 'vip', 'giveaway']
    emojis_resultado = ['✅', '❌', '💰']
    
    if any(p in texto_limpo for p in palavras_proibidas) or any(e in texto for e in emojis_resultado):
        return False

    # 2. LISTA BRANCA EXPANDIDA (Para pegar REB+AST, Points, etc.)
    # Adicionei suporte a REB+AST, PTS+REB, e variações
    filtro_esportes = r'(nba|playoff|nfl|mlb|basketball)'
    filtro_stats = r'(over|under|o\d|u\d|pra|pts|points|reb|rebounds|ast|assists|3pm|3pa|ra|pr|pa|reb\+ast|pts\+reb|pts\+ast)'
    
    tem_esporte = bool(re.search(filtro_esportes, texto_limpo))
    tem_stat = bool(re.search(filtro_stats, texto_limpo))
    
    if not (tem_esporte and tem_stat):
        # Log para você ver no Render o que ele está lendo e recusando
        logger.info(f"🔍 Analisando: {texto[:40]}... | Esporte: {tem_esporte} | Stat: {tem_stat}")
        
    return tem_esporte and tem_stat

def extrair_apenas_aposta(texto):
    """
    Tenta pegar a linha da aposta. Se o tweet for curto (como os dos prints), 
    manda o texto quase todo para não perder o nome do jogador.
    """
    linhas = texto.split('\n')
    aposta_isolada = []
    
    # Filtro de busca de linha
    termos_chave = r'(over|under|o\d|u\d|pra|pts|points|reb|ast|3pm|ra|pr|pa|\+)'
    
    for linha in linhas:
        # Se a linha tem um número e um termo de aposta
        if re.search(r'\d', linha) and re.search(termos_chave, linha.lower()):
            # Ignora linhas que são apenas propaganda (links)
            if "http" not in linha.lower():
                aposta_isolada.append(linha.strip())
            
    if aposta_isolada:
        return "\n".join(aposta_isolada)
    return texto.strip()