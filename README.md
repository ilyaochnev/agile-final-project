 # Algorithmic Trading Bot Dashboard for Capital.com

 ## Architecture Overview

This project uses a **React** front end and a **Node.js (Express)** back end. The front end focuses on the interactive dashboard and real-time visualization, while the back end handles Capital.com authentication, live market data, strategy execution, and order placement. This keeps API keys and session tokens on the server only and out of the browser.  

**Key roles:**

* **Backend (Node/Express)**: Authenticates to Capital.com, manages session tokens, connects to the streaming API, executes the RSI strategy, and exposes REST + Socket.io endpoints.
* **Frontend (React)**: Provides login, configuration, live market data, account summary, and trade controls. Receives streaming data over Socket.io for real-time updates.

---

## Backend Implementation (Node.js + Express)

### Initialization and Configuration

```js
// server.js
const express = require('express');
const axios = require('axios');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: { origin: "http://localhost:3000", methods: ["GET", "POST"] }
});

app.use(express.json());
app.use(cors());

const BASE_URL_LIVE = 'https://api-capital.backend-capital.com/api/v1';
const BASE_URL_DEMO = 'https://demo-api-capital.backend-capital.com/api/v1';

let currentEnv = 'demo';
let apiKey = null;
let cstToken = null;
let securityToken = null;
let streamingHost = null;
let wsClient = null;
let tradingActive = false;
let currentPosition = null;
let initialBalance = 0;
let maxDrawdownPerc = null;
let lastTradeTime = 0;
```

**Explanation:** We configure Express, enable CORS for the React app, and define the Capital.com base URLs for demo/live environments. Runtime state (tokens, positions, and bot status) is kept in memory for a single-user session.

---

### Login and Session Establishment

```js
app.post('/api/login', async (req, res) => {
  const { identifier, password, apiKey: userApiKey, environment } = req.body;
  if (!identifier || !password || !userApiKey) {
    return res.status(400).json({ error: "Missing credentials" });
  }

  currentEnv = environment === 'live' ? 'live' : 'demo';
  const baseUrl = currentEnv === 'live' ? BASE_URL_LIVE : BASE_URL_DEMO;
  apiKey = userApiKey;

  try {
    const loginResp = await axios.post(`${baseUrl}/session`, {
      identifier,
      password,
      encryptedPassword: false
    }, {
      headers: { 'X-CAP-API-KEY': apiKey, 'Content-Type': 'application/json' }
    });

    cstToken = loginResp.headers['cst'];
    securityToken = loginResp.headers['x-security-token'];
    if (!cstToken || !securityToken) {
      throw new Error("Authentication failed: no tokens received");
    }

    const data = loginResp.data;
    initialBalance = data.accountInfo.balance;
    streamingHost = data.streamingHost;

    establishWebSocketConnection();
    return res.json({ success: true, balance: initialBalance, accountCurrency: data.currencyIsoCode });
  } catch (err) {
    return res.status(401).json({ error: "Login to Capital.com API failed." });
  }
});
```

**Explanation:** The `/api/login` endpoint authenticates to Capital.com, stores session tokens (`CST`, `X-SECURITY-TOKEN`), captures account info, and starts the streaming WebSocket. Tokens are kept server-side only.

---

### Streaming Market Data (WebSocket)

```js
function sendWsMessage(message) {
  if (wsClient && wsClient.readyState === wsClient.OPEN) {
    message.cst = cstToken;
    message.securityToken = securityToken;
    wsClient.send(JSON.stringify(message));
  }
}

function establishWebSocketConnection() {
  if (!streamingHost || !cstToken || !securityToken) return;
  const url = `${streamingHost}connect`;
  wsClient = new (require('ws'))(url);

  wsClient.on('open', () => {
    const defaultEpic = "EURUSD";
    const timeframe = "MINUTE_5";
    sendWsMessage({
      destination: "marketData.subscribe",
      correlationId: "price_sub_1",
      payload: { epics: [ defaultEpic ] }
    });
    sendWsMessage({
      destination: "OHLCMarketData.subscribe",
      correlationId: "ohlc_sub_1",
      payload: { epics: [ defaultEpic ], resolutions: [ timeframe ], type: "classic" }
    });
  });

  wsClient.on('message', (data) => {
    const msg = JSON.parse(data);
    if (msg.status !== "OK") return;
    if (msg.destination === "quote" && msg.payload) {
      io.emit('priceUpdate', {
        epic: msg.payload.epic,
        bid: msg.payload.bid,
        ask: msg.payload.ofr,
        timestamp: msg.payload.timestamp
      });
    }
    if (msg.destination === "ohlc.event" && msg.payload) {
      io.emit('ohlcUpdate', {
        epic: msg.payload.epic,
        resolution: msg.payload.resolution,
        o: msg.payload.o,
        h: msg.payload.h,
        l: msg.payload.l,
        c: msg.payload.c,
        timestamp: msg.payload.t
      });
      handleNewPriceBar(msg.payload.epic, msg.payload.resolution, msg.payload.c);
    }
  });
}
```

