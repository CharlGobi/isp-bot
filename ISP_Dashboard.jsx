import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell
} from "recharts";

// ─── DESIGN TOKENS ──────────────────────────────────────────
const C = {
  bg:       "#05060A",
  surface:  "#0C0E14",
  card:     "#10131C",
  border:   "#1C2030",
  borderBright: "#2A3050",
  green:    "#00E676",
  greenDim: "#00A854",
  red:      "#FF3D57",
  redDim:   "#CC2040",
  blue:     "#29B6F6",
  blueDim:  "#1A7FA8",
  yellow:   "#FFD740",
  purple:   "#9C6EFA",
  text:     "#D0D8F0",
  textDim:  "#7080A0",
  textMuted:"#404860",
};

// ─── SAMPLE DATA ────────────────────────────────────────────
const SAMPLE_TRADES = [
  { date:"2026-04-01",time:"08:23",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.08342,sl:1.08192,tp1:1.08492,tp2:1.08642,score:8.0,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-01",exitTime:"09:15",exit:1.08498,pips:15.6,profit:7.80,dailyDD:0.0,maxDD:0.0,riskUsed:8,result:"WIN",reason:"TP1 Hit",consec:0,balance:10007.80,equity:10007.80 },
  { date:"2026-04-01",time:"09:45",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.08510,sl:1.08360,tp1:1.08660,tp2:1.08810,score:7.5,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-01",exitTime:"10:32",exit:1.08650,pips:14.0,profit:7.00,dailyDD:0.0,maxDD:0.0,riskUsed:15,result:"WIN",reason:"TP1 Hit",consec:0,balance:10014.80,equity:10014.80 },
  { date:"2026-04-01",time:"13:15",symbol:"EURUSD",direction:"SELL",lots:0.05,entry:1.08620,sl:1.08770,tp1:1.08470,tp2:1.08320,score:6.0,regime:"RANGE",bias:"BEARISH",session:"NY",exitDate:"2026-04-01",exitTime:"13:58",exit:1.08770,pips:-15.0,profit:-7.50,dailyDD:0.7,maxDD:0.7,riskUsed:22,result:"LOSS",reason:"SL Hit",consec:1,balance:10007.30,equity:10007.30 },
  { date:"2026-04-01",time:"14:30",symbol:"EURUSD",direction:"SELL",lots:0.05,entry:1.08580,sl:1.08730,tp1:1.08430,tp2:1.08280,score:7.0,regime:"BEAR TREND",bias:"BEARISH",session:"NY",exitDate:"2026-04-01",exitTime:"15:42",exit:1.08430,pips:15.0,profit:7.50,dailyDD:0.7,maxDD:0.7,riskUsed:30,result:"WIN",reason:"TP1 Hit",consec:0,balance:10014.80,equity:10014.80 },
  { date:"2026-04-02",time:"08:12",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.08710,sl:1.08560,tp1:1.08860,tp2:1.09010,score:9.0,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-02",exitTime:"09:55",exit:1.09012,pips:30.2,profit:15.10,dailyDD:0.0,maxDD:0.0,riskUsed:10,result:"WIN",reason:"TP2 Trail",consec:0,balance:10029.90,equity:10029.90 },
  { date:"2026-04-02",time:"10:05",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.09020,sl:1.08870,tp1:1.09170,tp2:1.09320,score:6.5,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-02",exitTime:"10:51",exit:1.08870,pips:-15.0,profit:-7.50,dailyDD:0.7,maxDD:0.7,riskUsed:18,result:"LOSS",reason:"SL Hit",consec:1,balance:10022.40,equity:10022.40 },
  { date:"2026-04-02",time:"13:22",symbol:"GBPUSD",direction:"SELL",lots:0.04,entry:1.26540,sl:1.26690,tp1:1.26390,tp2:1.26240,score:8.5,regime:"BEAR TREND",bias:"BEARISH",session:"NY",exitDate:"2026-04-02",exitTime:"14:30",exit:1.26240,pips:30.0,profit:12.00,dailyDD:0.7,maxDD:0.7,riskUsed:28,result:"WIN",reason:"TP2 Trail",consec:0,balance:10034.40,equity:10034.40 },
  { date:"2026-04-03",time:"08:35",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.08850,sl:1.08700,tp1:1.09000,tp2:1.09150,score:7.0,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-03",exitTime:"09:20",exit:1.08700,pips:-15.0,profit:-7.50,dailyDD:0.7,maxDD:0.7,riskUsed:8,result:"LOSS",reason:"SL Hit",consec:1,balance:10026.90,equity:10026.90 },
  { date:"2026-04-03",time:"09:50",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.08720,sl:1.08570,tp1:1.08870,tp2:1.09020,score:8.0,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-03",exitTime:"10:55",exit:1.08870,pips:15.0,profit:7.50,dailyDD:0.7,maxDD:0.7,riskUsed:15,result:"WIN",reason:"TP1 Hit",consec:0,balance:10034.40,equity:10034.40 },
  { date:"2026-04-03",time:"13:10",symbol:"GBPUSD",direction:"BUY",lots:0.04,entry:1.26450,sl:1.26300,tp1:1.26600,tp2:1.26750,score:9.5,regime:"BULL TREND",bias:"BULLISH",session:"NY",exitDate:"2026-04-03",exitTime:"15:10",exit:1.26752,pips:30.2,profit:12.08,dailyDD:0.0,maxDD:0.0,riskUsed:25,result:"WIN",reason:"TP2 Trail",consec:0,balance:10046.48,equity:10046.48 },
  { date:"2026-04-04",time:"08:18",symbol:"EURUSD",direction:"SELL",lots:0.05,entry:1.09100,sl:1.09250,tp1:1.08950,tp2:1.08800,score:7.5,regime:"BEAR TREND",bias:"BEARISH",session:"London",exitDate:"2026-04-04",exitTime:"09:12",exit:1.08948,pips:15.2,profit:7.60,dailyDD:0.0,maxDD:0.0,riskUsed:8,result:"WIN",reason:"TP1 Hit",consec:0,balance:10054.08,equity:10054.08 },
  { date:"2026-04-04",time:"14:05",symbol:"USDJPY",direction:"BUY",lots:0.04,entry:149.820,sl:149.670,tp1:149.970,tp2:150.120,score:8.0,regime:"BULL TREND",bias:"BULLISH",session:"NY",exitDate:"2026-04-04",exitTime:"15:30",exit:150.122,pips:30.2,profit:9.65,dailyDD:0.0,maxDD:0.0,riskUsed:20,result:"WIN",reason:"TP2 Trail",consec:0,balance:10063.73,equity:10063.73 },
  { date:"2026-04-07",time:"08:45",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.09220,sl:1.09070,tp1:1.09370,tp2:1.09520,score:6.5,regime:"WEAK TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-07",exitTime:"09:30",exit:1.09070,pips:-15.0,profit:-7.50,dailyDD:0.7,maxDD:0.7,riskUsed:8,result:"LOSS",reason:"SL Hit",consec:1,balance:10056.23,equity:10056.23 },
  { date:"2026-04-07",time:"13:35",symbol:"GBPUSD",direction:"SELL",lots:0.04,entry:1.27100,sl:1.27250,tp1:1.26950,tp2:1.26800,score:8.5,regime:"BEAR TREND",bias:"BEARISH",session:"NY",exitDate:"2026-04-07",exitTime:"14:50",exit:1.26800,pips:30.0,profit:12.00,dailyDD:0.7,maxDD:0.7,riskUsed:22,result:"WIN",reason:"TP2 Trail",consec:0,balance:10068.23,equity:10068.23 },
  { date:"2026-04-08",time:"08:22",symbol:"EURUSD",direction:"BUY",lots:0.05,entry:1.09380,sl:1.09230,tp1:1.09530,tp2:1.09680,score:9.0,regime:"BULL TREND",bias:"BULLISH",session:"London",exitDate:"2026-04-08",exitTime:"09:45",exit:1.09532,pips:15.2,profit:7.60,dailyDD:0.0,maxDD:0.0,riskUsed:8,result:"WIN",reason:"TP1 Hit",consec:0,balance:10075.83,equity:10075.83 },
];

const buildEquityCurve = (trades) => {
  let balance = 10000;
  return [
    { date: "Start", balance: 10000, dd: 0 },
    ...trades.map(t => {
      balance += t.profit;
      return { date: t.date + " " + t.time, balance: +balance.toFixed(2), dd: +t.maxDD.toFixed(2), profit: t.profit };
    })
  ];
};

// ─── UTILS ──────────────────────────────────────────────────
const pct  = (v, d=1)  => (v >= 0 ? "+" : "") + v.toFixed(d) + "%";
const usd  = (v, d=2)  => (v >= 0 ? "+" : "-") + "$" + Math.abs(v).toFixed(d);
const pip  = (v, d=1)  => (v >= 0 ? "+" : "") + v.toFixed(d) + " p";
const num  = (v, d=1)  => v.toFixed(d);
const clr  = (v)       => v >= 0 ? C.green : C.red;

// ─── COMPONENTS ─────────────────────────────────────────────

function Glow({ color = C.green, size = 8, opacity = 0.6 }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size,
      borderRadius: "50%", background: color,
      boxShadow: `0 0 ${size}px ${color}`,
      opacity, flexShrink: 0
    }} />
  );
}

function StatCard({ label, value, sub, color = C.text, pulse = false }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: "14px 16px",
      display: "flex", flexDirection: "column", gap: 4
    }}>
      <span style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: "monospace" }}>{label}</span>
      <span style={{ fontSize: 22, fontWeight: 700, color, fontFamily: "monospace", letterSpacing: "-0.02em" }}>
        {value}
      </span>
      {sub && <span style={{ fontSize: 11, color: C.textDim, fontFamily: "monospace" }}>{sub}</span>}
    </div>
  );
}

