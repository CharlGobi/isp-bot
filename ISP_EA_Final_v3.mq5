//+------------------------------------------------------------------+
//|  InstitutionalSniperPro v3.0                                     |
//|  PATCHED BUILD — All best-practice fixes applied                 |
//|                                                                  |
//|  PATCHES vs v2.0 (BP/BUG fixes):                                |
//|  [A]  Auto-detect ORDER_FILLING mode per symbol (BP-01/BUG-06)  |
//|  [B]  Check TERMINAL/MQL/ACCOUNT trade-allowed in OnInit (BP-04)|
//|  [C]  Check SYMBOL_TRADE_MODE before trading (BP-03)            |
//|  [D]  BarsCalculated warmup guard in OnTick (BP-05/BUG-18)      |
//|  [E]  Validate SL/TP vs SYMBOL_TRADE_STOPS_LEVEL (BP-08)        |
//|  [F]  ChartRedraw() after Comment() (BP-06)                     |
//|  [G]  Weekend/market-closed guard (BP-10)                       |
//|  [H]  OnChartEvent throttle — max once per 2s (BP-11)           |
//|                                                                  |
//|  FIXES vs v1.0:                                                  |
//|  [1]  Added EventSetTimer(30) — OnTimer was never registered     |
//|  [2]  Fixed position sizing — universal formula (JPY/Gold safe)  |
//|  [3]  Fixed ManageOpenTrades — no live buffer on every tick      |
//|  [4]  Added TradeRecord struct — entry state stored for logging  |
//|  [5]  Fixed HistoryDealSelect before HistoryDealGetDouble        |
//|  [6]  Fixed CloseAllPositions — ticket-based (no index shift)    |
//|  [7]  Added Phase 2 ONNX — optional, graceful fallback          |
//|  [8]  Added Phase 3 Sentiment — WebRequest, graceful fallback    |
//|  [9]  Added Phase 4 inline logging — no external .mqh needed     |
//|  [10] Defined FRACTAL_UPPER/LOWER explicitly (no Indicators.mqh) |
//|  [11] Added GMT offset input — Exness server UTC+3 default       |
//|  [12] Cached regime/bias for dashboard safety                    |
//|  [13] Added RSI/ATR percentile for ONNX feature vector           |
//|  [14] Fixed DI+ DI- buffer indices (1 and 2, not 0 and 1)       |
//|  [15] Fixed DEAL_ENTRY_OUT check in OnTradeTransaction           |
//|  [16] Added input validation in OnInit                           |
//|  [17] Daily summary auto-writes on day change                    |
//+------------------------------------------------------------------+

#property copyright "ISP EA v3.0 — Fully Patched Build"
#property version   "3.00"
#property description "Institutional Sniper Pro | Prop Firm Ready | All Phases Integrated | All BP Fixes Applied"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\DealInfo.mqh>

// FIX [10]: Define fractal buffer constants explicitly
// iFractals buffer 0 = upper fractals (highs/resistance)
// iFractals buffer 1 = lower fractals (lows/support)
#define FRACTAL_UPPER 0
#define FRACTAL_LOWER 1

//============================================================
//  SECTION 1: ENUMS
//============================================================
enum ENUM_REGIME {
   REGIME_BULL_TREND,
   REGIME_BEAR_TREND,
   REGIME_WEAK_TREND,
   REGIME_RANGE,
   REGIME_AVOID
};
enum ENUM_BIAS { BIAS_BULL, BIAS_BEAR, BIAS_NEUTRAL };

//============================================================
//  SECTION 2: INPUTS
//============================================================
input group "=== CORE STRATEGY ==="
input int    InpEMA_Fast       = 9;
input int    InpEMA_Mid        = 21;
input int    InpEMA_Slow       = 50;

input group "=== MULTI-TIMEFRAME BIAS ==="
input ENUM_TIMEFRAMES InpHTF1  = PERIOD_H4;
input int    InpHTF1_EMA       = 200;
input ENUM_TIMEFRAMES InpHTF2  = PERIOD_H1;
input int    InpHTF2_EMA       = 50;
input int    InpHTF3_EMA       = 20;   // H1 EMA-20 fast bias gate (0 = disabled)

input group "=== REGIME DETECTION ==="
input int    InpADX_Period     = 14;
input double InpADX_Trend      = 25.0;
input double InpADX_Avoid      = 15.0;
input double InpATR_MaxMult    = 1.5;
input double InpATR_MinMult    = 0.7;

input group "=== SESSION FILTER ==="
input bool   InpUseSession     = true;
input int    InpServerGMTOffset= 3;    // FIX [11]: Exness = UTC+3 default
input int    InpLondonOpenUTC  = 8;
input int    InpLondonCloseUTC = 16;
input int    InpNYOpenUTC      = 13;
input int    InpNYCloseUTC     = 21;

input group "=== NEWS FILTER ==="
input bool   InpUseNews        = true;
input int    InpNewsBefore_Min = 15;
input int    InpNewsAfter_Min  = 60;  // was 30 — 60min buffer after 12:30 data before NY open

input group "=== RISK MANAGEMENT ==="
input double InpRiskPct        = 0.5;   // % equity per trade
input double InpDailyLossLimit = 3.0;   // % — prop firms allow 5%, we use 3%
input double InpMaxDDLimit       = 8.0;   // % — prop firms allow 10%, we use 8%
input int    InpMaxConsecLosses  = 3;    // consecutive losses before pausing
input int    InpConsecPauseHours = 8;    // hours to pause after consecutive loss limit
input double InpMinScoreReq      = 7.0;  // trade quality minimum (was 6.0)
input int    InpMaxOpenTrades  = 2;
input bool   InpHalfKelly      = true;

input group "=== STOP LOSS & TAKE PROFIT ==="
input double InpSL_ATR_Mult    = 1.5;
input double InpTP1_RR         = 1.0;
input double InpTP2_RR         = 2.5;
input double InpTrail_ATR_Mult = 2.5;

input group "=== PHASE 2: ONNX ML FILTER ==="
input bool   InpUseONNX        = false; // Enable after running Python training
input float  InpONNXThreshold  = 0.55f;
input string InpONNXModelPath  = "ISP_Models\\EURUSD_model.onnx";

input group "=== PHASE 3: SENTIMENT FILTER ==="
input bool   InpUseSentiment   = false; // Enable after running isp_sentiment_service.py
input string InpSentimentURL   = "http://localhost:5050/sentiment";
input double InpSentBlockScore = -0.10;

input group "=== PHASE 4: LOGGING ==="
input bool   InpEnableLog      = true;
input string InpLogFolder      = "ISP_Logs";

input group "=== EA IDENTITY ==="
input int    InpMagicNumber    = 202601;
input string InpComment        = "ISP_v2";

//============================================================
//  SECTION 3: TRADE RECORD STRUCT (FIX [4])
//============================================================
struct TradeRecord {
   ulong    posId;
   string   direction;
   double   lots;
   double   entry;
   double   sl;
   double   tp1;
   double   tp2;
   double   score;
   string   regime;
   string   bias;
   string   session;
   double   ddAtEntry;
   double   maxDDAtEntry;
   int      openAtEntry;
   double   balAtEntry;
   double   eqAtEntry;
   datetime openTime;
};

//============================================================
//  SECTION 4: GLOBAL VARIABLES
//============================================================
CTrade       Trade;
CPositionInfo PosInfo;
CDealInfo    DealInfo;

// Indicator handles
int h_EMA_Fast, h_EMA_Mid, h_EMA_Slow;
int h_EMA_H4, h_EMA_H1, h_EMA_H1Fast;
int h_FracM5, h_FracH1;
int h_ADX_M5, h_ADX_H1;
int h_ATR_M5;
int h_RSI_M5;

// FIX [7]: ONNX handle — INVALID_HANDLE means Phase 2 not active
long g_OnnxHandle = INVALID_HANDLE;

// Data buffers
double buf_EmaFast[], buf_EmaMid[], buf_EmaSlw[];
double buf_EmaH4[], buf_EmaH1[], buf_EmaH1Fast[];
double buf_FracHi[], buf_FracLo[];
double buf_FracHiH1[], buf_FracLoH1[];
double buf_ADX[], buf_DI_P[], buf_DI_M[];
double buf_ADX_H1[];
double buf_ATR[];
double buf_RSI[];

// Risk tracking
double   g_DayStartBal;
double   g_EqHighWater;
datetime g_LastDay;
bool     g_Halted;
string   g_HaltReason;
int      g_ConsecLosses  = 0;
datetime g_PauseUntil    = 0;

// FIX [3]: Cached ATR updated only on bar close (safe for ManageOpenTrades on tick)
double   g_CachedATR = 0.0;

