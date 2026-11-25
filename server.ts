import 'dotenv/config';
import { execSync, spawn, type ChildProcess } from 'child_process';
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const PY_PORT = Number(process.env.FASTAPI_PORT || 8765);
const PY_BASE_URL = `http://127.0.0.1:${PY_PORT}`;

let pyProcess: ChildProcess | null = null;
let startingBackendPromise: Promise<void> | null = null;

async function isPythonBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${PY_BASE_URL}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

async function startPythonBackendInternal(forceRestart = false): Promise<void> {
  if (forceRestart || (await isPythonBackendUp())) {
    if (!forceRestart && pyProcess && !pyProcess.killed) {
      return;
    }
    try {
      execSync(`pkill -f "uvicorn backend.main:app.*--port ${PY_PORT}"`, {
        stdio: 'ignore',
      });
      await new Promise((r) => setTimeout(r, 350));
    } catch {
      // ignore if process cannot be signaled
    }
  }

  const args = [
    '-m',
    'uvicorn',
    'backend.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    String(PY_PORT),
  ];

  pyProcess = spawn('python', args, {
    cwd: __dirname,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pyProcess.stdout?.on('data', (chunk) => {
    process.stdout.write(`[fastapi] ${chunk}`);
  });
  pyProcess.stderr?.on('data', (chunk) => {
    process.stderr.write(`[fastapi] ${chunk}`);
  });
  pyProcess.on('exit', (code) => {
    if (code !== null && code !== 0) {
      console.error(`[fastapi] exited with code ${code}`);
    }
    pyProcess = null;
  });

  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await isPythonBackendUp()) {
      return;
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error('Timed out waiting for Python FastAPI backend to start');
}

async function ensurePythonBackend(forceRestart = false): Promise<void> {
  if (!forceRestart && pyProcess && !pyProcess.killed && (await isPythonBackendUp())) {
    return;
  }
  if (!startingBackendPromise) {
    startingBackendPromise = startPythonBackendInternal(forceRestart).finally(() => {
      startingBackendPromise = null;
    });
  }
  return startingBackendPromise;
}

function cleanupPython() {
  if (pyProcess && !pyProcess.killed) {
    pyProcess.kill('SIGTERM');
    pyProcess = null;
  }
}

process.on('SIGINT', () => {
  cleanupPython();
  process.exit(0);
});
process.on('SIGTERM', () => {
  cleanupPython();
  process.exit(0);
});

async function startServer() {
  await ensurePythonBackend(true);

  const app = express();

  app.use('/api', express.raw({ type: '*/*', limit: '5mb' }), async (req, res) => {
    try {
      await ensurePythonBackend(false);

      const targetUrl = `${PY_BASE_URL}${req.originalUrl}`;
      const headers: Record<string, string> = {};
      for (const [k, v] of Object.entries(req.headers)) {
        if (k === 'host' || k === 'connection' || k === 'content-length') continue;
        if (typeof v === 'string') headers[k] = v;
        else if (Array.isArray(v)) headers[k] = v.join(', ');
      }

      const hasBody = !['GET', 'HEAD'].includes(req.method.toUpperCase());
      const bodyPayload =
        hasBody && Buffer.isBuffer(req.body) && req.body.length > 0
          ? new Uint8Array(req.body)
          : undefined;

      let upstream: Response;
      try {
        upstream = await fetch(targetUrl, {
          method: req.method,
          headers,
          body: bodyPayload,
        });
      } catch {
        await ensurePythonBackend(true);
        upstream = await fetch(targetUrl, {
          method: req.method,
          headers,
          body: bodyPayload,
        });
      }

      res.status(upstream.status);
      upstream.headers.forEach((value, key) => {
        if (key.toLowerCase() === 'transfer-encoding') return;
        res.setHeader(key, value);
      });

      const arrayBuf = await upstream.arrayBuffer();
      res.send(Buffer.from(arrayBuf));
    } catch (err) {
      console.error('Proxy error:', err);
      res.status(502).json({ detail: 'Backend service unavailable' });
    }
  });

  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distDir = path.resolve(__dirname, 'dist');
    app.use(express.static(distDir));
    app.get('*', (_req, res) => {
      const indexFile = path.join(distDir, 'index.html');
      if (fs.existsSync(indexFile)) {
        res.sendFile(indexFile);
      } else {
        res.status(404).send('Build output not found');
      }
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`TripLedger server listening on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  cleanupPython();
  process.exit(1);
});