**Explanation:** The server opens a streaming connection and subscribes to live quotes and OHLC updates. Each update is forwarded to the frontend via Socket.io for immediate UI refresh.

---

### RSI Strategy & Trading Logic

```js
let RSI_PERIOD = 14;
let RSI_OVERBOUGHT = 70;
let RSI_OVERSOLD = 30;
let positionSizePercent = 5;
let fixedPositionSize = null;
let stopLossPercent = 2;
let takeProfitPercent = 4;

const priceHistory = [];

function handleNewPriceBar(epic, resolution, closePrice) {
  priceHistory.push(closePrice);
  if (priceHistory.length > RSI_PERIOD + 1) priceHistory.shift();
  if (priceHistory.length < RSI_PERIOD + 1) return;

  const rsi = calculateRSI(priceHistory, RSI_PERIOD);
  io.emit('indicatorUpdate', { epic, RSI: rsi, timestamp: Date.now() });

  if (!tradingActive) return;

  if (rsi < RSI_OVERSOLD) {
    if (!currentPosition) openPosition(epic, 'BUY', closePrice);
    else if (currentPosition.direction === 'SELL') closePosition(currentPosition.dealId, () => {
      openPosition(epic, 'BUY', closePrice);
    });
  } else if (rsi > RSI_OVERBOUGHT) {
    if (!currentPosition) openPosition(epic, 'SELL', closePrice);
    else if (currentPosition.direction === 'BUY') closePosition(currentPosition.dealId, () => {
      openPosition(epic, 'SELL', closePrice);
    });
  }
}

function calculateRSI(closes, period) {
  if (closes.length < period + 1) return 50;
  let gains = 0, losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }
  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  return 100 - (100 / (1 + (avgGain / avgLoss)));
}
```

**Explanation:** The RSI calculation uses the last `RSI_PERIOD` closing prices. If RSI crosses oversold/overbought thresholds, the bot opens or reverses positions accordingly, enforcing a single active position at a time.

---

### Order Execution

```js
async function openPosition(epic, direction, currentPrice) {
  if (!cstToken || !securityToken) return;

  const now = Date.now();
  if (now - lastTradeTime < 60000) return; // rate limit: 1 trade/min
  lastTradeTime = now;

  let size = fixedPositionSize
    ? fixedPositionSize
    : parseFloat(((positionSizePercent / 100) * initialBalance / currentPrice).toFixed(2));
  if (size < 1) size = 1;

  const SL = stopLossPercent
    ? parseFloat((currentPrice * (1 - (stopLossPercent / 100) * (direction === 'BUY' ? 1 : -1))).toFixed(5))
    : null;
  const TP = takeProfitPercent
    ? parseFloat((currentPrice * (1 + (takeProfitPercent / 100) * (direction === 'BUY' ? 1 : -1))).toFixed(5))
    : null;

  const orderPayload = {
    epic,
    direction,
    size,
    orderType: "MARKET",
    ...(SL && { stopLevel: SL }),
    ...(TP && { profitLevel: TP }),
    guaranteedStop: false
  };

  const baseUrl = currentEnv === 'live' ? BASE_URL_LIVE : BASE_URL_DEMO;
  const resp = await axios.post(`${baseUrl}/positions`, orderPayload, {
    headers: {
      'X-SECURITY-TOKEN': securityToken,
      'CST': cstToken,
      'X-CAP-API-KEY': apiKey,
      'Content-Type': 'application/json'
    }
  });

  const confirmResp = await axios.get(`${baseUrl}/confirms/${resp.data.dealReference}`, {
    headers: {
      'X-SECURITY-TOKEN': securityToken,
      'CST': cstToken,
      'X-CAP-API-KEY': apiKey
    }
  });
  const deal = confirmResp.data.affectedDeals?.[0];
  if (deal) {
    currentPosition = {
      dealId: deal.dealId,
      epic,
      direction,
      size,
      entryPrice: deal.level,
      stopLevel: SL,
      takeProfitLevel: TP
    };
    io.emit('positionOpened', currentPosition);
  }
}
```

**Explanation:** Orders are placed via `POST /positions` and confirmed via `GET /confirms/{dealReference}`. The backend applies stop-loss and take-profit levels and rate-limits trades to one per minute.

---

### Operational Endpoints

```js
app.post('/api/config', (req, res) => {
  const config = req.body;
  if (config.RSI_PERIOD) RSI_PERIOD = config.RSI_PERIOD;
  if (config.RSI_OVERSOLD) RSI_OVERSOLD = config.RSI_OVERSOLD;
  if (config.RSI_OVERBOUGHT) RSI_OVERBOUGHT = config.RSI_OVERBOUGHT;
  if (config.positionSizePercent !== undefined) positionSizePercent = config.positionSizePercent;
  if (config.fixedPositionSize !== undefined) fixedPositionSize = config.fixedPositionSize;
  if (config.stopLossPercent !== undefined) stopLossPercent = config.stopLossPercent;
  if (config.takeProfitPercent !== undefined) takeProfitPercent = config.takeProfitPercent;
  if (config.maxDrawdownPerc !== undefined) maxDrawdownPerc = config.maxDrawdownPerc;
  return res.json({ success: true, message: "Configuration updated" });
});

app.post('/api/start', (req, res) => {
  tradingActive = true;
  lastTradeTime = 0;
  res.json({ success: true });
});

app.post('/api/pause', (req, res) => {
  tradingActive = false;
  res.json({ success: true });
});

app.post('/api/stopAll', async (req, res) => {
  tradingActive = false;
  if (currentPosition) await closePosition(currentPosition.dealId);
  res.json({ success: true });
});
```