// FIX [12]: Cached values for dashboard (safe to call from OnTimer without buffer access)
ENUM_REGIME g_CachedRegime    = REGIME_AVOID;
ENUM_BIAS   g_CachedBias      = BIAS_NEUTRAL;
double      g_CachedScore     = 0.0;
string      g_NewsEventName   = "";   // last news event blocking trading (for dashboard)
double      g_DailyDD_Pct  = 0.0;
double      g_MaxDD_Pct    = 0.0;

// Daily performance counters
int    g_DayTrades, g_DayWins, g_DayLosses;
int    g_DayLondon, g_DayLondonW;
int    g_DayNY,     g_DayNYW;
double g_DayGWin,   g_DayGLoss, g_DayScoreSum;
bool   g_DayHalted;

// Trade records for logging (up to 50 concurrent positions)
TradeRecord g_Recs[50];
int         g_RecCount = 0;

//============================================================
//  SECTION 5: LOGGING HELPERS (FIX [9] — inline, no .mqh needed)
//============================================================
void Log_EnsureHeader(string path, string header) {
   int hc = FileOpen(path, FILE_READ|FILE_CSV|FILE_COMMON);
   if(hc != INVALID_HANDLE) { FileClose(hc); return; }
   int hw = FileOpen(path, FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(hw == INVALID_HANDLE) return;
   FileWrite(hw, header);
   FileClose(hw);
}

void Log_Trade(TradeRecord &r, datetime exitT, double exitPx,
               double pips, double profit, string res, string why) {
   if(!InpEnableLog) return;
   string path = InpLogFolder+"\\ISP_Trades_"+_Symbol+"_"+
                 StringSubstr(TimeToString(r.openTime,TIME_DATE),0,10)+".csv";
   Log_EnsureHeader(path,
      "Date,Time,Symbol,Direction,Lots,EntryPrice,StopLoss,TP1,TP2,"
      "TradeScore,Regime,HTFBias,Session,ExitDate,ExitTime,ExitPrice,"
      "PipsGained,Profit,DailyDD_Pct,MaxDD_Pct,DailyRiskUsed_Pct,"
      "Result,CloseReason,OpenTradesAtEntry,BalanceAtEntry,EquityAtEntry");
   int h = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h,
      TimeToString(r.openTime,TIME_DATE), TimeToString(r.openTime,TIME_MINUTES),
      _Symbol, r.direction, DoubleToString(r.lots,2),
      DoubleToString(r.entry,_Digits), DoubleToString(r.sl,_Digits),
      DoubleToString(r.tp1,_Digits),   DoubleToString(r.tp2,_Digits),
      DoubleToString(r.score,1), r.regime, r.bias, r.session,
      TimeToString(exitT,TIME_DATE), TimeToString(exitT,TIME_MINUTES),
      DoubleToString(exitPx,_Digits),
      DoubleToString(pips,1), DoubleToString(profit,2),
      DoubleToString(r.ddAtEntry,3), DoubleToString(g_MaxDD_Pct,3),
      DoubleToString((r.ddAtEntry/InpDailyLossLimit)*100.0,1),
      res, why, IntegerToString(r.openAtEntry),
      DoubleToString(r.balAtEntry,2), DoubleToString(r.eqAtEntry,2));
   FileClose(h);
}

void Log_Skipped(string dir, double score, string why, string regime, string bias) {
   if(!InpEnableLog) return;
   string path = InpLogFolder+"\\ISP_Skipped_"+_Symbol+"_"+
                 StringSubstr(TimeToString(TimeCurrent(),TIME_DATE),0,10)+".csv";
   Log_EnsureHeader(path, "DateTime,Symbol,Direction,Score,SkipReason,Regime,Bias");
   int h = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(),TIME_DATE|TIME_MINUTES),
             _Symbol, dir, DoubleToString(score,1), why, regime, bias);
   FileClose(h);
}

void Log_Halt(string reason) {
   if(!InpEnableLog) return;
   string path = InpLogFolder+"\\ISP_Halts_"+_Symbol+".csv";
   Log_EnsureHeader(path, "DateTime,Symbol,Reason,DailyDD,MaxDD,Equity");
   int h = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(),TIME_DATE|TIME_MINUTES),
             _Symbol, reason,
             DoubleToString(g_DailyDD_Pct,3), DoubleToString(g_MaxDD_Pct,3),
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2));
   FileClose(h);
}

void Log_DailySummary() {
   if(!InpEnableLog || g_DayTrades == 0) return;
   string path = InpLogFolder+"\\ISP_Daily_"+_Symbol+".csv";
   Log_EnsureHeader(path,
      "Date,Symbol,Trades,Wins,Losses,WinRate,NetProfit,GrossWin,GrossLoss,"
      "ProfitFactor,LondonTrades,LondonWR,NYTrades,NYWR,AvgScore,StartBal,HaltOccurred");
   int h = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   double wr  = g_DayTrades  > 0 ? (double)g_DayWins /g_DayTrades*100  : 0;
   double lwr = g_DayLondon  > 0 ? (double)g_DayLondonW/g_DayLondon*100: 0;
   double nwr = g_DayNY      > 0 ? (double)g_DayNYW/g_DayNY*100        : 0;
   double pf  = g_DayGLoss != 0  ? g_DayGWin/MathAbs(g_DayGLoss) : 0;
   double avg = g_DayTrades  > 0 ? g_DayScoreSum/g_DayTrades : 0;
   FileWrite(h,
      TimeToString(TimeCurrent(),TIME_DATE), _Symbol,
      IntegerToString(g_DayTrades), IntegerToString(g_DayWins), IntegerToString(g_DayLosses),
      DoubleToString(wr,1), DoubleToString(g_DayGWin+g_DayGLoss,2),
      DoubleToString(g_DayGWin,2), DoubleToString(g_DayGLoss,2),
      DoubleToString(pf,2),
      IntegerToString(g_DayLondon), DoubleToString(lwr,1),
      IntegerToString(g_DayNY),     DoubleToString(nwr,1),
      DoubleToString(avg,1), DoubleToString(g_DayStartBal,2),
      (g_DayHalted ? "YES" : "NO"));
   FileClose(h);
}

//============================================================
//  SECTION 5b: CHANGELOG LOGGER
//  Called once on OnInit() — creates ISP_Changelog.csv with a
//  timestamped record of what changed and when.
//============================================================
void Log_Changelog(string version, string changeSummary) {
   if(!InpEnableLog) return;
   string path = InpLogFolder + "\\ISP_Changelog.csv";
   Log_EnsureHeader(path, "DateTime,Symbol,Version,Change");
   int h = FileOpen(path, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES),
             _Symbol, version, changeSummary);
   FileClose(h);
}

//============================================================
//  SECTION 6: ONNX PHASE 2 (FIX [7])
//  Requires MT5 build 3390+ (Dec 2022).
//  Disabled by default — add  #define USE_ONNX  to enable.
//============================================================
#ifdef USE_ONNX
bool ONNX_Init() {
   if(!InpUseONNX) return false;
   g_OnnxHandle = OnnxCreateFromFile(InpONNXModelPath, ONNX_DEFAULT);
   if(g_OnnxHandle == INVALID_HANDLE) {
      PrintFormat("ISP ONNX: NOT LOADED — '%s' not found (error %d). Trading without ML filter.",
                  InpONNXModelPath, GetLastError());
      return false;
   }
   long inShape[]  = {1, 27};
   long outShape[] = {1, 2};
   long lblShape[] = {1};
   if(!OnnxSetInputShape(g_OnnxHandle, 0, inShape) ||
      !OnnxSetOutputShape(g_OnnxHandle, 0, lblShape) ||
      !OnnxSetOutputShape(g_OnnxHandle, 1, outShape)) {
      PrintFormat("ISP ONNX: Shape config error %d. Disabling.", GetLastError());
      OnnxRelease(g_OnnxHandle);
      g_OnnxHandle = INVALID_HANDLE;
      return false;
   }
   Print("ISP ONNX: Model loaded OK.");
   return true;
}

float ONNX_GetProb(float &feat[]) {
   if(g_OnnxHandle == INVALID_HANDLE) return -1.0f;
   float input[1][27];
   for(int i = 0; i < 27; i++) input[0][i] = feat[i];
   float lbl[1];    lbl[0] = 0;
   float prob[1][2]; ArrayInitialize(prob, 0);
   if(!OnnxRun(g_OnnxHandle, ONNX_DEFAULT, input, lbl, prob)) {
      PrintFormat("ISP ONNX: OnnxRun failed error %d", GetLastError());
      return -1.0f;
   }
   return prob[0][1];
}
#else
// Stubs — compile on any MT5 build when USE_ONNX is not defined
bool  ONNX_Init()                  { return false;  }
float ONNX_GetProb(float &feat[])  { return -1.0f;  }
#endif

