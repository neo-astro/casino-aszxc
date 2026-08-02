import json
import time
import os
import re
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from database import init_db, save_spin, save_game_metrics

TARGET_URL = "https://casino.virtualsoft.tech/game/play/?gameid=126271&mode=real&provider=SMARTSOFT&lan=es&partnerid=8&token=0P5290870Pmmfuf130ghpkoup8kln7&balance=0&currency=USD&userid=5230783&isMobile=false"

def extract_game_info_from_url(url):
    """Extrae el game_id y provider de la URL para aislar datos de juegos distintos."""
    try:
        parsed_url = urlparse(url)
        params = parse_qs(parsed_url.query)
        game_id = params.get("gameid", ["126271"])[0]
        provider = params.get("provider", ["SMARTSOFT"])[0]
        return game_id, provider
    except Exception:
        return "126271", "SMARTSOFT"

def extract_numeric_value(element):
    """Auxiliar para extraer un valor numérico flotante de un elemento HTML."""
    if not element:
        return 0.0
    text = element.text.replace("--", "").strip()
    match = re.search(r"[\d\.]+", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0
    return 0.0

def parse_html_fragment(html_string, game_id="126271", provider="SMARTSOFT"):
    """
    Parsea el HTML asociando estrictamente el marcador y las métricas
    de apuestas al HASH ÚNICO del juego actual para evitar mezclas entre rondas.
    """
    soup = BeautifulSoup(html_string, "html.parser")
    spins_data = []
    current_hash = None
    latest_valid_hash = None
    
    # 1. Extraer historial de giros / spins en #last100Spins
    history_container = soup.find(id="last100Spins") or soup.find("div", class_="history")
    if history_container:
        rows = history_container.find_all("div", class_="row")
        for row in rows:
            data_info_raw = row.get("data-info")
            if not data_info_raw:
                continue
                
            try:
                info_json = json.loads(data_info_raw)
                is_current = "current" in row.get("class", [])
                info_json["is_current"] = is_current
                info_json["game_id"] = game_id
                info_json["provider"] = provider
                
                spin_hash = info_json.get("SpinHash")
                if is_current:
                    current_hash = spin_hash
                elif not latest_valid_hash and spin_hash and spin_hash != "loading":
                    latest_valid_hash = spin_hash
                    
                spins_data.append(info_json)
            except json.JSONDecodeError as e:
                print(f"Error decodificando data-info: {e}")

    # Determinar el hash al que corresponden las apuestas actuales de la partida
    active_spin_hash = current_hash if (current_hash and current_hash != "loading") else latest_valid_hash
    if not active_spin_hash:
        active_spin_hash = "PENDIENTE"
                
    # 2. Extraer métricas de la mesa de apuestas (#playersActive, #playersCashOut)
    players_active_count = 0
    players_win_count = 0
    total_bet_amount = 0.0
    players_cashout_total = 0.0
    
    players_container = soup.find(id="players") or soup.select_one(".info-content.bets")
    
    if players_container:
        # A) Apuestas activas (#playersActive) -> col2: Monto
        players_active_div = players_container.find(id="playersActive")
        if players_active_div:
            active_rows = players_active_div.find_all("div", class_="row")
            for r in active_rows:
                players_active_count += 1
                col_monto = r.find("div", class_="col2")
                total_bet_amount += extract_numeric_value(col_monto)

        # B) Jugadores que cobraron (#playersCashOut) -> col2: Monto, col4: Ganancia
        players_cashout_div = players_container.find(id="playersCashOut")
        if players_cashout_div:
            cashout_rows = players_cashout_div.find_all("div", class_="row")
            for r in cashout_rows:
                players_active_count += 1
                col_monto = r.find("div", class_="col2")
                col_ganancia = r.find("div", class_="col4")
                
                monto = extract_numeric_value(col_monto)
                ganancia = extract_numeric_value(col_ganancia)
                
                total_bet_amount += monto
                players_cashout_total += ganancia
                if ganancia > 0 or "win" in r.get("class", []):
                    players_win_count += 1
    else:
        # Fallback de respaldo
        all_rows = soup.select(".info-content.bets .row, #players .row")
        for r in all_rows:
            col_monto = r.find("div", class_="col2")
            col_ganancia = r.find("div", class_="col4")
            if col_monto:
                players_active_count += 1
                total_bet_amount += extract_numeric_value(col_monto)
            if col_ganancia:
                ganancia = extract_numeric_value(col_ganancia)
                players_cashout_total += ganancia
                if ganancia > 0:
                    players_win_count += 1
                    
    return {
        "spins": spins_data,
        "active_spin_hash": active_spin_hash,
        "metrics": {
            "spin_hash": active_spin_hash,
            "game_id": game_id,
            "provider": provider,
            "players_active": players_active_count,
            "players_win_count": players_win_count,
            "total_bet_amount": total_bet_amount,
            "players_cashout_total": players_cashout_total
        }
    }

def process_and_save_data(parsed_result):
    """Guarda o actualiza las métricas y spins en la base de datos sin duplicaciones."""
    spins = parsed_result.get("spins", [])
    metrics = parsed_result.get("metrics", {})
    
    saved_count = 0
    for spin in spins:
        spin_hash = spin.get("SpinHash")
        if spin_hash and spin_hash != "loading":
            if save_spin(spin):
                saved_count += 1
                
    if metrics.get("spin_hash") and metrics.get("spin_hash") not in ["loading", "PENDIENTE"]:
        save_game_metrics(metrics)
        
    return saved_count

def run_live_scraper(url=TARGET_URL, headless=True, interval_seconds=3):
    """Ejecuta el scraper en vivo mostrando el HASH exacto en cada log de consola."""
    init_db()
    game_id, provider = extract_game_info_from_url(url)
    print(f"Iniciando scraper en vivo para Game ID: {game_id} | Proveedor: {provider}")
    print(f"URL: {url}\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Navegando a la página (continuando...): {e}")
            
        print("Página cargada. Monitoreando en tiempo real con aislamiento por HASH...\n")
        
        try:
            while True:
                content = page.content()
                frames = page.frames
                combined_content = content
                for frame in frames:
                    try:
                        combined_content += "\n" + frame.content()
                    except Exception:
                        pass
                        
                parsed = parse_html_fragment(combined_content, game_id=game_id, provider=provider)
                saved = process_and_save_data(parsed)
                
                m = parsed["metrics"]
                active_hash = parsed.get("active_spin_hash", "PENDIENTE")
                hash_short = active_hash[:16] + "..." if len(active_hash) > 16 else active_hash
                
                timestamp = time.strftime('%H:%M:%S')
                print(f"[{timestamp}] [Hash: {hash_short}] Jugadores: {m['players_active']:<3} | Ingresado: ${m['total_bet_amount']:>7.2f} | Ganadores: {m['players_win_count']:<3} | Total Cobrado: ${m['players_cashout_total']:>7.2f}")
                
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nScraper detenido por el usuario.")
        finally:
            browser.close()

if __name__ == "__main__":
    import sys
    init_db()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        headless_mode = "--show" not in sys.argv
        run_live_scraper(headless=headless_mode)
    else:
        print("Modo de prueba de fragmento HTML:")
        sample_fragment = '''
        <aside id="left">
            <div class="history" id="last100Spins">
                <div id="loading"
                    data-info="{&quot;SpinTime&quot;:&quot;JUEGO ACTUAL&quot;,&quot;Coefficient&quot;:&quot;EN JUEGO&quot;,&quot;SpinHash&quot;:&quot;loading&quot;,&quot;Info&quot;:&quot;ESPERANDO&quot;}"
                    class="row current" data-attr="hash current"><span class="history-logo"></span></div>
                <div id="6692A05360517E5503B1F009AFD1360FC722EA1D65C54C3645A767A11D526161"
                    data-info="{&quot;Coefficient&quot;:2.45,&quot;SpinHash&quot;:&quot;6692A05360517E5503B1F009AFD1360FC722EA1D65C54C3645A767A11D526161&quot;,&quot;Info&quot;:&quot;2.45_ec242d0c-16fe-4c9d-84c1-357d22b53f65&quot;,&quot;SpinTime&quot;:&quot;2026-08-02T17:02:07.9894165+02:00&quot;}"
                    class="row win" data-attr="hash open">2.45<span class="coef">x</span></div>
            </div>
        </aside>
        <div class="info-content bets active">
            <div class="head">
                <div class="col1"><div>Usuario</div></div>
                <div class="col2">Monto</div>
                <div class="col3">Cobro</div>
                <div class="col4">Ganancia</div>
            </div>
            <div class="list" id="players">
                <div>
                    <div id="playersActive">
                        <div class="row">
                            <div class="col1"><div>B****7</div></div>
                            <div class="col2">19.70<span class="currency">USD</span></div>
                            <div class="col3">--</div>
                            <div class="col4">--</div>
                        </div>
                    </div>
                    <div id="playersCashOut">
                        <div class="row win">
                            <div class="col1"><div>d****7</div></div>
                            <div class="col2">0.10<span class="currency">USD</span></div>
                            <div class="col3">2.04<span class="coef">x</span></div>
                            <div class="col4">0.20<span class="currency">USD</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        '''
        res = parse_html_fragment(sample_fragment)
        saved = process_and_save_data(res)
        print("Resultado del parseo de prueba:")
        print(json.dumps(res, indent=2))
        print(f"Registros guardados en DB: {saved}")
