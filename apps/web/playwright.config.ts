import {defineConfig,devices} from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:90_000,expect:{timeout:15_000},fullyParallel:false,retries:0,reporter:'list',use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure',screenshot:'only-on-failure'},webServer:[
 {command:'rm -f /tmp/airchitect-p2-e2e.db && DATABASE_URL=sqlite+aiosqlite:////tmp/airchitect-p2-e2e.db alembic upgrade head && DATABASE_URL=sqlite+aiosqlite:////tmp/airchitect-p2-e2e.db uvicorn app.main:app --host 0.0.0.0 --port 8000',cwd:'../api',port:8000,reuseExistingServer:false,timeout:120_000},
 {command:'npm run dev -- --port 4173',cwd:'.',port:4173,reuseExistingServer:false,timeout:120_000}
],projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