void ONNX_BuildFeatures(float &feat[]) {
   ArrayResize(feat, 27);
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double atr   = buf_ATR[1];
   double atrSum = 0;
   for(int i = 2; i <= 21; i++) atrSum += buf_ATR[i];
   double atrAvg = (atrSum > 0) ? atrSum / 20.0 : atr;
   
   double c1 = iClose(_Symbol,PERIOD_M5,1), o1 = iOpen(_Symbol,PERIOD_M5,1);
   double h1 = iHigh(_Symbol,PERIOD_M5,1),  l1 = iLow(_Symbol,PERIOD_M5,1);
   double rng = h1 - l1; if(rng < _Point) rng = _Point;
   double spread = SymbolInfoDouble(_Symbol,SYMBOL_ASK) - SymbolInfoDouble(_Symbol,SYMBOL_BID);
   
   int bfAge = 50, brAge = 50;
   for(int i=3;i<=50;i++){if(buf_FracLo[i]!=EMPTY_VALUE&&buf_FracLo[i]>0&&bfAge==50)bfAge=i;}
   for(int i=3;i<=50;i++){if(buf_FracHi[i]!=EMPTY_VALUE&&buf_FracHi[i]>0&&brAge==50)brAge=i;}
   
   double rsi = buf_RSI[1];
   double c4  = iClose(_Symbol,PERIOD_M5,4);
   double c10 = iClose(_Symbol,PERIOD_M5,10);
   
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int utcHr = dt.hour - InpServerGMTOffset; if(utcHr<0) utcHr+=24;
   
   // Feature order must match isp_feature_engineer.py FEATURE_COLS exactly
   feat[0]  = (float)(buf_EmaFast[1] / MathMax(buf_EmaMid[1], _Point));
   feat[1]  = (float)(buf_EmaMid[1]  / MathMax(buf_EmaSlw[1], _Point));
   feat[2]  = (float)(price           / MathMax(buf_EmaSlw[1], _Point));
   feat[3]  = (float)(price           / MathMax(buf_EmaH1[1],  _Point));
   feat[4]  = (float)(price           / MathMax(buf_EmaH4[1],  _Point));
   feat[5]  = (float)(atrAvg > 0 ? atr/atrAvg : 1.0);
   feat[6]  = (float)(atrAvg > 0 ? atr/atrAvg : 1.0);
   feat[7]  = (float)(atrAvg > 0 ? atr/atrAvg : 1.0);
   feat[8]  = (float)buf_ADX[1];
   feat[9]  = (float)(buf_DI_P[1] - buf_DI_M[1]);
   feat[10] = (float)buf_ADX_H1[1];
   feat[11] = (float)rsi;
   feat[12] = (float)((c4  > 0) ? (c1/c4  - 1.0) : 0.0);
   feat[13] = (float)((c10 > 0) ? (c1/c10 - 1.0) : 0.0);
   feat[14] = (float)(MathAbs(c1-o1)/rng);
   feat[15] = (float)((h1-MathMax(o1,c1)+MathMin(o1,c1)-l1)/rng);
   feat[16] = (float)(atr > 0 ? spread/atr : 0.0);
   feat[17] = (float)MathMin(bfAge, 50);
   feat[18] = (float)MathMin(brAge, 50);
   feat[19] = (float)((iHigh(_Symbol,PERIOD_M5,3) < iLow(_Symbol,PERIOD_M5,1)) ? 1.0f : 0.0f);
   feat[20] = (float)((iLow(_Symbol,PERIOD_M5,3)  > iHigh(_Symbol,PERIOD_M5,1))? 1.0f : 0.0f);
   feat[21] = 0.0f;
   feat[22] = 0.0f;
   feat[23] = (float)((utcHr>=InpLondonOpenUTC&&utcHr<InpLondonCloseUTC)?1.0f:0.0f);
   feat[24] = (float)((utcHr>=InpNYOpenUTC    &&utcHr<InpNYCloseUTC)    ?1.0f:0.0f);
   feat[25] = (float)((utcHr==13)             ? 1.0f : 0.0f);
   feat[26] = (float)dt.day_of_week;
}

//============================================================
//  SECTION 7: SENTIMENT PHASE 3 (FIX [8])
//============================================================
double Sentiment_Get(string pair) {
   if(!InpUseSentiment) return 0.0;
   string url   = InpSentimentURL + "?pair=" + pair;
   char   post[];
   char   result[];
   string resHdr;
   int code = WebRequest("GET", url, "", 3000, post, result, resHdr);
   if(code != 200) {
      if(code < 0 && GetLastError() == 4060)
         Print("ISP Sentiment: WebRequest blocked. Add 'http://localhost:5050' in MT5 Options > Expert Advisors > Allow WebRequest");
      return 0.0; // Service down = neutral, don't block trading
   }
   string json = CharArrayToString(result);
   string key  = "\"score\":";
   int pos = StringFind(json, key);
   if(pos < 0) return 0.0;
   pos += StringLen(key);
   string val = "";
   for(int i = pos; i < StringLen(json); i++) {
      ushort c = StringGetCharacter(json, i);
      if(c == ',' || c == '}' || c == ' ') break;
      val += StringSubstr(json, i, 1);
   }
   StringTrimLeft(val); StringTrimRight(val);
   return StringToDouble(val);
}

