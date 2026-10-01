import json
from tvDatafeed import TvDatafeed

tv = TvDatafeed()
for query in ["China PMI", "China Manufacturing PMI", "Caixin PMI", "China Caixin"]:
    print(f"--- search_symbol({query!r}) ---")
    try:
        results = tv.search_symbol(query, exchange="ECONOMICS")
        print(json.dumps(results, indent=2)[:4000])
    except Exception as e:
        print(f"FAIL -> {e!r}")