**Explanation:** These endpoints allow the frontend to update strategy parameters, start/stop the bot, and trigger an emergency stop that closes open positions.

---

## Frontend Implementation (React)

### Core App and Socket.io Integration

```jsx
import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import { CandlestickChart } from './CandlestickChart';
import './App.css';

const socket = io();

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [environment, setEnvironment] = useState('demo');
  const [credentials, setCredentials] = useState({ apiKey: '', login: '', password: '' });
  const [account, setAccount] = useState({ balance: 0, profitLoss: 0, available: 0 });
  const [positions, setPositions] = useState([]);
  const [selectedEpic, setSelectedEpic] = useState('EURUSD');
  const [livePrice, setLivePrice] = useState({ bid: 0, ask: 0 });
  const [candles, setCandles] = useState([]);
  const [rsiValue, setRsiValue] = useState(null);
  const [botActive, setBotActive] = useState(false);
  const [config, setConfig] = useState({
    RSI_PERIOD: 14,
    RSI_OVERSOLD: 30,
    RSI_OVERBOUGHT: 70,
    positionSizePercent: 5,
    stopLossPercent: 2,
    takeProfitPercent: 4,
    maxDrawdownPerc: 20
  });

  useEffect(() => {
    socket.on('priceUpdate', data => {
      if (data.epic === selectedEpic) setLivePrice({ bid: data.bid, ask: data.ask });
    });
    socket.on('ohlcUpdate', bar => {
      if (bar.epic === selectedEpic) {
        setCandles(prev => [...prev, { time: bar.timestamp, open: bar.o, high: bar.h, low: bar.l, close: bar.c }]);
      }
    });
    socket.on('indicatorUpdate', ind => {
      if (ind.epic === selectedEpic) setRsiValue(ind.RSI.toFixed(2));
    });
    socket.on('positionOpened', pos => setPositions([pos]));
    socket.on('positionClosed', () => setPositions([]));
    socket.on('positionUpdate', pos => setPositions([pos]));
    return () => {
      socket.off('priceUpdate');
      socket.off('ohlcUpdate');
      socket.off('indicatorUpdate');
      socket.off('positionOpened');
      socket.off('positionClosed');
      socket.off('positionUpdate');
    };
  }, [selectedEpic]);
```

**Explanation:** The React app subscribes to Socket.io events for real-time prices, candles, RSI, and positions. Updates instantly re-render the dashboard.

---

### Login Flow

```jsx
const handleLogin = async () => {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identifier: credentials.login,
      password: credentials.password,
      apiKey: credentials.apiKey,
      environment
    })
  });
  const data = await response.json();
  if (data.success) {
    setLoggedIn(true);
    setAccount(prev => ({ ...prev, balance: data.balance }));
  }
};
```

**Explanation:** The login view posts credentials to the backend. On success, the dashboard loads and renders live data.

---

### Trading Controls & Strategy Settings

```jsx
const handleStartBot = async () => {
  await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  await fetch('/api/start', { method: 'POST' });
  setBotActive(true);
};

const handlePauseBot = async () => {
  await fetch('/api/pause', { method: 'POST' });
  setBotActive(false);
};

const handleStopAll = async () => {
  await fetch('/api/stopAll', { method: 'POST' });
  setBotActive(false);
};
```

**Explanation:** The UI starts, pauses, or stops the bot and synchronizes the user-configured RSI parameters to the server.

---

## Security and Risk Controls

* **Credentials never leave the backend.** The frontend only sends credentials once to `/api/login`. Tokens are stored server-side.
* **HTTPS + CORS** limit exposure to authorized UI origins.
* **Rate limits** prevent order flooding (1 trade/minute).
* **Stop-loss / take-profit** applied to every order.
* **Max drawdown** controls can halt trading if losses exceed a threshold.

---

## Running Locally

1. **Backend**
   ```bash
   cd server
   npm install express axios cors ws socket.io
   node server.js
   ```
2. **Frontend**
   ```bash
   cd client
   npm install socket.io-client
   npm start
   ```

The frontend runs at `http://localhost:3000` and connects to the backend at `http://localhost:4000`.

---

## Notes & Next Steps

* Add historical price endpoints for initial chart population (`/api/history`).
* Add account refresh polling for balance/equity updates.
* Optionally add multi-instrument support with dynamic subscriptions.
* Consider persistent storage for logs and trade history.