//============================================================
//  SECTION 8: INIT / DEINIT
//============================================================
int OnInit() {
   // FIX [16]: Validate critical inputs
   if(InpRiskPct <= 0 || InpRiskPct > 10.0) {
      Alert("ISP: InpRiskPct invalid (", InpRiskPct, "). Must be 0.1–10.0");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpDailyLossLimit <= 0 || InpDailyLossLimit > InpMaxDDLimit) {
      Alert("ISP: InpDailyLossLimit must be > 0 and < InpMaxDDLimit");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpMagicNumber <= 0) {
      Alert("ISP: Magic number must be positive");
      return INIT_PARAMETERS_INCORRECT;
   }
   
   // PATCH [B]: Verify trading is enabled at all 3 levels — terminal, EA, account
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) {
      Alert("ISP v3: Algo trading is DISABLED in the MT5 terminal.\n"
            "Click the 'Algo Trading' button in the toolbar to enable it.");
      return INIT_FAILED;
   }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) {
      Alert("ISP v3: EA trading not allowed.\n"
            "In EA properties, enable 'Allow Algo Trading'.");
      return INIT_FAILED;
   }
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) {
      Alert("ISP v3: Account ", AccountInfoInteger(ACCOUNT_LOGIN),
            " is not allowed to trade. Check account status with broker.");
      return INIT_FAILED;
   }

   // PATCH [C]: Verify the symbol is open and accepts new orders
   ENUM_SYMBOL_TRADE_MODE tradeMode =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(tradeMode == SYMBOL_TRADE_MODE_DISABLED) {
      Alert("ISP v3: ", _Symbol, " trading is disabled by broker.");
      return INIT_FAILED;
   }
   if(tradeMode == SYMBOL_TRADE_MODE_CLOSEONLY) {
      Alert("ISP v3: ", _Symbol, " is in CLOSE-ONLY mode (possibly pre-weekend/auction). Restart when market opens.");
      return INIT_FAILED;
   }

   Trade.SetExpertMagicNumber(InpMagicNumber);
   Trade.SetDeviationInPoints(30);

   // PATCH [A]: Auto-detect the fill mode this broker/account/symbol supports
   // Hardcoding IOC fails silently on demo accounts and non-Raw-Spread Exness accounts
   {
      long fillFlags = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
      ENUM_ORDER_TYPE_FILLING fillMode = ORDER_FILLING_IOC; // default
      if((fillFlags & SYMBOL_FILLING_IOC) != 0)
         fillMode = ORDER_FILLING_IOC;
      else if((fillFlags & SYMBOL_FILLING_FOK) != 0)
         fillMode = ORDER_FILLING_FOK;
      else
         fillMode = ORDER_FILLING_RETURN; // fallback — works on almost all brokers
      Trade.SetTypeFilling(fillMode);
      PrintFormat("ISP v3: Fill mode auto-detected: %s (flags=%d)",
                  EnumToString(fillMode), (int)fillFlags);
   }
   Trade.SetAsyncMode(false);
   
   // Create indicator handles
   h_EMA_Fast = iMA(_Symbol, PERIOD_M5, InpEMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   h_EMA_Mid  = iMA(_Symbol, PERIOD_M5, InpEMA_Mid,  0, MODE_EMA, PRICE_CLOSE);
   h_EMA_Slow = iMA(_Symbol, PERIOD_M5, InpEMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   h_EMA_H4      = iMA(_Symbol, InpHTF1,   InpHTF1_EMA, 0, MODE_EMA, PRICE_CLOSE);
   h_EMA_H1      = iMA(_Symbol, InpHTF2,   InpHTF2_EMA, 0, MODE_EMA, PRICE_CLOSE);
   h_EMA_H1Fast  = (InpHTF3_EMA > 0) ? iMA(_Symbol, InpHTF2, InpHTF3_EMA, 0, MODE_EMA, PRICE_CLOSE) : INVALID_HANDLE;
   h_FracM5   = iFractals(_Symbol, PERIOD_M5);
   h_FracH1   = iFractals(_Symbol, InpHTF2);
   h_ADX_M5   = iADX(_Symbol, PERIOD_M5, InpADX_Period);
   h_ADX_H1   = iADX(_Symbol, InpHTF2,   InpADX_Period);
   h_ATR_M5   = iATR(_Symbol, PERIOD_M5, 14);
   h_RSI_M5   = iRSI(_Symbol, PERIOD_M5, 14, PRICE_CLOSE);
   
   // Validate handles
   if(h_EMA_Fast==INVALID_HANDLE || h_EMA_Mid==INVALID_HANDLE ||
      h_EMA_Slow==INVALID_HANDLE || h_ADX_M5==INVALID_HANDLE  ||
      h_ATR_M5  ==INVALID_HANDLE || h_FracM5 ==INVALID_HANDLE ||
      h_RSI_M5  ==INVALID_HANDLE) {
      Alert("ISP: Failed to create indicator handles for ", _Symbol,
            ". Check symbol name and broker.");
      return INIT_FAILED;
   }
   
   // Set all arrays as series (index 0 = most recent bar)
   ArraySetAsSeries(buf_EmaFast, true);  ArraySetAsSeries(buf_EmaMid,   true);
   ArraySetAsSeries(buf_EmaSlw,     true);  ArraySetAsSeries(buf_EmaH4,    true);
   ArraySetAsSeries(buf_EmaH1,      true);  ArraySetAsSeries(buf_EmaH1Fast,true);
   ArraySetAsSeries(buf_FracHi,     true);
   ArraySetAsSeries(buf_FracLo,  true);  ArraySetAsSeries(buf_FracHiH1, true);
   ArraySetAsSeries(buf_FracLoH1,true);  ArraySetAsSeries(buf_ADX,      true);
   ArraySetAsSeries(buf_DI_P,    true);  ArraySetAsSeries(buf_DI_M,     true);
   ArraySetAsSeries(buf_ADX_H1,  true);  ArraySetAsSeries(buf_ATR,      true);
   ArraySetAsSeries(buf_RSI,     true);
   
   // Risk state
   g_DayStartBal  = AccountInfoDouble(ACCOUNT_BALANCE);
   g_EqHighWater  = AccountInfoDouble(ACCOUNT_EQUITY);
   g_LastDay      = iTime(_Symbol, PERIOD_D1, 0);
   g_Halted       = false;
   g_HaltReason   = "";
   
   // Reset daily counters
   g_DayTrades = g_DayWins = g_DayLosses = 0;
   g_DayLondon = g_DayLondonW = g_DayNY = g_DayNYW = 0;
   g_DayGWin   = g_DayGLoss  = g_DayScoreSum = 0;
   g_DayHalted = false;
   
   // Create log folder
   if(InpEnableLog) FolderCreate(InpLogFolder, FILE_COMMON);
   
   // Phase 2: ONNX
   ONNX_Init();
   
   // FIX [1]: Register timer for dashboard + compliance checks
   EventSetTimer(30);
   
   PrintFormat("ISP v3.1 INIT | %s | Magic %d | Risk %.1f%% | DailyLim %.1f%% | MaxDD %.1f%%",
               _Symbol, InpMagicNumber, InpRiskPct, InpDailyLossLimit, InpMaxDDLimit);
   PrintFormat("ISP PHASE STATUS | ONNX: %s | Sentiment: %s | Logging: %s",
               (g_OnnxHandle!=INVALID_HANDLE ? "ACTIVE" : (InpUseONNX ? "MODEL MISSING" : "OFF")),
               (InpUseSentiment ? "ENABLED" : "OFF"),
               (InpEnableLog    ? "ACTIVE"  : "OFF"));

   Log_Changelog("v3.1",
      "regime-direction guard in GetSignal; H1 EMA-20 fast bias gate; "
      "CalcScore trend bonus aligned-direction only; consecutive loss pause (3x/8h); "
      "news calendar diagnostic logging; InpNewsAfter 30->60min; InpMinScore 6->7; "
      "news event name on dashboard; changelog log added");

   DrawDashboard();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
#ifdef USE_ONNX
   if(g_OnnxHandle != INVALID_HANDLE) OnnxRelease(g_OnnxHandle);
#endif
   IndicatorRelease(h_EMA_Fast); IndicatorRelease(h_EMA_Mid);
   IndicatorRelease(h_EMA_Slow); IndicatorRelease(h_EMA_H4);
   IndicatorRelease(h_EMA_H1);  IndicatorRelease(h_EMA_H1Fast);
   IndicatorRelease(h_FracM5);
   IndicatorRelease(h_FracH1);  IndicatorRelease(h_ADX_M5);
   IndicatorRelease(h_ADX_H1);  IndicatorRelease(h_ATR_M5);
   IndicatorRelease(h_RSI_M5);
   Comment("");
}

// FIX [1]: Timer fires every 30 seconds
void OnTimer() {
   CheckDailyReset(); // Catch day change between ticks
   UpdateDrawdown();
   DrawDashboard();
}

//============================================================
//  SECTION 9: MAIN TICK
//============================================================
void OnTick() {
   // PATCH [D]: Warmup guard — wait for enough bars before any indicator-based logic
   // EMA-50 needs 50 bars, ADX 14 needs 28, ATR 14 needs 14; require 200 to be safe
   static bool g_WarmupDone = false;
   if(!g_WarmupDone) {
      if(BarsCalculated(h_EMA_Slow) < 200 || BarsCalculated(h_ATR_M5) < 200 ||
         BarsCalculated(h_ADX_M5)  < 200) {
         static int warnCount = 0;
         if(++warnCount % 100 == 1)
            PrintFormat("ISP v3: Waiting for warmup — EMA_Slow: %d/200 bars",
                        BarsCalculated(h_EMA_Slow));
         ManageOpenTrades(); // Still trail existing positions during warmup
         return;
      }
      g_WarmupDone = true;
      Print("ISP v3: Warmup complete (200+ bars). Trading enabled.");
   }

   // PATCH [G]: Weekend/closed-market guard
   // Some brokers send ticks on Saturday/Sunday — reject them to avoid rejected orders
   {
      MqlDateTime dtW; TimeToStruct(TimeCurrent(), dtW);
      if(dtW.day_of_week == 0 || dtW.day_of_week == 6) {
         ManageOpenTrades(); // Still trail during weekend (position may still be open)
         return;
      }
   }

   // FIX [3]: Manage trailing on every tick using CACHED ATR (not live buffer)
   ManageOpenTrades();
   
   // Entry logic only on new M5 bar close
   static datetime lastBar = 0;
   datetime curBar = iTime(_Symbol, PERIOD_M5, 0);
   if(curBar == lastBar) return;
   lastBar = curBar;
   
   // Update cached ATR from closed bar (index 1 = last complete candle)
   double tmpATR[];
   ArraySetAsSeries(tmpATR, true);
   if(CopyBuffer(h_ATR_M5, 0, 0, 3, tmpATR) > 0) g_CachedATR = tmpATR[1];
   
   // ── GATE 1: Daily reset ──────────────────────────────────
   CheckDailyReset();
   
   // ── GATE 2: Prop firm circuit breaker ────────────────────
   if(!CheckPropFirmRules()) { DrawDashboard(); return; }

   // ── GATE 2b: Consecutive loss pause ──────────────────────
   if(g_PauseUntil > 0 && TimeCurrent() < g_PauseUntil) {
      Log_Skipped("--", 0, "CONSEC_LOSS_PAUSE", RegimeStr(g_CachedRegime), BiasStr(g_CachedBias));
      return;
   }

   // ── GATE 3: Session filter ───────────────────────────────
   if(InpUseSession && !IsInSession()) return;
   
   // ── GATE 4: Max open trades ──────────────────────────────
   if(CountOpenTrades() >= InpMaxOpenTrades) return;
   
   // ── GATES 5-6: Indicators + regime ───────────────────────
   if(!RefreshBuffers()) return;
   
   ENUM_REGIME regime = GetRegime();
   g_CachedRegime = regime;
   if(regime == REGIME_AVOID) {
      Log_Skipped("--", 0, "REGIME_AVOID", RegimeStr(regime), "");
      return;
   }
   
   // ── GATE 7: HTF bias ─────────────────────────────────────
   ENUM_BIAS bias = GetBias();
   g_CachedBias = bias;
   if(bias == BIAS_NEUTRAL) {
      Log_Skipped("--", 0, "HTF_NEUTRAL", RegimeStr(regime), "NEUTRAL");
      return;
   }
   
   // ── GATE 8: Entry signal ─────────────────────────────────
   int sig = GetSignal(bias, regime);
   if(sig == 0) return;
   string sigStr = (sig == 1 ? "BUY" : "SELL");
   
   // ── GATE 9: Quality score ────────────────────────────────
   double score = CalcScore(sig, regime, bias);
   g_CachedScore = score;
   if(score < InpMinScoreReq) {
      Log_Skipped(sigStr, score, "LOW_SCORE", RegimeStr(regime), BiasStr(bias));
      return;
   }
   
   // ── GATE 10: ONNX ML filter (Phase 2) ────────────────────
   if(g_OnnxHandle != INVALID_HANDLE) {
      float feat[];
      ONNX_BuildFeatures(feat);
      float prob = ONNX_GetProb(feat);
      if(prob >= 0.0f && prob < InpONNXThreshold) {
         PrintFormat("ISP ONNX blocked: P(win)=%.3f < threshold %.3f", prob, InpONNXThreshold);
         Log_Skipped(sigStr, score, StringFormat("ONNX_%.3f", prob), RegimeStr(regime), BiasStr(bias));
         return;
      }
      if(prob > 0.0f) score = MathMin(10.0, score + (double)(prob - 0.55f) * 4.0);
   }
   
   // ── GATE 11: News filter ─────────────────────────────────
   if(InpUseNews && IsNewsWindow()) {
      Log_Skipped(sigStr, score, "NEWS_WINDOW", RegimeStr(regime), BiasStr(bias));
      return;
   }
   
   // ── GATE 12: Sentiment filter (Phase 3) ──────────────────
   if(InpUseSentiment) {
      double sent = Sentiment_Get(_Symbol);
      if(sent <= InpSentBlockScore) {
         PrintFormat("ISP Sentiment blocked: score=%.4f", sent);
         Log_Skipped(sigStr, score, StringFormat("SENT_%.3f", sent), RegimeStr(regime), BiasStr(bias));
         return;
      }
      // Sentiment tailwind bonus
      if(sig == 1 && sent >= 0.10) score = MathMin(10.0, score + 0.5);
      if(sig ==-1 && sent <= -0.10) score = MathMin(10.0, score + 0.5);
   }
   
   // ── Spread sanity check ───────────────────────────────────
   double atr    = buf_ATR[1];
   double spread = SymbolInfoDouble(_Symbol,SYMBOL_ASK) - SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(spread > atr * 0.5) {
      PrintFormat("ISP: Spread %.5f > ATR*0.5 %.5f — skipping", spread, atr*0.5);
      return;
   }
   
   // ── Position size + execute ───────────────────────────────
   double slDist = atr * InpSL_ATR_Mult;
   double lots   = CalcLotSize(slDist);
   if(lots <= 0) return;
   
   ExecuteTrade(sig, lots, slDist, score, regime, bias);
   DrawDashboard();
}

//============================================================
//  SECTION 10: PROP FIRM RISK MODULE
//============================================================
void UpdateDrawdown() {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_EqHighWater) g_EqHighWater = eq;
   g_DailyDD_Pct = g_DayStartBal > 0 ?
                   MathMax(0, (g_DayStartBal - eq) / g_DayStartBal * 100.0) : 0.0;
   g_MaxDD_Pct   = g_EqHighWater > 0 ?
                   MathMax(0, (g_EqHighWater - eq) / g_EqHighWater * 100.0) : 0.0;
}

