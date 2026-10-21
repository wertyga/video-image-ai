// Запускает Python-скрипт через .venv проекта (Windows и Linux) - для npm run.
//   node scripts/py.mjs scripts/lora_studio.py --port 8190
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const python = process.platform === "win32"
  ? join(root, ".venv", "Scripts", "python.exe")
  : join(root, ".venv", "bin", "python");
if (!existsSync(python)) {
  console.error(`Нет ${python}. Сначала установка: .\\scripts\\setup.ps1 / ./scripts/setup.sh`);
  process.exit(1);
}

const child = spawn(python, process.argv.slice(2), {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONUNBUFFERED: "1" },
});
// Ctrl+C получает и дочерний процесс, ждём его выхода
process.on("SIGINT", () => {});
child.on("exit", (code, signal) => process.exit(signal ? 1 : code ?? 0));
