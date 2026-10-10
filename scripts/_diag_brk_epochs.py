"""
Script de diagnostico TEMPORAL (no se agrega al workflow diario) - solo para confirmar, desde
un entorno con internet real (GitHub Actions), si bitview.space/Bitcoin Research Kit expone de
verdad las series epoch_N_supply / epoch_N_supply_in_loss / epoch_N_supply_in_profit que aparecen
en su codigo fuente (bitview_client/__init__.py). Se borra despues de usarlo.
"""
import json
import requests


def fetch(series_id):
    url = f"https://bitview.space/api/series/{series_id}/day1"
    r = requests.get(url, timeout=30)
    return r.status_code, r


def main():
    ids = []
    for n in range(5):
        ids.append(f"epoch_{n}_supply")
        ids.append(f"epoch_{n}_supply_in_loss")
        ids.append(f"epoch_{n}_supply_in_profit")

    results = {}
    for sid in ids:
        try:
            status, r = fetch(sid)
            if status == 200:
                data = r.json().get("data", [])
                non_null = [v for v in data if v is not None]
                last_val = non_null[-1] if non_null else None
                results[sid] = {"status": status, "len": len(data), "non_null": len(non_null), "last": last_val}
            else:
                results[sid] = {"status": status, "body": r.text[:200]}
        except Exception as e:
            results[sid] = {"error": str(e)}

    print("DIAG_RESULT_START")
    print(json.dumps(results, indent=2))
    print("DIAG_RESULT_END")


if __name__ == "__main__":
    main()