void CheckDailyReset() {
   datetime curDay = iTime(_Symbol, PERIOD_D1, 0);
   if(curDay == g_LastDay) return;
   // FIX [17]: Write daily summary before resetting counters
   Log_DailySummary();
   g_DayStartBal = AccountInfoDouble(ACCOUNT_BALANCE);
   g_LastDay     = curDay;
   g_DayTrades = g_DayWins = g_DayLosses = 0;
   g_DayLondon = g_DayLondonW = g_DayNY = g_DayNYW = 0;
   g_DayGWin = g_DayGLoss = g_DayScoreSum = 0;
   g_DayHalted    = false;
   g_ConsecLosses = 0;
   g_PauseUntil   = 0;
   if(g_Halted && StringFind(g_HaltReason, "DAILY") >= 0) {
      g_Halted = false; g_HaltReason = "";
      Print("ISP: Daily reset — trading re-enabled. New balance: ", g_DayStartBal);
   }
}

bool CheckPropFirmRules() {
   UpdateDrawdown();
   
   // Rule 1: Daily loss limit
   if(g_DailyDD_Pct >= InpDailyLossLimit) {
      if(!g_Halted) {
         g_Halted = true; g_HaltReason = "DAILY_LIMIT"; g_DayHalted = true;
         string m = StringFormat("ISP HALT: Daily DD %.2f%% >= limit %.2f%%",
                                 g_DailyDD_Pct, InpDailyLossLimit);
         Alert(m); Print(m); SendNotification(m);
         CloseAllPositions("Daily limit");
         Log_Halt("DAILY_LIMIT");
      }
      return false;
   }
   
   // Rule 2: Max total drawdown (permanent until manual restart)
   if(g_MaxDD_Pct >= InpMaxDDLimit) {
      if(!g_Halted || StringFind(g_HaltReason,"MAX_DD") < 0) {
         g_Halted = true; g_HaltReason = "MAX_DD";
         string m = StringFormat("ISP HALT: Max DD %.2f%% >= limit %.2f%%",
                                 g_MaxDD_Pct, InpMaxDDLimit);
         Alert(m); Print(m); SendNotification(m);
         CloseAllPositions("Max DD");
         Log_Halt("MAX_DD");
      }
      return false;
   }
   
   return !g_Halted;
}

//============================================================
//  SECTION 11: SESSION
//============================================================
bool IsInSession() {
   // Convert server time to UTC using the GMT offset input
   datetime utc = TimeCurrent() - (datetime)(InpServerGMTOffset * 3600);
   MqlDateTime dt; TimeToStruct(utc, dt);
   int hr = dt.hour;
   bool london = (hr >= InpLondonOpenUTC && hr < InpLondonCloseUTC);
   bool ny     = (hr >= InpNYOpenUTC     && hr < InpNYCloseUTC);
   return (london || ny);
}

string GetSession() {
   datetime utc = TimeCurrent() - (datetime)(InpServerGMTOffset * 3600);
   MqlDateTime dt; TimeToStruct(utc, dt);
   int hr = dt.hour;
   if(hr >= InpLondonOpenUTC && hr < InpLondonCloseUTC) return "London";
   if(hr >= InpNYOpenUTC     && hr < InpNYCloseUTC)     return "NY";
   return "Off-Session";
}

//============================================================
//  SECTION 12: BUFFER REFRESH
//============================================================
bool RefreshBuffers() {
   const int N = 60;
   if(CopyBuffer(h_EMA_Fast, 0, 0, N, buf_EmaFast)   <= 0) return false;
   if(CopyBuffer(h_EMA_Mid,  0, 0, N, buf_EmaMid)    <= 0) return false;
   if(CopyBuffer(h_EMA_Slow, 0, 0, N, buf_EmaSlw)    <= 0) return false;
   if(CopyBuffer(h_EMA_H4,   0, 0, N, buf_EmaH4)     <= 0) return false;
   if(CopyBuffer(h_EMA_H1,   0, 0, N, buf_EmaH1)     <= 0) return false;
   if(h_EMA_H1Fast != INVALID_HANDLE)
      if(CopyBuffer(h_EMA_H1Fast, 0, 0, N, buf_EmaH1Fast) <= 0) return false;
   if(CopyBuffer(h_FracM5, FRACTAL_UPPER, 0, N, buf_FracHi)   <= 0) return false;
   if(CopyBuffer(h_FracM5, FRACTAL_LOWER, 0, N, buf_FracLo)   <= 0) return false;
   if(CopyBuffer(h_FracH1, FRACTAL_UPPER, 0, N, buf_FracHiH1) <= 0) return false;
   if(CopyBuffer(h_FracH1, FRACTAL_LOWER, 0, N, buf_FracLoH1) <= 0) return false;
   // FIX [14]: iADX buffers — 0=ADX, 1=+DI, 2=-DI
   if(CopyBuffer(h_ADX_M5, 0, 0, N, buf_ADX)   <= 0) return false;
   if(CopyBuffer(h_ADX_M5, 1, 0, N, buf_DI_P)  <= 0) return false;
   if(CopyBuffer(h_ADX_M5, 2, 0, N, buf_DI_M)  <= 0) return false;
   if(CopyBuffer(h_ADX_H1, 0, 0, N, buf_ADX_H1)<= 0) return false;
   if(CopyBuffer(h_ATR_M5, 0, 0, N, buf_ATR)   <= 0) return false;
   // FIX [13]: RSI buffer for ONNX features
   if(CopyBuffer(h_RSI_M5, 0, 0, N, buf_RSI)   <= 0) return false;
   return true;
}