function RiskGauge({ label, used, limit, color }) {
  const pct = Math.min((used / limit) * 100, 100);
  const barColor = pct > 75 ? C.red : pct > 50 ? C.yellow : color;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 10, color: C.textDim, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</span>
        <span style={{ fontSize: 12, color: barColor, fontFamily: "monospace", fontWeight: 700 }}>
          {used.toFixed(2)}% <span style={{ color: C.textMuted }}>/ {limit}%</span>
        </span>
      </div>
      <div style={{ height: 6, background: C.border, borderRadius: 3, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: `linear-gradient(90deg, ${barColor}88, ${barColor})`,
          borderRadius: 3, transition: "width 0.6s ease",
          boxShadow: `0 0 8px ${barColor}66`
        }} />
      </div>
    </div>
  );
}

function Badge({ text, color }) {
  return (
    <span style={{
      fontSize: 9, fontFamily: "monospace", fontWeight: 700,
      letterSpacing: "0.1em", textTransform: "uppercase",
      padding: "2px 7px", borderRadius: 3,
      background: color + "20", color, border: `1px solid ${color}40`
    }}>{text}</span>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.borderBright}`,
      borderRadius: 6, padding: "10px 14px", fontFamily: "monospace", fontSize: 12
    }}>
      <div style={{ color: C.textDim, marginBottom: 6, fontSize: 10 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.value >= 0 ? C.green : C.red }}>
          {p.name}: {typeof p.value === "number" ? (p.name === "balance" ? "$" + p.value.toFixed(2) : p.value.toFixed(2) + "%") : p.value}
        </div>
      ))}
    </div>
  );
};

// ─── MAIN DASHBOARD ─────────────────────────────────────────
export default function ISPDashboard() {
  const [trades, setTrades]         = useState(SAMPLE_TRADES);
  const [activeTab, setActiveTab]   = useState("overview");
  const [filterSym, setFilterSym]   = useState("ALL");
  const [filterRes, setFilterRes]   = useState("ALL");
  const [filterSess, setFilterSess] = useState("ALL");
  const [sortCol, setSortCol]       = useState("date");
  const [sortDir, setSortDir]       = useState("desc");
  const [demoMode, setDemoMode]     = useState(true);

  const equityCurve = buildEquityCurve(trades);

  // ── Derived stats ──
  const wins       = trades.filter(t => t.result === "WIN");
  const losses     = trades.filter(t => t.result === "LOSS");
  const totalProfit = trades.reduce((s, t) => s + t.profit, 0);
  const grossWin   = wins.reduce((s, t) => s + t.profit, 0);
  const grossLoss  = losses.reduce((s, t) => s + t.profit, 0);
  const pFactor    = grossLoss !== 0 ? (grossWin / Math.abs(grossLoss)) : 0;
  const winRate    = trades.length ? (wins.length / trades.length) * 100 : 0;
  const avgWin     = wins.length ? grossWin / wins.length : 0;
  const avgLoss    = losses.length ? Math.abs(grossLoss) / losses.length : 0;
  const avgRR      = avgLoss ? avgWin / avgLoss : 0;
  const avgScore   = trades.length ? trades.reduce((s, t) => s + t.score, 0) / trades.length : 0;
  const maxDD      = Math.max(...trades.map(t => t.maxDD), 0);
  const maxDailyDD = Math.max(...trades.map(t => t.dailyDD), 0);

  // Prop firm compliance
  const DAILY_LIMIT = 3.0, MAX_DD_LIMIT = 8.0;
  const latestTrade = trades[trades.length - 1];
  const currentDailyDD = latestTrade?.dailyDD || 0;
  const currentMaxDD   = latestTrade?.maxDD   || 0;
  const propStatus     = currentMaxDD >= MAX_DD_LIMIT ? "HALTED" :
                         currentDailyDD >= DAILY_LIMIT ? "DAILY LIMIT" :
                         currentMaxDD >= MAX_DD_LIMIT * 0.8 ? "WARNING" : "ACTIVE";

  // Session breakdown
  const londonTrades = trades.filter(t => t.session === "London");
  const nyTrades     = trades.filter(t => t.session === "NY");
  const lWR = londonTrades.length ? (londonTrades.filter(t => t.result==="WIN").length / londonTrades.length)*100 : 0;
  const nWR = nyTrades.length     ? (nyTrades.filter(t => t.result==="WIN").length     / nyTrades.length)*100     : 0;
  const lPnL = londonTrades.reduce((s, t) => s + t.profit, 0);
  const nPnL = nyTrades.reduce((s, t) => s + t.profit, 0);

  // Regime breakdown
  const regimes = ["BULL TREND","BEAR TREND","WEAK TREND","RANGE"];
  const regimeStats = regimes.map(r => {
    const rt = trades.filter(t => t.regime === r);
    const rw = rt.filter(t => t.result === "WIN");
    return { name: r, count: rt.length, wr: rt.length ? (rw.length/rt.length)*100 : 0, pnl: rt.reduce((s,t)=>s+t.profit,0) };
  }).filter(r => r.count > 0);

  // Score distribution
  const scoreBins = [
    { range: "5-6", trades: trades.filter(t=>t.score>=5&&t.score<6.5) },
    { range: "6.5-7.5", trades: trades.filter(t=>t.score>=6.5&&t.score<7.5) },
    { range: "7.5-8.5", trades: trades.filter(t=>t.score>=7.5&&t.score<8.5) },
    { range: "8.5-10", trades: trades.filter(t=>t.score>=8.5) },
  ].map(b => ({
    range: b.range,
    count: b.trades.length,
    wr: b.trades.length ? (b.trades.filter(t=>t.result==="WIN").length/b.trades.length)*100 : 0
  }));

  // Daily P&L bars
  const dailyPnL = Object.entries(
    trades.reduce((acc, t) => {
      acc[t.date] = (acc[t.date] || 0) + t.profit;
      return acc;
    }, {})
  ).map(([date, pnl]) => ({ date: date.slice(5), pnl: +pnl.toFixed(2) }));

  // Filtered trade log
  const filteredTrades = trades
    .filter(t => filterSym === "ALL" || t.symbol === filterSym)
    .filter(t => filterRes === "ALL" || t.result === filterRes)
    .filter(t => filterSess === "ALL" || t.session === filterSess)
    .sort((a, b) => {
      const av = a[sortCol], bv = b[sortCol];
      const d = typeof av === "string" ? av.localeCompare(bv) : av - bv;
      return sortDir === "desc" ? -d : d;
    });

  const symbols = [...new Set(trades.map(t => t.symbol))];

  // File upload handler
  const handleFileUpload = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const lines = ev.target.result.trim().split("\n");
        const header = lines[0].split(",").map(h => h.replace(/"/g,"").trim());
        const parsed = lines.slice(1).map(line => {
          const vals = line.split(",").map(v => v.replace(/"/g,"").trim());
          const obj = {};
          header.forEach((h, i) => { obj[h] = vals[i]; });
          return {
            date: obj["Date"] || "", time: obj["Time"] || "",
            symbol: obj["Symbol"] || "EURUSD",
            direction: obj["Direction"] || "BUY",
            lots: parseFloat(obj["Lots"]) || 0,
            entry: parseFloat(obj["EntryPrice"]) || 0,
            sl: parseFloat(obj["StopLoss"]) || 0,
            tp1: parseFloat(obj["TP1"]) || 0,
            tp2: parseFloat(obj["TP2"]) || 0,
            score: parseFloat(obj["TradeScore"]) || 0,
            regime: obj["Regime"] || "", bias: obj["HTFBias"] || "",
            session: obj["Session"] || "",
            exitDate: obj["ExitDate"] || "", exitTime: obj["ExitTime"] || "",
            exit: parseFloat(obj["ExitPrice"]) || 0,
            pips: parseFloat(obj["PipsGained"]) || 0,
            profit: parseFloat(obj["Profit"]) || 0,
            dailyDD: parseFloat(obj["DailyDD_Pct"]) || 0,
            maxDD: parseFloat(obj["MaxDD_Pct"]) || 0,
            riskUsed: parseFloat(obj["DailyRiskUsed_Pct"]) || 0,
            result: obj["Result"] || "LOSS",
            reason: obj["CloseReason"] || "",
            consec: parseInt(obj["ConsecLosses"]) || 0,
            balance: parseFloat(obj["BalanceAtEntry"]) || 0,
            equity: parseFloat(obj["EquityAtEntry"]) || 0,
          };
        }).filter(t => t.date && t.symbol);
        setTrades(parsed);
        setDemoMode(false);
      } catch(err) {
        alert("CSV parse error: " + err.message);
      }
    };
    reader.readAsText(file);
  }, []);

  const statusColor = propStatus === "ACTIVE" ? C.green : propStatus === "WARNING" ? C.yellow : C.red;

  // ── STYLES ──
  const tabStyle = (t) => ({
    padding: "8px 20px", cursor: "pointer", fontSize: 11,
    fontFamily: "monospace", letterSpacing: "0.1em", textTransform: "uppercase",
    fontWeight: 700, borderBottom: `2px solid ${activeTab===t ? C.blue : "transparent"}`,
    color: activeTab===t ? C.blue : C.textDim,
    background: "transparent", border: "none",
    borderBottom: `2px solid ${activeTab===t ? C.blue : "transparent"}`,
    transition: "color 0.2s"
  });

  const thStyle = {
    padding: "8px 12px", fontSize: 9, color: C.textMuted, fontFamily: "monospace",
    textTransform: "uppercase", letterSpacing: "0.12em", borderBottom: `1px solid ${C.border}`,
    background: C.surface, textAlign: "left", cursor: "pointer", whiteSpace: "nowrap",
    fontWeight: 600
  };

  const tdStyle = {
    padding: "7px 12px", fontSize: 11, fontFamily: "monospace",
    borderBottom: `1px solid ${C.border}28`, whiteSpace: "nowrap"
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "monospace" }}>

      {/* ── Scanline effect ── */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1000,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)"
      }} />

      {/* ── HEADER ── */}
      <div style={{
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "0 24px", display: "flex", alignItems: "center",
        justifyContent: "space-between", height: 52, position: "sticky", top: 0, zIndex: 100
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: `linear-gradient(135deg, ${C.blue}, ${C.purple})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 900
            }}>⚡</div>
            <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.05em", color: C.text }}>
              INSTITUTIONAL SNIPER PRO
            </span>
            <span style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.1em" }}>v1.0</span>
          </div>

          {demoMode && (
            <Badge text="DEMO DATA" color={C.yellow} />
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Glow color={statusColor} size={7} />
            <span style={{ fontSize: 10, color: statusColor, fontWeight: 700, letterSpacing: "0.1em" }}>
              {propStatus}
            </span>
          </div>

          <div style={{ fontSize: 12, color: C.textDim }}>
            Balance: <span style={{ color: C.text, fontWeight: 700 }}>
              ${(10000 + totalProfit).toFixed(2)}
            </span>
          </div>

          <div style={{ fontSize: 12, color: totalProfit >= 0 ? C.green : C.red, fontWeight: 700 }}>
            {usd(totalProfit)} ({pct((totalProfit/10000)*100)})
          </div>

          <label style={{
            padding: "6px 14px", fontSize: 10, fontWeight: 700,
            letterSpacing: "0.1em", textTransform: "uppercase",
            background: C.blue + "20", color: C.blue,
            border: `1px solid ${C.blue}60`, borderRadius: 5,
            cursor: "pointer"
          }}>
            LOAD CSV
            <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: "none" }} />
          </label>
        </div>
      </div>

      {/* ── TABS ── */}
      <div style={{
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "0 24px", display: "flex", gap: 0
      }}>
        {["overview","trades","sessions","regimes","compliance"].map(t => (
          <button key={t} onClick={() => setActiveTab(t)} style={tabStyle(t)}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ padding: "20px 24px", maxWidth: 1600, margin: "0 auto" }}>

        {/* ════════════════════════════════════════
            TAB: OVERVIEW
        ════════════════════════════════════════ */}
        {activeTab === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

            {/* KPI Row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 12 }}>
              <StatCard label="Total Trades" value={trades.length} />
              <StatCard label="Win Rate" value={winRate.toFixed(1)+"%"} color={winRate>=55?C.green:C.red} sub={`${wins.length}W / ${losses.length}L`} />
              <StatCard label="Profit Factor" value={pFactor.toFixed(2)} color={pFactor>=1.4?C.green:pFactor>=1.0?C.yellow:C.red} sub={pFactor>=1.4?"Excellent":pFactor>=1.0?"Acceptable":"Poor"} />
              <StatCard label="Avg RR" value={avgRR.toFixed(2)+"R"} color={avgRR>=1.5?C.green:C.yellow} sub={`Win $${avgWin.toFixed(2)} / Loss $${avgLoss.toFixed(2)}`} />
              <StatCard label="Net Profit" value={usd(totalProfit)} color={clr(totalProfit)} sub={pct((totalProfit/10000)*100)} />
              <StatCard label="Avg Score" value={avgScore.toFixed(1)+"/10"} color={avgScore>=7?C.green:C.yellow} sub={`Min required: 6.0`} />
              <StatCard label="Max Drawdown" value={maxDD.toFixed(2)+"%"} color={maxDD<5?C.green:maxDD<8?C.yellow:C.red} sub={`Limit: 8.0%`} />
              <StatCard label="Max Daily DD" value={maxDailyDD.toFixed(2)+"%"} color={maxDailyDD<2?C.green:maxDailyDD<3?C.yellow:C.red} sub={`Limit: 3.0%`} />
            </div>

            {/* Charts Row */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>

              {/* Equity Curve */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                  Equity Curve — Starting Balance $10,000
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={equityCurve}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={C.blue} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={C.blue} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={C.border} strokeDasharray="3 3" strokeOpacity={0.5} />
                    <XAxis dataKey="date" tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false}
                      tickFormatter={(v) => v.includes(" ") ? v.split(" ")[0].slice(5) : ""} />
                    <YAxis tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false}
                      tickFormatter={(v) => "$"+v.toFixed(0)} domain={["auto","auto"]} />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={10000} stroke={C.textMuted} strokeDasharray="4 4" strokeOpacity={0.5} />
                    <Area type="monotone" dataKey="balance" name="balance"
                      stroke={C.blue} strokeWidth={2} fill="url(#eqGrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Daily P&L */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                  Daily P&L
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dailyPnL}>
                    <CartesianGrid stroke={C.border} strokeDasharray="3 3" strokeOpacity={0.5} />
                    <XAxis dataKey="date" tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false} />
                    <YAxis tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false}
                      tickFormatter={(v) => "$"+v.toFixed(0)} />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={0} stroke={C.textMuted} />
                    <Bar dataKey="pnl" name="pnl" radius={[3, 3, 0, 0]}>
                      {dailyPnL.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? C.green : C.red}
                          fillOpacity={0.8} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Bottom Row: Score Dist + Session + Regime */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>

              {/* Score Distribution */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                  Trade Quality Score Distribution
                </div>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={scoreBins} layout="vertical">
                    <XAxis type="number" tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false} />
                    <YAxis type="category" dataKey="range" tick={{ fill: C.textDim, fontSize: 10, fontFamily: "monospace" }} tickLine={false} width={55} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" name="count" fill={C.blue} fillOpacity={0.8} radius={[0,3,3,0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ marginTop: 8, fontSize: 10, color: C.textDim }}>
                  {scoreBins.map(b => (
                    <div key={b.range} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                      <span>{b.range}</span>
                      <span style={{ color: b.wr>=60?C.green:b.wr>=50?C.yellow:C.red }}>
                        {b.wr.toFixed(0)}% WR
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Session Performance */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                  Session Performance
                </div>
                {[
                  { name: "London", trades: londonTrades, wr: lWR, pnl: lPnL, color: C.blue },
                  { name: "New York", trades: nyTrades, wr: nWR, pnl: nPnL, color: C.purple },
                ].map(s => (
                  <div key={s.name} style={{ marginBottom: 20 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: s.color }}>{s.name}</span>
                      <span style={{ fontSize: 12, color: clr(s.pnl) }}>{usd(s.pnl)}</span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.trades.length}</div>
                        <div style={{ fontSize: 9, color: C.textMuted }}>TRADES</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: s.wr>=55?C.green:C.yellow }}>{s.wr.toFixed(0)}%</div>
                        <div style={{ fontSize: 9, color: C.textMuted }}>WIN RATE</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: clr(s.pnl) }}>{(s.pnl/10000*100).toFixed(2)}%</div>
                        <div style={{ fontSize: 9, color: C.textMuted }}>RETURN</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Regime Performance */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                  Regime Performance
                </div>
                {regimeStats.map(r => {
                  const rColor = r.wr >= 60 ? C.green : r.wr >= 50 ? C.yellow : C.red;
                  return (
                    <div key={r.name} style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "10px 0", borderBottom: `1px solid ${C.border}28`
                    }}>
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: C.text }}>{r.name}</div>
                        <div style={{ fontSize: 10, color: C.textDim }}>{r.count} trades</div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: rColor }}>{r.wr.toFixed(0)}%</div>
                        <div style={{ fontSize: 10, color: clr(r.pnl) }}>{usd(r.pnl)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════
            TAB: TRADE LOG
        ════════════════════════════════════════ */}
        {activeTab === "trades" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Filters */}
            <div style={{
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "14px 16px",
              display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap"
            }}>
              <span style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                FILTER:
              </span>
              {[
                { label: "Symbol", val: filterSym, set: setFilterSym, opts: ["ALL", ...symbols] },
                { label: "Result", val: filterRes, set: setFilterRes, opts: ["ALL","WIN","LOSS"] },
                { label: "Session", val: filterSess, set: setFilterSess, opts: ["ALL","London","NY"] },
              ].map(f => (
                <div key={f.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 10, color: C.textDim }}>{f.label}:</span>
                  <select
                    value={f.val}
                    onChange={e => f.set(e.target.value)}
                    style={{
                      background: C.surface, color: C.text, border: `1px solid ${C.border}`,
                      borderRadius: 4, padding: "4px 8px", fontSize: 11, fontFamily: "monospace",
                      cursor: "pointer"
                    }}
                  >
                    {f.opts.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              ))}
              <div style={{ marginLeft: "auto", fontSize: 11, color: C.textDim }}>
                {filteredTrades.length} trades shown
              </div>
            </div>

            {/* Table */}
            <div style={{
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 8, overflow: "hidden"
            }}>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {[
                        ["date","Date"],["time","Time"],["symbol","Sym"],["direction","Dir"],
                        ["lots","Lots"],["score","Score"],["session","Session"],
                        ["regime","Regime"],["pips","Pips"],["profit","P&L"],
                        ["dailyDD","DD Day"],["maxDD","DD Max"],["result","Result"],["reason","Reason"]
                      ].map(([col, label]) => (
                        <th key={col} style={thStyle} onClick={() => {
                          if(sortCol===col) setSortDir(d=>d==="asc"?"desc":"asc");
                          else { setSortCol(col); setSortDir("desc"); }
                        }}>
                          {label} {sortCol===col ? (sortDir==="desc"?"↓":"↑") : ""}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.map((t, i) => {
                      const isWin = t.result === "WIN";
                      return (
                        <tr key={i} style={{
                          background: i%2===0 ? "transparent" : C.surface+"50",
                          transition: "background 0.15s"
                        }}>
                          <td style={tdStyle}>{t.date}</td>
                          <td style={tdStyle}>{t.time}</td>
                          <td style={{ ...tdStyle, color: C.blue, fontWeight: 700 }}>{t.symbol}</td>
                          <td style={{ ...tdStyle, color: t.direction==="BUY"?C.green:C.red, fontWeight: 700 }}>
                            {t.direction}
                          </td>
                          <td style={tdStyle}>{t.lots.toFixed(2)}</td>
                          <td style={{ ...tdStyle, color: t.score>=7.5?C.green:t.score>=6?C.yellow:C.red, fontWeight: 700 }}>
                            {t.score.toFixed(1)}
                          </td>
                          <td style={tdStyle}>{t.session}</td>
                          <td style={{ ...tdStyle, fontSize: 10 }}>{t.regime}</td>
                          <td style={{ ...tdStyle, color: t.pips>=0?C.green:C.red }}>
                            {pip(t.pips)}
                          </td>
                          <td style={{ ...tdStyle, color: t.profit>=0?C.green:C.red, fontWeight: 700 }}>
                            {usd(t.profit)}
                          </td>
                          <td style={{ ...tdStyle, color: t.dailyDD>=2?C.yellow:C.textDim }}>
                            {t.dailyDD.toFixed(2)}%
                          </td>
                          <td style={{ ...tdStyle, color: t.maxDD>=5?C.red:t.maxDD>=3?C.yellow:C.textDim }}>
                            {t.maxDD.toFixed(2)}%
                          </td>
                          <td style={tdStyle}>
                            <Badge text={t.result} color={isWin?C.green:C.red} />
                          </td>
                          <td style={{ ...tdStyle, color: C.textDim, fontSize: 10 }}>{t.reason}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════
            TAB: SESSIONS
        ════════════════════════════════════════ */}
        {activeTab === "sessions" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {[
                { name: "London Session", time: "08:00 - 16:00 UTC", data: londonTrades, wr: lWR, pnl: lPnL, color: C.blue },
                { name: "New York Session", time: "13:00 - 21:00 UTC", data: nyTrades, wr: nWR, pnl: nPnL, color: C.purple },
              ].map(s => {
                const sWins = s.data.filter(t=>t.result==="WIN");
                const sLoss = s.data.filter(t=>t.result==="LOSS");
                const sAvgRR = s.data.length ? s.data.reduce((a,t)=>a+t.score,0)/s.data.length : 0;
                return (
                  <div key={s.name} style={{ background: C.card, border: `1px solid ${s.color}40`, borderRadius: 8, padding: 24 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
                      <div>
                        <div style={{ fontSize: 16, fontWeight: 800, color: s.color }}>{s.name}</div>
                        <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{s.time}</div>
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: clr(s.pnl) }}>{usd(s.pnl)}</div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
                      {[
                        { l: "Trades", v: s.data.length, c: C.text },
                        { l: "Win Rate", v: s.wr.toFixed(1)+"%", c: s.wr>=55?C.green:C.yellow },
                        { l: "Wins", v: sWins.length, c: C.green },
                        { l: "Losses", v: sLoss.length, c: C.red },
                      ].map(st => (
                        <div key={st.l} style={{ textAlign: "center", background: C.surface, borderRadius: 6, padding: "10px 8px" }}>
                          <div style={{ fontSize: 20, fontWeight: 700, color: st.c }}>{st.v}</div>
                          <div style={{ fontSize: 9, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.1em" }}>{st.l}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>Avg Score</div>
                    <div style={{ height: 6, background: C.border, borderRadius: 3, marginBottom: 16 }}>
                      <div style={{ height: "100%", width: `${(sAvgRR/10)*100}%`, background: s.color, borderRadius: 3 }} />
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: s.color }}>{sAvgRR.toFixed(1)} / 10</div>
                  </div>
                );
              })}
            </div>

            {/* Session P&L by day chart */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
              <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                Session P&L Comparison by Day
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={dailyPnL}>
                  <CartesianGrid stroke={C.border} strokeDasharray="3 3" strokeOpacity={0.4} />
                  <XAxis dataKey="date" tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false} />
                  <YAxis tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false} tickFormatter={v=>"$"+v} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine y={0} stroke={C.textMuted} />
                  <Bar dataKey="pnl" name="pnl" radius={[3,3,0,0]}>
                    {dailyPnL.map((e, i) => <Cell key={i} fill={e.pnl>=0?C.green:C.red} fillOpacity={0.8} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════
            TAB: REGIMES
        ════════════════════════════════════════ */}
        {activeTab === "regimes" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {regimes.map(r => {
                const rt = trades.filter(t=>t.regime===r);
                const rw = rt.filter(t=>t.result==="WIN");
                const rPnl = rt.reduce((s,t)=>s+t.profit,0);
                const rWR = rt.length ? (rw.length/rt.length)*100 : 0;
                const rColor = rWR>=60?C.green:rWR>=50?C.yellow:rt.length?C.red:C.textMuted;
                return (
                  <div key={r} style={{ background: C.card, border: `1px solid ${rColor}30`, borderRadius: 8, padding: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, color: rColor, marginBottom: 16, letterSpacing: "0.05em" }}>{r}</div>
                    <div style={{ fontSize: 36, fontWeight: 900, color: rColor, marginBottom: 4 }}>
                      {rt.length ? rWR.toFixed(0)+"%" : "—"}
                    </div>
                    <div style={{ fontSize: 10, color: C.textDim, marginBottom: 16 }}>win rate</div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                      <span style={{ color: C.textDim }}>{rt.length} trades</span>
                      <span style={{ color: clr(rPnl), fontWeight: 700 }}>{rt.length?usd(rPnl):"—"}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
              <div style={{ fontSize: 10, color: C.textMuted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16 }}>
                Regime Win Rate vs Trade Count
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={regimeStats}>
                  <CartesianGrid stroke={C.border} strokeDasharray="3 3" strokeOpacity={0.4}/>
                  <XAxis dataKey="name" tick={{ fill: C.textDim, fontSize: 10, fontFamily: "monospace" }} tickLine={false} />
                  <YAxis tick={{ fill: C.textMuted, fontSize: 9 }} tickLine={false} unit="%" />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="wr" name="wr" radius={[4,4,0,0]}>
                    {regimeStats.map((r, i) => (
                      <Cell key={i} fill={r.wr>=60?C.green:r.wr>=50?C.yellow:C.red} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════
            TAB: COMPLIANCE
        ════════════════════════════════════════ */}
        {activeTab === "compliance" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Prop Firm Status Card */}
            <div style={{
              background: C.card, border: `2px solid ${statusColor}40`,
              borderRadius: 8, padding: 24,
              display: "flex", alignItems: "center", gap: 20
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: statusColor + "20",
                border: `2px solid ${statusColor}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 28
              }}>
                {propStatus === "ACTIVE" ? "✓" : propStatus === "WARNING" ? "⚠" : "✗"}
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 900, color: statusColor, letterSpacing: "0.05em" }}>
                  {propStatus}
                </div>
                <div style={{ fontSize: 12, color: C.textDim, marginTop: 4 }}>
                  {propStatus === "ACTIVE" ? "All prop firm rules complied with. Bot is trading normally." :
                   propStatus === "WARNING" ? "Approaching drawdown limits. Position sizing reduced automatically." :
                   "Trading halted. Drawdown limit reached. Bot stopped all trading."}
                </div>
              </div>
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ fontSize: 11, color: C.textDim }}>Total Net Profit</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: clr(totalProfit) }}>{usd(totalProfit)}</div>
                <div style={{ fontSize: 12, color: clr(totalProfit) }}>{pct((totalProfit/10000)*100)} of target</div>
              </div>
            </div>

            {/* Risk Gauges */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 24 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 20 }}>
                  DAILY DRAWDOWN MONITOR
                </div>
                <RiskGauge label="Today's Drawdown" used={currentDailyDD} limit={DAILY_LIMIT} color={C.blue} />
                <div style={{ marginTop: 16, fontSize: 11, color: C.textDim, lineHeight: 1.8 }}>
                  <div>Hard limit: <span style={{ color: C.text }}>{DAILY_LIMIT}%</span></div>
                  <div>Prop firm limit: <span style={{ color: C.text }}>5.0%</span></div>
                  <div>Buffer remaining: <span style={{ color: C.green }}>{(DAILY_LIMIT - currentDailyDD).toFixed(2)}%</span></div>
                  <div>Position reduction at: <span style={{ color: C.yellow }}>1.5% used</span></div>
                </div>
              </div>

              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 24 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 20 }}>
                  MAX DRAWDOWN MONITOR
                </div>
                <RiskGauge label="Total Max Drawdown" used={currentMaxDD} limit={MAX_DD_LIMIT} color={C.purple} />
                <div style={{ marginTop: 16, fontSize: 11, color: C.textDim, lineHeight: 1.8 }}>
                  <div>Hard limit: <span style={{ color: C.text }}>{MAX_DD_LIMIT}%</span></div>
                  <div>Prop firm limit: <span style={{ color: C.text }}>10.0%</span></div>
                  <div>Buffer remaining: <span style={{ color: C.green }}>{(MAX_DD_LIMIT - currentMaxDD).toFixed(2)}%</span></div>
                  <div>High water mark: <span style={{ color: C.text }}>$10,000.00</span></div>
                </div>
              </div>
            </div>

            {/* Prop Firm Comparison */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 24 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 20 }}>
                PROP FIRM RULE COMPLIANCE CHECK
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {["Firm","EA Allowed","Daily Limit","Max DD","Consistency","Your Status"].map(h => (
                      <th key={h} style={{ ...thStyle, fontSize: 9 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { firm:"FTMO",     ea:"✓",  daily:"5%",    maxDD:"10%", consistency:"None",    ok: currentDailyDD<5 && currentMaxDD<10 },
                    { firm:"E8 Markets",ea:"✓", daily:"3-9.2%",maxDD:"4-14%",consistency:"35% cap",ok: currentDailyDD<3 && currentMaxDD<8 },
                    { firm:"FundedNext",ea:"✓", daily:"5%",    maxDD:"10%", consistency:"None",    ok: currentDailyDD<5 && currentMaxDD<10 },
                    { firm:"The5ers",   ea:"✓", daily:"5%",    maxDD:"10%", consistency:"None",    ok: currentDailyDD<5 && currentMaxDD<10 },
                    { firm:"FunderPro", ea:"Self-coded",daily:"Varies",maxDD:"Varies",consistency:"None",ok:true },
                  ].map((r, i) => (
                    <tr key={i} style={{ background: i%2===0?"transparent":C.surface+"50" }}>
                      <td style={{ ...tdStyle, fontWeight: 700, color: C.blue }}>{r.firm}</td>
                      <td style={{ ...tdStyle, color: C.green }}>{r.ea}</td>
                      <td style={tdStyle}>{r.daily}</td>
                      <td style={tdStyle}>{r.maxDD}</td>
                      <td style={{ ...tdStyle, color: C.textDim }}>{r.consistency}</td>
                      <td style={tdStyle}>
                        <Badge text={r.ok ? "PASS" : "FAIL"} color={r.ok ? C.green : C.red} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Rule audit log */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 24 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 16 }}>
                RULE AUDIT LOG
              </div>
              {[
                { time:"2026-04-01 08:00", rule:"Daily Reset", detail:"New trading day. Balance: $10,000.00", status:"INFO" },
                { time:"2026-04-01 13:58", rule:"SL Hit — Daily DD Check", detail:"DD: 0.75% / 3.0% limit. Position sizing unchanged.", status:"OK" },
                { time:"2026-04-02 09:00", rule:"Daily Reset", detail:"New trading day. Balance: $10,014.80", status:"INFO" },
                { time:"2026-04-03 09:20", rule:"SL Hit — Daily DD Check", detail:"DD: 0.75% / 3.0% limit. Position sizing unchanged.", status:"OK" },
                { time:"2026-04-07 09:30", rule:"SL Hit — Daily DD Check", detail:"DD: 0.75% / 3.0% limit. Position sizing unchanged.", status:"OK" },
                { time:"2026-04-08 09:45", rule:"Trade Closed — TP1 Hit", detail:"Score: 9.0/10. Profit: +$7.60. All rules complied.", status:"OK" },
              ].map((e, i) => (
                <div key={i} style={{
                  display: "flex", gap: 16, padding: "10px 0",
                  borderBottom: `1px solid ${C.border}40`,
                  alignItems: "flex-start"
                }}>
                  <span style={{ fontSize: 10, color: C.textMuted, whiteSpace: "nowrap", marginTop: 1 }}>{e.time}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: e.status==="OK"?C.green:e.status==="WARN"?C.yellow:C.blue, whiteSpace: "nowrap" }}>
                    {e.status}
                  </span>
                  <div>
                    <div style={{ fontSize: 11, color: C.text, fontWeight: 600 }}>{e.rule}</div>
                    <div style={{ fontSize: 10, color: C.textDim }}>{e.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* Footer */}
      <div style={{
        padding: "16px 24px", borderTop: `1px solid ${C.border}`,
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }}>
        <span style={{ fontSize: 10, color: C.textMuted }}>
          ISP DASHBOARD v1.0 — {demoMode ? "DEMO DATA — Load your CSV from MT5 Files/ISP_Logs/" : `${trades.length} trades loaded`}
        </span>
        <span style={{ fontSize: 10, color: C.textMuted }}>
          Magic: {202601} · Exness MT5 · Updated: {new Date().toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}
