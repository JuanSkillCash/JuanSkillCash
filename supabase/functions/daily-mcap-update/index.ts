// Se ejecuta una vez al día vía pg_cron (ver supabase/daily-mcap-cron.sql). Trae datos públicos
// y gratuitos de CoinGecko (sin API key), calcula TOTAL2/TOTAL3/OTHERS/dominancias, y los guarda
// en mcap_index_history. No depende de que nadie abra la página — corre en la infraestructura de
// Supabase, no en el navegador de un visitante ni en ningún proceso de Claude.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CG_BASE = "https://api.coingecko.com/api/v3";

async function cgFetch(path: string) {
  const res = await fetch(`${CG_BASE}${path}`);
  if (!res.ok) throw new Error(`CoinGecko ${path} -> HTTP ${res.status}`);
  return res.json();
}

Deno.serve(async (_req) => {
  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const global = await cgFetch("/global");
    const total = global.data.total_market_cap.usd;

    // BTC, ETH, USDT y USDC por id exacto (no por posición) para que no falle si el orden cambia
    const pinned = await cgFetch(
      "/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,tether,usd-coin&order=market_cap_desc&sparkline=false",
    );
    const btcRow = pinned.find((c: any) => c.id === "bitcoin");
    const ethRow = pinned.find((c: any) => c.id === "ethereum");
    const usdtRow = pinned.find((c: any) => c.id === "tether");
    const usdcRow = pinned.find((c: any) => c.id === "usd-coin");
    if (!btcRow || !ethRow) throw new Error("CoinGecko no devolvió bitcoin/ethereum");

    // top 10 por capitalización real (igual a como TradingView define OTHERS = todo menos el top 10)
    const top10 = await cgFetch(
      "/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false",
    );
    const top10Sum = top10.reduce((sum: number, c: any) => sum + (c.market_cap || 0), 0);

    const btc = btcRow.market_cap;
    const eth = ethRow.market_cap;
    const usdt = usdtRow ? usdtRow.market_cap : null;
    const usdc = usdcRow ? usdcRow.market_cap : null;
    const total2 = total - btc;
    const total3 = total2 - eth;
    const others = total - top10Sum;
    const btcD = (btc / total) * 100;
    const ethD = (eth / total) * 100;
    const usdtD = usdt != null ? (usdt / total) * 100 : null;
    const usdcD = usdc != null ? (usdc / total) * 100 : null;

    // se corre a las 23:55 UTC — la foto de ese momento se guarda como el cierre del día en curso
    const day = new Date().toISOString().slice(0, 10);
    const rows = [
      { index_name: "TOTAL", day, value: total, source: "coingecko" },
      { index_name: "TOTAL2", day, value: total2, source: "coingecko" },
      { index_name: "TOTAL3", day, value: total3, source: "coingecko" },
      { index_name: "OTHERS", day, value: others, source: "coingecko" },
      { index_name: "BTC", day, value: btc, source: "coingecko" },
      { index_name: "ETH", day, value: eth, source: "coingecko" },
      { index_name: "BTC.D", day, value: btcD, source: "coingecko" },
      { index_name: "ETH.D", day, value: ethD, source: "coingecko" },
    ];
    if (usdtD != null) rows.push({ index_name: "USDT.D", day, value: usdtD, source: "coingecko" });
    if (usdcD != null) rows.push({ index_name: "USDC.D", day, value: usdcD, source: "coingecko" });

    const { error } = await supabase
      .from("mcap_index_history")
      .upsert(rows, { onConflict: "index_name,day", ignoreDuplicates: true });
    if (error) throw error;

    return new Response(JSON.stringify({ ok: true, day, rows: rows.length }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: String(err) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