//============================================================
//  SECTION 13: REGIME DETECTION
//============================================================
ENUM_REGIME GetRegime() {
   double adx  = buf_ADX[1];
   double atr  = buf_ATR[1];
   double aSum = 0; for(int i=2;i<=21;i++) aSum += buf_ATR[i];
   double aAvg = aSum / 20.0;
   if(atr < aAvg * InpATR_MinMult) return REGIME_AVOID;
   if(atr > aAvg * InpATR_MaxMult) return REGIME_AVOID;
   if(adx < InpADX_Avoid)          return REGIME_AVOID;
   if(adx < InpADX_Trend)          return REGIME_RANGE;
   return (buf_DI_P[1] > buf_DI_M[1]) ? REGIME_BULL_TREND : REGIME_BEAR_TREND;
}

//============================================================
//  SECTION 14: HTF BIAS
//============================================================
ENUM_BIAS GetBias() {
   double px = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool bH4      = (px > buf_EmaH4[1]);
   bool bH1      = (px > buf_EmaH1[1]);
   bool bH1Fast  = (h_EMA_H1Fast == INVALID_HANDLE) ? true : (px > buf_EmaH1Fast[1]);
   if(bH4 && bH1 && bH1Fast)   return BIAS_BULL;
   if(!bH4 && !bH1)            return BIAS_BEAR;
   return BIAS_NEUTRAL;
}

//============================================================
//  SECTION 15: ENTRY SIGNAL
//============================================================
int GetSignal(ENUM_BIAS bias, ENUM_REGIME regime) {
   double fast = buf_EmaFast[1], fp = buf_EmaFast[2];
   double mid  = buf_EmaMid[1],  mp = buf_EmaMid[2];
   double slow = buf_EmaSlw[1];
   double c1   = iClose(_Symbol,PERIOD_M5,1);
   double l1   = iLow(_Symbol,PERIOD_M5,1);
   double h1   = iHigh(_Symbol,PERIOD_M5,1);
   
   bool bullAlign = (fast > mid && mid > slow);
   bool bearAlign = (fast < mid && mid < slow);
   bool bullCross = (fp <= mp && fast > mid);
   bool bearCross = (fp >= mp && fast < mid);
   bool bullPull  = (bullAlign && l1 <= mid * 1.0005 && c1 > mid);
   bool bearPull  = (bearAlign && h1 >= mid * 0.9995 && c1 < mid);
   
   // Find recent fractal confirmation
   // BUY: need recent lower fractal (support) below current price broken upward
   bool bullFrac = false, bearFrac = false;
   for(int i=3; i<=15; i++) {
      if(buf_FracLo[i]!=EMPTY_VALUE && buf_FracLo[i]>0 && !bullFrac)
         { bullFrac = (c1 > buf_FracLo[i]); break; }
   }
   for(int i=3; i<=15; i++) {
      if(buf_FracHi[i]!=EMPTY_VALUE && buf_FracHi[i]>0 && !bearFrac)
         { bearFrac = (c1 < buf_FracHi[i]); break; }
   }
   
   int sig = 0;
   if(bias==BIAS_BULL && bullAlign && (bullCross||bullPull) && bullFrac) sig =  1;
   if(bias==BIAS_BEAR && bearAlign && (bearCross||bearPull) && bearFrac) sig = -1;
   // Range: crossovers only
   if(regime==REGIME_RANGE && sig!=0 && !bullCross && !bearCross) sig = 0;
   // Block when LTF regime direction opposes entry direction
   if(regime==REGIME_BEAR_TREND && sig ==  1) sig = 0;
   if(regime==REGIME_BULL_TREND && sig == -1) sig = 0;
   return sig;
}

//============================================================
//  SECTION 16: TRADE QUALITY SCORE
//============================================================
double CalcScore(int sig, ENUM_REGIME regime, ENUM_BIAS bias) {
   double s = 0;
   bool fa = (sig==1) ? (buf_EmaFast[1]>buf_EmaMid[1]&&buf_EmaMid[1]>buf_EmaSlw[1])
                      : (buf_EmaFast[1]<buf_EmaMid[1]&&buf_EmaMid[1]<buf_EmaSlw[1]);
   if(fa) s += 2.0;
   double adx=buf_ADX[1], adxH1=buf_ADX_H1[1];
   if(adx>=InpADX_Trend && adxH1>=InpADX_Trend) s += 2.0;
   else if(adx>=InpADX_Trend || adxH1>=InpADX_Trend) s += 1.0;
   if(IsInSession()) s += 2.0;
   if(sig ==  1 && regime == REGIME_BULL_TREND) s += 1.0;
   if(sig == -1 && regime == REGIME_BEAR_TREND) s += 1.0;
   if(sig==1) { for(int i=3;i<=10;i++) if(buf_FracLoH1[i]!=EMPTY_VALUE&&buf_FracLoH1[i]>0){s+=1;break;} }
   else       { for(int i=3;i<=10;i++) if(buf_FracHiH1[i]!=EMPTY_VALUE&&buf_FracHiH1[i]>0){s+=1;break;} }
   double atr=buf_ATR[1]; double aSum=0;
   for(int i=2;i<=21;i++) aSum+=buf_ATR[i];
   double aAvg=aSum/20.0;
   if(atr>=aAvg*0.8 && atr<=aAvg*1.3) s += 1.0;
   if(CheckSMC(sig)) s += 1.0;
   return MathMin(s, 10.0);
}

bool CheckSMC(int sig) {
   double h3=iHigh(_Symbol,PERIOD_M5,3), l3=iLow(_Symbol,PERIOD_M5,3);
   double h1=iHigh(_Symbol,PERIOD_M5,1), l1=iLow(_Symbol,PERIOD_M5,1);
   if(sig== 1 && h3 < l1) return true;
   if(sig==-1 && l3 > h1) return true;
   double c1=iClose(_Symbol,PERIOD_M5,1), c5=iClose(_Symbol,PERIOD_M5,5);
   double o6=iOpen(_Symbol,PERIOD_M5,6),  c6=iClose(_Symbol,PERIOD_M5,6);
   if(sig== 1 && o6>c6 && c1>c5*1.002) return true;
   if(sig==-1 && o6<c6 && c1<c5*0.998) return true;
   return false;
}

