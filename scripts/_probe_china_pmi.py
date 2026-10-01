from tvDatafeed import TvDatafeed, Interval

tv = TvDatafeed()
candidates = [
    ("ECONOMICS", "CNNPMI"),
    ("ECONOMICS", "CNPMIM"),
    ("ECONOMICS", "CHNPMIM"),
    ("ECONOMICS", "CNMPMI"),
    ("ECONOMICS", "CNCPMIM"),
    ("ECONOMICS", "CNBPMIM"),
    ("ECONOMICS", "CHPMIM"),
]
for exch, sym in candidates:
    try:
        df = tv.get_hist(symbol=sym, exchange=exch, interval=Interval.in_daily, n_bars=5)
        if df is not None and not df.empty:
            print(f"OK {exch}:{sym} -> last close(s): {df['close'].tail(3).tolist()}")
        else:
            print(f"EMPTY {exch}:{sym}")
    except Exception as e:
        print(f"FAIL {exch}:{sym} -> {e!r}")