//============================================================
//  SECTION 17: NEWS FILTER
//============================================================
bool IsNewsWindow() {
   g_NewsEventName = "";  // clear on each check
   MqlCalendarValue vals[];
   datetime t0 = TimeCurrent() - InpNewsBefore_Min*60;
   datetime t1 = TimeCurrent() + InpNewsAfter_Min*60;
   int n = CalendarValueHistory(vals, t0, t1, NULL, NULL);
   if(n <= 0) {
      // Warn every 5 min if calendar is empty — broker may not provide calendar data
      static datetime s_lastWarn = 0;
      if(InpUseNews && TimeCurrent() - s_lastWarn > 300) {
         PrintFormat("ISP News: CalendarValueHistory returned 0 events — verify broker calendar is active (t0=%s t1=%s)",
                     TimeToString(t0), TimeToString(t1));
         s_lastWarn = TimeCurrent();
      }
      return false;
   }
   string base  = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   string quote = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   for(int i = 0; i < n; i++) {
      MqlCalendarEvent ev;
      if(!CalendarEventById(vals[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry cc;
      if(!CalendarCountryById(ev.country_id, cc)) continue;
      if(StringFind(base, cc.currency)>=0 || StringFind(quote, cc.currency)>=0) {
         g_NewsEventName = StringFormat("%s (%s)", ev.name, cc.currency);
         PrintFormat("ISP News block: %s", g_NewsEventName);
         return true;
      }
   }
   return false;
}

//============================================================
//  SECTION 18: POSITION SIZING (FIX [2] — universal formula)
//============================================================
double CalcLotSize(double slPriceDist) {
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   // FIX [2]: Universal pip value calculation — works for all pairs including JPY and Gold
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   if(tickVal<=0 || tickSz<=0 || slPriceDist<=0) {
      Print("ISP Sizing: Invalid tick data for ", _Symbol); return 0;
   }
   
   // Reduce risk when near daily limit
   double rMult = 1.0;
   if(g_DailyDD_Pct >= InpDailyLossLimit * 0.75) rMult = 0.25;
   else if(g_DailyDD_Pct >= InpDailyLossLimit * 0.5) rMult = 0.5;
   
   double rPct = InpRiskPct * rMult;
   if(InpHalfKelly) rPct *= 0.5;
   
   double rAmt     = equity * (rPct / 100.0);
   double valPerLot = tickVal / tickSz;  // $ value per 1.0 price unit per lot
   double rawLot   = rAmt / (slPriceDist * valPerLot);
   
   double lots = MathFloor(rawLot / step) * step;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);
   
   // Absolute cap: never exceed 1% equity in one trade
   if(lots * slPriceDist * valPerLot > equity * 0.01)
      lots = MathFloor((equity*0.01/(slPriceDist*valPerLot))/step)*step;
   lots = MathMax(lots, minLot);
   
   PrintFormat("ISP Lot: rPct=%.2f%% rMult=%.1f SLdist=%.5f lot=%.2f eq=$%.2f",
               rPct, rMult, slPriceDist, lots, equity);
   return lots;
}

//============================================================
//  SECTION 19: EXECUTE TRADE
//============================================================
void ExecuteTrade(int sig, double lots, double slDist, double score,
                  ENUM_REGIME regime, ENUM_BIAS bias) {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dgt = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double stp = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mln = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double hl  = MathMax(MathFloor((lots/2.0)/stp)*stp, mln);
   
   double entry, sl, tp1, tp2;
   if(sig == 1) {
      entry=ask;
      sl  =NormalizeDouble(ask - slDist,          dgt);
      tp1 =NormalizeDouble(ask + slDist*InpTP1_RR, dgt);
      tp2 =NormalizeDouble(ask + slDist*InpTP2_RR, dgt);
   } else {
      entry=bid;
      sl  =NormalizeDouble(bid + slDist,          dgt);
      tp1 =NormalizeDouble(bid - slDist*InpTP1_RR, dgt);
      tp2 =NormalizeDouble(bid - slDist*InpTP2_RR, dgt);
   }
   
   // PATCH [E]: Validate SL distance against broker's minimum stop level
   // SYMBOL_TRADE_STOPS_LEVEL is in points; _Point*10 alone is insufficient on many brokers
   {
      long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double minStopDist = MathMax(stopsLevel * _Point, _Point * 10);
      if(MathAbs(entry - sl) <= minStopDist) {
         PrintFormat("ISP v3: SL distance %.5f <= broker min %.5f (stops_level=%d). Expanding SL.",
                     MathAbs(entry-sl), minStopDist, (int)stopsLevel);
         // Expand SL to 110% of minimum distance rather than skipping the trade
         double newSlDist = minStopDist * 1.1;
         if(sig == 1) sl = NormalizeDouble(entry - newSlDist, dgt);
         else         sl = NormalizeDouble(entry + newSlDist, dgt);
         // Recalculate TPs proportionally
         if(sig == 1) { tp1 = NormalizeDouble(entry + newSlDist*InpTP1_RR, dgt);
                        tp2 = NormalizeDouble(entry + newSlDist*InpTP2_RR, dgt); }
         else         { tp1 = NormalizeDouble(entry - newSlDist*InpTP1_RR, dgt);
                        tp2 = NormalizeDouble(entry - newSlDist*InpTP2_RR, dgt); }
      }
   }
   
   string c1 = StringFormat("%s_TP1_S%d", InpComment, (int)(score*10));
   string c2 = StringFormat("%s_TP2_S%d", InpComment, (int)(score*10));
   
   bool ok1 = (sig==1) ? Trade.Buy (hl,_Symbol,ask,sl,tp1,c1)
                       : Trade.Sell(hl,_Symbol,bid,sl,tp1,c1);
   bool ok2 = (sig==1) ? Trade.Buy (hl,_Symbol,ask,sl,tp2,c2)
                       : Trade.Sell(hl,_Symbol,bid,sl,tp2,c2);
   
   if(!ok1 && !ok2) {
      PrintFormat("ISP TRADE FAILED: code=%d '%s'",
                  Trade.ResultRetcode(), Trade.ResultRetcodeDescription());
      return;
   }
   
   string sess = GetSession();
   if(sess=="London") g_DayLondon++;
   else if(sess=="NY") g_DayNY++;
   g_DayScoreSum += score;
   
   // Store record for logging (posId assigned in OnTradeTransaction)
   if(g_RecCount < 49) {
      g_Recs[g_RecCount].posId        = 0; // set on DEAL_ENTRY_IN
      g_Recs[g_RecCount].direction    = (sig==1?"BUY":"SELL");
      g_Recs[g_RecCount].lots         = hl * 2;
      g_Recs[g_RecCount].entry        = entry;
      g_Recs[g_RecCount].sl           = sl;
      g_Recs[g_RecCount].tp1          = tp1;
      g_Recs[g_RecCount].tp2          = tp2;
      g_Recs[g_RecCount].score        = score;
      g_Recs[g_RecCount].regime       = RegimeStr(regime);
      g_Recs[g_RecCount].bias         = BiasStr(bias);
      g_Recs[g_RecCount].session      = sess;
      g_Recs[g_RecCount].ddAtEntry    = g_DailyDD_Pct;
      g_Recs[g_RecCount].maxDDAtEntry = g_MaxDD_Pct;
      g_Recs[g_RecCount].openAtEntry  = CountOpenTrades();
      g_Recs[g_RecCount].balAtEntry   = AccountInfoDouble(ACCOUNT_BALANCE);
      g_Recs[g_RecCount].eqAtEntry    = AccountInfoDouble(ACCOUNT_EQUITY);
      g_Recs[g_RecCount].openTime     = TimeCurrent();
      g_RecCount++;
   }
   
   PrintFormat("ISP OPEN %s %s | Lot %.2f+%.2f | Entry %.5f | SL %.5f | TP1 %.5f | TP2 %.5f | Score %.1f",
               (sig==1?"BUY":"SELL"), _Symbol, hl, hl, entry, sl, tp1, tp2, score);
   SendNotification(StringFormat("ISP %s %s %.1f/10 | SL=%.5f TP=%.5f",
                                 (sig==1?"BUY":"SELL"), _Symbol, score, sl, tp2));
}

//============================================================
//  SECTION 20: TRADE MANAGEMENT (FIX [3] — cached ATR on tick)
//============================================================
void ManageOpenTrades() {
   if(g_CachedATR <= 0) return;
   double trail = g_CachedATR * InpTrail_ATR_Mult;
   int    dgt   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pt    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double slDist = g_CachedATR * InpSL_ATR_Mult;
   
   for(int i = PositionsTotal()-1; i >= 0; i--) {
      if(!PosInfo.SelectByIndex(i)) continue;
      if(PosInfo.Magic()  != InpMagicNumber) continue;
      if(PosInfo.Symbol() != _Symbol) continue;
      if(StringFind(PosInfo.Comment(), "TP2") < 0) continue; // Trail TP2 only
      
      ulong  tkt   = PosInfo.Ticket();
      double opPx  = PosInfo.PriceOpen();
      double curSL = PosInfo.StopLoss();
      double curTP = PosInfo.TakeProfit();
      long   type  = PosInfo.PositionType();
      
      if(type == POSITION_TYPE_BUY) {
         double cur = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(cur - opPx < slDist) continue; // Wait for 1R in profit
         double hh = iHigh(_Symbol, PERIOD_M5, 1);
         for(int b=2; b<=14; b++) hh = MathMax(hh, iHigh(_Symbol,PERIOD_M5,b));
         double nsl = NormalizeDouble(hh - trail, dgt);
         if(nsl > curSL + pt*2) {
            if(!Trade.PositionModify(tkt, nsl, curTP))
               PrintFormat("ISP Trail BUY fail: %d", Trade.ResultRetcode());
         }
      } else {
         double cur = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(opPx - cur < slDist) continue;
         double ll = iLow(_Symbol, PERIOD_M5, 1);
         for(int b=2; b<=14; b++) ll = MathMin(ll, iLow(_Symbol,PERIOD_M5,b));
         double nsl = NormalizeDouble(ll + trail, dgt);
         if(nsl < curSL - pt*2) {
            if(!Trade.PositionModify(tkt, nsl, curTP))
               PrintFormat("ISP Trail SELL fail: %d", Trade.ResultRetcode());
         }
      }
   }
}

//============================================================
//  SECTION 21: ON TRADE TRANSACTION (FIX [5] + [15])
//============================================================
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result) {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   
   // FIX [5]: Must call HistoryDealSelect before any HistoryDeal* functions
   if(!HistoryDealSelect(trans.deal)) return;
   DealInfo.Ticket(trans.deal);
   if(DealInfo.Magic()  != InpMagicNumber) return;
   if(DealInfo.Symbol() != _Symbol) return;
   
   ENUM_DEAL_ENTRY de = DealInfo.Entry();
   
   if(de == DEAL_ENTRY_IN) {
      // New position — link record to position ID
      ulong posId = DealInfo.PositionId();
      for(int i = g_RecCount-1; i >= 0; i--) {
         if(g_Recs[i].posId == 0) { g_Recs[i].posId = posId; break; }
      }
   }
   // FIX [15]: Check DEAL_ENTRY_OUT correctly
   else if(de == DEAL_ENTRY_OUT || de == DEAL_ENTRY_INOUT || de == DEAL_ENTRY_OUT_BY) {
      ulong    posId     = DealInfo.PositionId();
      datetime closeTime = (datetime)DealInfo.Time();
      double   closePx   = DealInfo.Price();
      double   profit    = DealInfo.Profit() + DealInfo.Commission() + DealInfo.Swap();
      
      // Find matching record
      int ri = -1;
      for(int i = 0; i < g_RecCount; i++) {
         if(g_Recs[i].posId == posId) { ri = i; break; }
      }
      
      if(ri >= 0) {
         TradeRecord r = g_Recs[ri];
         // Pips calculation — handles JPY/Gold with different pip sizes
         double pipSz = _Point * 10; // Default (5-digit pairs: 0.00010)
         string sym   = _Symbol;
         if(StringFind(sym,"JPY") >= 0) pipSz = _Point * 100; // JPY: 0.010
         if(StringFind(sym,"XAU") >= 0) pipSz = _Point * 10;  // Gold varies
         
         double pips   = (r.direction=="BUY") ?
                         (closePx - r.entry) / pipSz :
                         (r.entry - closePx) / pipSz;
         string res    = (profit >= 0) ? "WIN" : "LOSS";
         string why    = GetCloseReason(r, closePx);
         
         Log_Trade(r, closeTime, closePx, pips, profit, res, why);
         
         // Update stats
         g_DayTrades++;
         if(profit >= 0) {
            g_DayWins++; g_DayGWin += profit;
            if(r.session == "London") g_DayLondonW++;
            if(r.session == "NY")     g_DayNYW++;
            g_ConsecLosses = 0;  // reset streak on win
         } else {
            g_DayLosses++; g_DayGLoss += profit;
            g_ConsecLosses++;
            if(g_ConsecLosses >= InpMaxConsecLosses) {
               g_PauseUntil = TimeCurrent() + (datetime)(InpConsecPauseHours * 3600);
               string msg = StringFormat(
                  "ISP CONSEC PAUSE: %d losses in a row on %s — pausing %dh until %s",
                  g_ConsecLosses, _Symbol, InpConsecPauseHours,
                  TimeToString(g_PauseUntil, TIME_DATE|TIME_MINUTES));
               Print(msg);
               SendNotification(msg);
            }
         }
         
         // Remove record (ticket-safe array compact)
         for(int i = ri; i < g_RecCount-1; i++) g_Recs[i] = g_Recs[i+1];
         g_RecCount--;
         
         PrintFormat("ISP CLOSE %s %s | %.1f pips | P&L $%.2f | %s | %s",
                     r.direction, _Symbol, pips, profit, res, why);
         
         // Consecutive loss alert
         if(g_DayLosses >= 3 && g_DayLosses > g_DayWins)
            SendNotification(StringFormat("ISP: %d losses today on %s — review conditions",
                                          g_DayLosses, _Symbol));
      }
   }
}

string GetCloseReason(TradeRecord &r, double closePx) {
   double d   = MathAbs(closePx - r.entry);
   double slD = MathAbs(r.sl  - r.entry);
   double t1D = MathAbs(r.tp1 - r.entry);
   double t2D = MathAbs(r.tp2 - r.entry);
   double eps = _Point * 10;
   if(MathAbs(d - t2D) < eps) return "TP2_Trail";
   if(MathAbs(d - t1D) < eps) return "TP1_Hit";
   if(MathAbs(d - slD) < eps) return "SL_Hit";
   bool isLoss = ((r.direction=="BUY"  && closePx < r.entry) ||
                  (r.direction=="SELL" && closePx > r.entry));
   return isLoss ? "Trailing_SL" : "Trailing_TP";
}

//============================================================
//  SECTION 22: UTILITIES (FIX [6] — ticket-based close)
//============================================================
int CountOpenTrades() {
   int n = 0;
   for(int i = 0; i < PositionsTotal(); i++)
      if(PosInfo.SelectByIndex(i) &&
         PosInfo.Magic()  == InpMagicNumber &&
         PosInfo.Symbol() == _Symbol) n++;
   return n;
}

// FIX [6]: Collect tickets first, then close — no index-shift bug
void CloseAllPositions(string reason) {
   Print("ISP: Closing all positions | Reason: ", reason);
   ulong tkts[];
   int   n = 0;
   for(int i = 0; i < PositionsTotal(); i++) {
      if(PosInfo.SelectByIndex(i) &&
         PosInfo.Magic()  == InpMagicNumber &&
         PosInfo.Symbol() == _Symbol) {
         ArrayResize(tkts, n+1);
         tkts[n++] = PosInfo.Ticket();
      }
   }
   for(int i = 0; i < n; i++) {
      if(!Trade.PositionClose(tkts[i], 50))
         PrintFormat("ISP Close fail ticket %I64u: %d", tkts[i], Trade.ResultRetcode());
   }
}

string RegimeStr(ENUM_REGIME r) {
   switch(r){
      case REGIME_BULL_TREND: return "BULL TREND";
      case REGIME_BEAR_TREND: return "BEAR TREND";
      case REGIME_WEAK_TREND: return "WEAK TREND";
      case REGIME_RANGE:      return "RANGE";
      default:                return "AVOID";
   }
}
string BiasStr(ENUM_BIAS b) {
   if(b==BIAS_BULL) return "BULLISH";
   if(b==BIAS_BEAR) return "BEARISH";
   return "NEUTRAL";
}

//============================================================
//  SECTION 23: CHART DASHBOARD (FIX [12] — cached values)
//============================================================
void DrawDashboard() {
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double pnl     = balance - g_DayStartBal;
   double pnlPct  = g_DayStartBal > 0 ? pnl/g_DayStartBal*100 : 0;
   double ddBuf   = InpDailyLossLimit - g_DailyDD_Pct;
   double mdBuf   = InpMaxDDLimit     - g_MaxDD_Pct;
   double wr      = g_DayTrades > 0 ? (double)g_DayWins/g_DayTrades*100 : 0;
   double pf      = g_DayGLoss  != 0 ? g_DayGWin/MathAbs(g_DayGLoss) : 0;
   
   // Phase status strings
   string onnxSt = (g_OnnxHandle != INVALID_HANDLE) ? "ACTIVE" :
                   (InpUseONNX ? "MISSING — Run Phase 2 Python scripts" : "OFF");
   string sentSt = InpUseSentiment ?
                   "ON — isp_sentiment_service.py must be running" : "OFF";
   string logSt  = InpEnableLog ? "ON — Files/"+InpLogFolder+"/" : "OFF";
   
   // Status line — most important info
   string statLn;
   if(g_Halted)         statLn = "🔴 HALTED: " + g_HaltReason;
   else if(!IsInSession()) statLn = "🟡 STANDBY — out of session";
   else                 statLn = "🟢 ACTIVE — scanning";
   
   string hud = StringFormat(
"╔═══════════════════════════════════════╗\n"
"║   INSTITUTIONAL SNIPER PRO  v3.0      ║\n"
"║   %s  │  Magic: %d              \n"
"╠═══════════════════════════════════════╣\n"
"║ ACCOUNT                               \n"
"║  Equity : $%-10.2f Balance: $%.2f\n"
"║  Day P&L: $%-8.2f (%.2f%%)         \n"
"╠═══ PROP FIRM RULES ═══════════════════╣\n"
"║  Daily DD : %5.2f%% / %.1f%%  [buf %.2f%%]\n"
"║  Max DD   : %5.2f%% / %.1f%%  [buf %.2f%%]\n"
"╠═══ TODAY ═════════════════════════════╣\n"
"║  Trades  : %d  (W:%d L:%d)  WR:%.0f%%\n"
"║  P.Factor: %.2f   Score: %.1f/10       \n"
"║  Open    : %d / %d max                 \n"
"╠═══ MARKET ════════════════════════════╣\n"
"║  Regime  : %-18s           \n"
"║  HTF Bias: %-18s           \n"
"║  Session : %-18s           \n"
"║  News    : %-30s\n"
"╠═══ PHASES ════════════════════════════╣\n"
"║  P2 ONNX : %-30s\n"
"║  P3 Sent : %-30s\n"
"║  P4 Log  : %-30s\n"
"╠═══ STATUS ════════════════════════════╣\n"
"║  %-38s\n"
"╚═══════════════════════════════════════╝",
      _Symbol, InpMagicNumber,
      equity, balance,
      pnl, pnlPct,
      g_DailyDD_Pct, InpDailyLossLimit, ddBuf,
      g_MaxDD_Pct,   InpMaxDDLimit,     mdBuf,
      g_DayTrades, g_DayWins, g_DayLosses, wr,
      pf, g_CachedScore,
      CountOpenTrades(), InpMaxOpenTrades,
      RegimeStr(g_CachedRegime),
      BiasStr(g_CachedBias),
      GetSession(),
      (g_NewsEventName != "" ? g_NewsEventName : "None"),
      onnxSt, sentSt, logSt,
      statLn
   );
   Comment(hud);
   ChartRedraw(); // PATCH [F]: Force immediate chart refresh — Comment alone doesn't repaint
}

// PATCH [H]: Throttle OnChartEvent — was calling DrawDashboard on every mouse move
// which spammed Comment() and caused chart flickering + unnecessary CPU load
void OnChartEvent(const int id, const long &lp, const double &dp, const string &sp) {
   static datetime lastDraw = 0;
   if(TimeCurrent() - lastDraw < 2) return; // Max one redraw per 2 seconds
   lastDraw = TimeCurrent();
   DrawDashboard();
}
//+------------------------------------------------------------------+
